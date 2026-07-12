from __future__ import annotations

import json
import re
import subprocess

from ..deployment_contract import DeploymentContract

from ..aws_cli import aws_command
from .base import VerifierResult, run_command


def verify_aws_identity() -> VerifierResult:
    return run_command("aws_identity", aws_command(["sts", "get-caller-identity"]), timeout=30)


def verify_amplify_apps() -> VerifierResult:
    return run_command("aws_amplify_list_apps", aws_command(["amplify", "list-apps"]), timeout=30)


def verify_app_runner_services() -> VerifierResult:
    return run_command("aws_app_runner_services", aws_command(["apprunner", "list-services"]), timeout=30)


def verify_ecs_clusters() -> VerifierResult:
    return run_command("aws_ecs_clusters", aws_command(["ecs", "list-clusters"]), timeout=30)


def verify_ecs_run_services(run_id: str) -> VerifierResult:
    tagged = _aws_json(
        aws_command(
            [
                "resourcegroupstaggingapi",
                "get-resources",
                "--tag-filters",
                "Key=cloud-cua,Values=true",
                f"Key=cloud-cua-run,Values={run_id}",
            ]
        ),
        timeout=45,
    )
    service_arns = sorted(
        {
            str(item.get("ResourceARN", ""))
            for item in tagged.get("ResourceTagMappingList", [])
            if ":ecs:" in str(item.get("ResourceARN", "")) and ":service/" in str(item.get("ResourceARN", ""))
        }
    )
    if not service_arns:
        return VerifierResult("aws_ecs_run_services", "failed", "aws resourcegroupstaggingapi get-resources", f"No tagged ECS service found for run {run_id}.")

    summaries: list[dict] = []
    failures: list[str] = []
    target_groups: set[str] = set()
    for arn in service_arns:
        parsed = _parse_ecs_service_arn(arn)
        if not parsed:
            failures.append(f"Could not parse ECS service ARN: {arn}")
            continue
        cluster, service = parsed
        data = _aws_json(aws_command(["ecs", "describe-services", "--cluster", cluster, "--services", service, "--include", "TAGS"]), timeout=45)
        services = data.get("services", [])
        if not services:
            failures.append(f"ECS service not returned by describe-services: {service}")
            continue
        item = services[0]
        deployments = item.get("deployments", [])
        primary = next((dep for dep in deployments if dep.get("status") == "PRIMARY"), deployments[0] if deployments else {})
        events = item.get("events", [])
        service_summary = {
            "service": service,
            "status": item.get("status"),
            "desiredCount": item.get("desiredCount"),
            "runningCount": item.get("runningCount"),
            "pendingCount": item.get("pendingCount"),
            "rolloutState": primary.get("rolloutState"),
            "rolloutStateReason": primary.get("rolloutStateReason"),
            "failedTasks": primary.get("failedTasks", 0),
            "recentEvents": [event.get("message") for event in events[:5]],
        }
        summaries.append(service_summary)
        if item.get("status") != "ACTIVE":
            failures.append(f"{service} status is {item.get('status')}.")
        desired = int(item.get("desiredCount") or 0)
        running = int(item.get("runningCount") or 0)
        if desired > 0 and running < desired:
            failures.append(f"{service} has {running}/{desired} running tasks.")
        rollout = primary.get("rolloutState")
        if rollout and rollout != "COMPLETED":
            failures.append(f"{service} rolloutState is {rollout}: {primary.get('rolloutStateReason')}")
        for event in events[:20]:
            message = str(event.get("message", ""))
            target_groups.update(re.findall(r"(arn:aws:elasticloadbalancing:[^)\s]+:targetgroup/[^)\s]+)", message))

    target_health: list[dict] = []
    for target_group in sorted(target_groups):
        health = _aws_json(aws_command(["elbv2", "describe-target-health", "--target-group-arn", target_group]), timeout=45)
        descriptions = health.get("TargetHealthDescriptions", [])
        states = []
        for description in descriptions:
            state = description.get("TargetHealth", {}).get("State")
            reason = description.get("TargetHealth", {}).get("Reason")
            target = description.get("Target", {})
            states.append({"target": target, "state": state, "reason": reason})
            if state != "healthy":
                failures.append(f"Target group {target_group} has target {target.get('Id')}:{target.get('Port')} in state {state} ({reason}).")
        target_health.append({"targetGroupArn": target_group, "targets": states})

    summary = json.dumps({"services": summaries, "targetHealth": target_health, "failures": failures}, indent=2)
    return VerifierResult("aws_ecs_run_services", "failed" if failures else "passed", "aws ecs describe-services + elbv2 describe-target-health", summary)


def verify_ecs_contract(run_id: str, contract: DeploymentContract) -> VerifierResult:
    command_label = "aws resourcegroupstaggingapi + ecs describe-services + ecs describe-task-definition + elbv2 describe-target-health"
    tagged = _aws_json(
        aws_command(
            [
                "resourcegroupstaggingapi",
                "get-resources",
                "--tag-filters",
                "Key=cloud-cua,Values=true",
                f"Key=cloud-cua-run,Values={run_id}",
            ]
        ),
        timeout=45,
    )
    service_arns = sorted(
        str(item.get("ResourceARN", ""))
        for item in tagged.get("ResourceTagMappingList", [])
        if ":ecs:" in str(item.get("ResourceARN", "")) and ":service/" in str(item.get("ResourceARN", ""))
    )
    failures: list[str] = []
    evidence: list[dict] = []
    if not service_arns:
        failures.append(f"No ECS service carrying cloud-cua-run={run_id} was found.")

    for arn in service_arns:
        parsed = _parse_ecs_service_arn(arn)
        if not parsed:
            failures.append(f"Could not parse tagged ECS service ARN {arn}.")
            continue
        cluster, service_name = parsed
        service_data = _aws_json(
            aws_command(["ecs", "describe-services", "--cluster", cluster, "--services", service_name, "--include", "TAGS"]),
            timeout=45,
        )
        services = service_data.get("services", [])
        if not services:
            failures.append(f"Tagged ECS service {service_name} was not returned by describe-services.")
            continue
        service = services[0]
        express_service: dict = {}
        active_configuration: dict = {}
        endpoints: list[str] = []
        if contract.target == "aws_ecs_express":
            express_data = _aws_json(
                aws_command(["ecs", "describe-express-gateway-service", "--service-arn", arn, "--include", "TAGS"]),
                timeout=45,
            )
            express_service = express_data.get("service", {})
            active_configurations = express_service.get("activeConfigurations", [])
            active_configuration = active_configurations[0] if active_configurations else {}
            endpoints = sorted(
                str(item.get("endpoint"))
                for item in active_configuration.get("ingressPaths", [])
                if item.get("endpoint")
            )
        task_definition_arn = str(active_configuration.get("taskDefinitionArn") or service.get("taskDefinition") or "")
        if not task_definition_arn:
            failures.append(f"ECS service {service_name} has no task definition ARN.")
            continue
        primary_container = active_configuration.get("primaryContainer", {})
        if primary_container:
            images = [str(primary_container.get("image"))] if primary_container.get("image") else []
            ports = [int(primary_container.get("containerPort"))] if primary_container.get("containerPort") is not None else []
        else:
            task_data = _aws_json(
                aws_command(["ecs", "describe-task-definition", "--task-definition", task_definition_arn, "--include", "TAGS"]),
                timeout=45,
            )
            task_definition = task_data.get("taskDefinition", {})
            containers = task_definition.get("containerDefinitions", [])
            images = sorted({str(item.get("image", "")) for item in containers if item.get("image")})
            ports = sorted(
                {
                    int(mapping.get("containerPort"))
                    for item in containers
                    for mapping in item.get("portMappings", [])
                    if mapping.get("containerPort") is not None
                }
            )
        if contract.container_image_uri and contract.container_image_uri not in images:
            failures.append(f"Task definition image mismatch: expected {contract.container_image_uri}, found {images or 'none'}.")
        if contract.selected_container_port is not None and contract.selected_container_port not in ports:
            failures.append(f"Task definition port mismatch: expected {contract.selected_container_port}, found {ports or 'none'}.")

        desired = int(service.get("desiredCount") or 0)
        running = int(service.get("runningCount") or 0)
        deployments = service.get("deployments", [])
        primary = next((item for item in deployments if item.get("status") == "PRIMARY"), deployments[0] if deployments else {})
        service_status = express_service.get("status", {}).get("statusCode") or service.get("status")
        if service_status != "ACTIVE":
            failures.append(f"ECS service {service_name} status is {service_status}.")
        if desired < 1 or running < desired:
            failures.append(f"ECS service {service_name} has {running}/{desired} running tasks.")
        if primary.get("rolloutState") and primary.get("rolloutState") != "COMPLETED":
            failures.append(f"ECS service {service_name} rollout is {primary.get('rolloutState')}.")

        target_groups = {
            str(item.get("targetGroupArn"))
            for item in service.get("loadBalancers", [])
            if item.get("targetGroupArn")
        }
        target_health: list[dict] = []
        if not target_groups:
            failures.append(f"ECS service {service_name} exposes no target group for health verification.")
        for target_group in sorted(target_groups):
            health_data = _aws_json(aws_command(["elbv2", "describe-target-health", "--target-group-arn", target_group]), timeout=45)
            descriptions = health_data.get("TargetHealthDescriptions", [])
            if not descriptions:
                failures.append(f"Target group {target_group} has no registered targets.")
            for item in descriptions:
                state = str(item.get("TargetHealth", {}).get("State", "unknown"))
                target = item.get("Target", {})
                target_health.append({"target": target, "state": state})
                if state != "healthy":
                    failures.append(f"Target {target.get('Id')}:{target.get('Port')} is {state}, not healthy.")
        evidence.append(
            {
                "serviceArn": arn,
                "taskDefinitionArn": task_definition_arn,
                "images": images,
                "ports": ports,
                "desiredCount": desired,
                "runningCount": running,
                "targetHealth": target_health,
                "endpoints": endpoints,
            }
        )

    summary = json.dumps({"contract": contract.to_dict(), "services": evidence, "failures": failures}, indent=2)
    return VerifierResult("aws_ecs_contract", "failed" if failures else "passed", command_label, summary)


def verify_ecr_repositories() -> VerifierResult:
    return run_command("aws_ecr_repositories", aws_command(["ecr", "describe-repositories"]), timeout=30)


def verify_lambda_functions() -> VerifierResult:
    return run_command("aws_lambda_functions", aws_command(["lambda", "list-functions", "--max-items", "20"]), timeout=30)


def verify_s3_buckets() -> VerifierResult:
    return run_command("aws_s3_list_buckets", aws_command(["s3api", "list-buckets"]), timeout=30)


def verify_cloudformation_stacks() -> VerifierResult:
    return run_command(
        "aws_cloudformation_stacks",
        aws_command(["cloudformation", "list-stacks", "--stack-status-filter", "CREATE_COMPLETE", "UPDATE_COMPLETE"]),
        timeout=30,
    )


def verify_tagged_resources(run_id: str | None = None) -> VerifierResult:
    filters = ["Key=cloud-cua,Values=true"]
    name = "aws_tagged_cloud_cua_resources"
    if run_id:
        filters.append(f"Key=cloud-cua-run,Values={run_id}")
        name = "aws_tagged_run_resources"
    return run_command(
        name,
        aws_command(["resourcegroupstaggingapi", "get-resources", "--tag-filters", *filters]),
        timeout=45,
    )


def verify_cloudtrail_event(event_name: str) -> VerifierResult:
    return run_command(
        f"aws_cloudtrail_{event_name}",
        aws_command(["cloudtrail", "lookup-events", "--lookup-attributes", f"AttributeKey=EventName,AttributeValue={event_name}"]),
        timeout=30,
    )


def _parse_ecs_service_arn(arn: str) -> tuple[str, str] | None:
    # arn:aws:ecs:region:account:service/cluster/service-name
    try:
        tail = arn.split(":service/", 1)[1]
        cluster, service = tail.split("/", 1)
        return cluster, service
    except Exception:
        return None


def _aws_json(command: list[str], timeout: int = 30) -> dict:
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    except Exception:
        return {}
    if proc.returncode != 0 or not proc.stdout.strip():
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}
