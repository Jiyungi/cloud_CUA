from __future__ import annotations

from .base import VerifierResult, run_command


def verify_aws_identity() -> VerifierResult:
    return run_command("aws_identity", ["aws", "sts", "get-caller-identity"], timeout=30)


def verify_amplify_apps() -> VerifierResult:
    return run_command("aws_amplify_list_apps", ["aws", "amplify", "list-apps"], timeout=30)


def verify_app_runner_services() -> VerifierResult:
    return run_command("aws_app_runner_services", ["aws", "apprunner", "list-services"], timeout=30)


def verify_ecs_clusters() -> VerifierResult:
    return run_command("aws_ecs_clusters", ["aws", "ecs", "list-clusters"], timeout=30)


def verify_lambda_functions() -> VerifierResult:
    return run_command("aws_lambda_functions", ["aws", "lambda", "list-functions", "--max-items", "20"], timeout=30)


def verify_s3_buckets() -> VerifierResult:
    return run_command("aws_s3_list_buckets", ["aws", "s3api", "list-buckets"], timeout=30)


def verify_cloudformation_stacks() -> VerifierResult:
    return run_command(
        "aws_cloudformation_stacks",
        ["aws", "cloudformation", "list-stacks", "--stack-status-filter", "CREATE_COMPLETE", "UPDATE_COMPLETE"],
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
        ["aws", "resourcegroupstaggingapi", "get-resources", "--tag-filters", *filters],
        timeout=45,
    )


def verify_cloudtrail_event(event_name: str) -> VerifierResult:
    return run_command(
        f"aws_cloudtrail_{event_name}",
        ["aws", "cloudtrail", "lookup-events", "--lookup-attributes", f"AttributeKey=EventName,AttributeValue={event_name}"],
        timeout=30,
    )
