from __future__ import annotations

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
