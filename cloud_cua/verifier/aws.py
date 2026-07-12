from __future__ import annotations

from .base import VerifierResult, run_command


def verify_aws_identity() -> VerifierResult:
    return run_command("aws_identity", ["aws", "sts", "get-caller-identity"], timeout=30)


def verify_amplify_apps() -> VerifierResult:
    return run_command("aws_amplify_list_apps", ["aws", "amplify", "list-apps"], timeout=30)


def verify_cloudtrail_event(event_name: str) -> VerifierResult:
    return run_command(
        f"aws_cloudtrail_{event_name}",
        ["aws", "cloudtrail", "lookup-events", "--lookup-attributes", f"AttributeKey=EventName,AttributeValue={event_name}"],
        timeout=30,
    )

