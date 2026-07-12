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


def verify_amplify_run(run_id: str, expected_app_name: str = "") -> VerifierResult:
    apps = _aws_json(aws_command(["amplify", "list-apps"]), timeout=45).get("apps", [])
    matched: list[dict] = []
    failures: list[str] = []
    for app in apps:
        app_id = str(app.get("appId") or "")
        arn = str(app.get("appArn") or "")
        if not app_id:
            continue
        tags = _aws_json(aws_command(["amplify", "list-tags-for-resource", "--resource-arn", arn]), timeout=30).get("tags", {}) if arn else {}
        if str(tags.get("cloud-cua-run")) != run_id:
            continue
        branches = _aws_json(aws_command(["amplify", "list-branches", "--app-id", app_id]), timeout=30).get("branches", [])
        jobs: list[dict] = []
        for branch in branches:
            branch_name = str(branch.get("branchName") or "")
            if branch_name:
                summaries = _aws_json(aws_command(["amplify", "list-jobs", "--app-id", app_id, "--branch-name", branch_name, "--max-results", "10"]), timeout=30).get("jobSummaries", [])
                jobs.extend({"branch": branch_name, **item} for item in summaries)
        successful = [item for item in jobs if item.get("status") == "SUCCEED"]
        default_domain = str(app.get("defaultDomain") or "")
        urls = [f"https://{branch.get('branchName')}.{default_domain}" for branch in branches if branch.get("branchName") and default_domain]
        matched.append({"appId": app_id, "name": app.get("name"), "tags": tags, "branches": branches, "jobs": jobs, "urls": urls})
        if expected_app_name and app.get("name") != expected_app_name:
            failures.append(f"Tagged Amplify app name mismatch: expected {expected_app_name}, found {app.get('name')}.")
        if not branches:
            failures.append(f"Amplify app {app_id} has no branch.")
        if not successful:
            failures.append(f"Amplify app {app_id} has no successful deployment job.")
        if not urls:
            failures.append(f"Amplify app {app_id} has no branch URL.")
    if not matched:
        failures.append(f"No Amplify app tagged cloud-cua-run={run_id} was found.")
    return VerifierResult("aws_amplify_run", "failed" if failures else "passed", "aws amplify list/get branches/jobs/tags", json.dumps({"apps": matched, "failures": failures}, indent=2))


def verify_s3_static_run(run_id: str, region: str = "us-east-1") -> VerifierResult:
    buckets = _aws_json(aws_command(["s3api", "list-buckets"]), timeout=30).get("Buckets", [])
    matched: list[dict] = []
    failures: list[str] = []
    for item in buckets:
        name = str(item.get("Name") or "")
        if not name.startswith("cloud-cua-"):
            continue
        tagging = _aws_json(aws_command(["s3api", "get-bucket-tagging", "--bucket", name]), timeout=30)
        tags = {str(tag.get("Key")): str(tag.get("Value")) for tag in tagging.get("TagSet", [])}
        if tags.get("cloud-cua-run") != run_id:
            continue
        website = _aws_json(aws_command(["s3api", "get-bucket-website", "--bucket", name]), timeout=30)
        head = _aws_json(aws_command(["s3api", "head-object", "--bucket", name, "--key", "index.html"]), timeout=30)
        endpoint = f"http://{name}.s3-website-{region}.amazonaws.com"
        matched.append({"bucket": name, "tags": tags, "website": website, "index": head, "url": endpoint})
        if website.get("IndexDocument", {}).get("Suffix") != "index.html":
            failures.append(f"S3 bucket {name} does not use index.html as its website index.")
        if not head:
            failures.append(f"S3 bucket {name} does not contain index.html.")
    if not matched:
        failures.append(f"No S3 website bucket tagged cloud-cua-run={run_id} was found.")
    return VerifierResult("aws_s3_static_run", "failed" if failures else "passed", "aws s3api tagging/website/head-object", json.dumps({"buckets": matched, "failures": failures}, indent=2))


def verify_runtime_secret_references(contract: DeploymentContract) -> VerifierResult:
    failures: list[str] = []
    evidence: list[dict] = []
    for env_name, arn in sorted(contract.runtime_secret_references.items()):
        marker = ":parameter/"
        if marker not in arn:
            failures.append(f"{env_name} is not an SSM parameter ARN.")
            continue
        parameter_name = "/" + arn.split(marker, 1)[1]
        result = _aws_json(aws_command(["ssm", "get-parameter", "--name", parameter_name]), timeout=30)
        parameter = result.get("Parameter", {})
        evidence.append({"name": env_name, "reference": arn, "type": parameter.get("Type"), "version": parameter.get("Version")})
        if parameter.get("Type") != "SecureString":
            failures.append(f"{env_name} parameter {parameter_name} is missing or is not SecureString.")
    return VerifierResult("aws_runtime_secrets", "failed" if failures else "passed", "aws ssm get-parameter without decryption", json.dumps({"references": evidence, "failures": failures}, indent=2))


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
        target_groups.update(_service_target_groups(item))

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
    mappings = tagged.get("ResourceTagMappingList", [])
    service_mappings = {
        str(item.get("ResourceARN", "")): {str(tag.get("Key", "")): str(tag.get("Value", "")) for tag in item.get("Tags", [])}
        for item in mappings
        if ":ecs:" in str(item.get("ResourceARN", "")) and ":service/" in str(item.get("ResourceARN", ""))
    }
    service_arns = sorted(service_mappings)
    failures: list[str] = []
    evidence: list[dict] = []
    if not service_arns:
        failures.append(f"No ECS service carrying cloud-cua-run={run_id} was found.")

    for arn in service_arns:
        actual_tags = service_mappings.get(arn, {})
        for key, expected in contract.required_tags.items():
            if actual_tags.get(key) != expected:
                failures.append(f"ECS service {arn} tag {key!r} mismatch: expected {expected!r}, found {actual_tags.get(key)!r}.")
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
            actual_health_path = active_configuration.get("healthCheckPath")
            if actual_health_path != contract.health_check_path:
                failures.append(
                    f"ECS Express health path mismatch: expected {contract.health_check_path!r}, found {actual_health_path!r}."
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

        target_groups = _service_target_groups(service)
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


def _service_target_groups(service: dict) -> set[str]:
    target_groups = {
        str(item.get("targetGroupArn"))
        for item in service.get("loadBalancers", []) or []
        if item.get("targetGroupArn")
    }
    for event in service.get("events", [])[:20]:
        message = str(event.get("message", ""))
        target_groups.update(re.findall(r"(arn:aws:elasticloadbalancing:[^)\s]+:targetgroup/[^)\s]+)", message))
    return target_groups


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


def verify_cloudtrail_run(run_id: str, event_names: list[str], start_time: str) -> VerifierResult:
    found: list[dict] = []
    for event_name in event_names:
        command = aws_command(
            [
                "cloudtrail",
                "lookup-events",
                "--lookup-attributes",
                f"AttributeKey=EventName,AttributeValue={event_name}",
                "--start-time",
                start_time,
                "--max-results",
                "50",
            ]
        )
        for item in _aws_json(command, timeout=45).get("Events", []):
            raw = str(item.get("CloudTrailEvent") or "")
            if run_id in raw or any(run_id in str(resource) for resource in item.get("Resources", [])):
                found.append({"eventName": item.get("EventName"), "eventTime": item.get("EventTime"), "resources": item.get("Resources", [])})
    status = "passed" if found else "skipped"
    summary = json.dumps({"run_id": run_id, "events": found, "note": "CloudTrail lookup can be delayed; exact resource verifiers remain authoritative."}, indent=2)
    return VerifierResult("aws_cloudtrail_run", status, "aws cloudtrail lookup-events", summary)


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
