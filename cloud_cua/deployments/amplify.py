from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from cloud_cua.models import RepoContext
from cloud_cua.deployment_contract import DeploymentContract
from cloud_cua.deployment_milestones import extract_json_object
from cloud_cua.h_runner import HTaskResult


@dataclass(frozen=True)
class AmplifyPlan:
    supported: bool
    app_name: str
    branch: str
    build_command: str | None
    output_directory: str | None
    env_vars: list[str]
    approval_required: bool
    h_inspect_task: str
    h_modify_task: str | None
    verifier_names: list[str]
    risks: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def build_amplify_plan(repo_name: str, ctx: RepoContext, branch: str = "main") -> AmplifyPlan:
    supported = ctx.recommendation == "aws_amplify"
    risks = list(ctx.risks)
    if not supported:
        risks.append(f"Repo recommendation is {ctx.recommendation}, not aws_amplify.")

    slug = re.sub(r"[^a-z0-9-]+", "-", repo_name.lower()).strip("-") or "app"
    app_name = f"cloud-cua-{slug}"[:50].rstrip("-")
    inspect_task = (
        "Open the AWS Amplify console and report whether an app can be created for this repo. "
        "Check whether GitHub/account linking is required. Do not create, edit, or delete anything."
    )
    modify_task = None
    if supported:
        modify_task = (
            f"Create or configure an AWS Amplify app named {app_name} for branch {branch}. "
            f"Use build command {ctx.build_command or 'the detected build command'} and output directory {ctx.output_directory or 'the detected output directory'}. "
            "Stop and report if GitHub OAuth, billing, broad permissions, or any destructive action is requested."
        )

    return AmplifyPlan(
        supported=supported,
        app_name=app_name,
        branch=branch,
        build_command=ctx.build_command,
        output_directory=ctx.output_directory,
        env_vars=ctx.env_vars,
        approval_required=supported,
        h_inspect_task=inspect_task,
        h_modify_task=modify_task,
        verifier_names=["aws_identity", "aws_amplify_list_apps", "http_live_url", "playwright_render"],
        risks=risks,
    )


@dataclass(frozen=True)
class AmplifyMilestoneReview:
    status: str
    observation: dict
    objections: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def build_amplify_inspection_task(contract: DeploymentContract) -> str:
    return f"""Milestone: inspect_amplify_manual_deploy

Open AWS Amplify Hosting in {contract.cloud_region}. Do not type, upload, create, edit, or submit anything. Inspect whether Deploy without Git is available and whether Amazon S3 is available as the manual deployment source. Report visible defaults and blockers through the structured schema.

Contract:
{contract.h_instructions()}
"""


def review_amplify_inspection(result: HTaskResult, contract: DeploymentContract) -> AmplifyMilestoneReview:
    data = extract_json_object(result.summary) if result.status == "completed" else None
    objections: list[str] = []
    if not data:
        objections.append("H did not return structured Amplify inspection evidence.")
        data = {}
    if data.get("manual_deploy_available") is not True:
        objections.append("Amplify Deploy without Git is not available.")
    if data.get("s3_source_available") is not True:
        objections.append("Amazon S3 is not available as the manual deployment source.")
    if data.get("region") not in {None, "", contract.cloud_region}:
        objections.append("Amplify console region does not match the contract.")
    if data.get("blockers"):
        objections.extend(str(item) for item in data["blockers"])
    return AmplifyMilestoneReview("blocked" if objections else "clear", data, tuple(objections))


def build_amplify_prepare_task(contract: DeploymentContract) -> str:
    artifact = _parse_s3_artifact(contract.artifact_reference)
    source_steps = (
        f"Click Browse S3. In the AWS picker, select bucket {artifact[0]!r}, then select object {artifact[1]!r}, "
        "and confirm the selection. Do not type or paste an s3:// URI into the location field."
        if artifact
        else "Stop because the contract does not contain a valid s3:// bucket/object artifact reference."
    )
    return f"""Milestone: prepare_amplify_manual_deploy

Use the loaded cloud-cua/aws-amplify skill. User approval is granted to prepare, but not submit, this manual deployment. Choose Deploy without Git and Amazon S3. Fill the exact app name and branch from the contract. {source_steps} Apply every required tag if the form exposes tags. Do not connect GitHub and do not click Save and deploy.

Contract:
{contract.h_instructions()}

Return structured evidence. Set ready_to_submit=true only when every value matches and the form remains unsubmitted.
"""


def _parse_s3_artifact(reference: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"s3://([^/]+)/(.+)", reference.strip())
    if not match:
        return None
    return match.group(1), match.group(2)


def review_amplify_prepared(result: HTaskResult, contract: DeploymentContract) -> AmplifyMilestoneReview:
    data = extract_json_object(result.summary) if result.status == "completed" else None
    objections: list[str] = []
    if not data:
        objections.append("H did not return structured prepared-form evidence.")
        data = {}
    expected = {
        "app_name": contract.resource_name,
        "branch_name": contract.branch_name,
        "artifact_reference": contract.artifact_reference,
    }
    for key, value in expected.items():
        if str(data.get(key) or "") != str(value):
            objections.append(f"Prepared Amplify {key} does not match the contract.")
    if data.get("ready_to_submit") is not True:
        objections.append("Amplify form is not confirmed ready to submit.")
    if data.get("submitted") is True:
        objections.append("H submitted during the prepare-only milestone.")
    if data.get("blockers"):
        objections.extend(str(item) for item in data["blockers"])
    return AmplifyMilestoneReview("blocked" if objections else "clear", data, tuple(objections))


def build_amplify_submit_task(contract: DeploymentContract) -> str:
    return f"""Milestone: submit_amplify_manual_deploy

The immediately preceding checkpoint proved the unsubmitted Amplify manual deployment form matches this contract:
{contract.h_instructions()}

Do not edit or retype fields. Confirm no new login, IAM, billing, validation, or source blocker is visible. If clear, click Save and deploy exactly once. Wait for AWS to return an app ID and deployment status. Never click submit twice. Return structured creation evidence including app ID, branch, deployment status, public app URL, tags, console URL, and blockers.
"""


def review_amplify_creation(result: HTaskResult, contract: DeploymentContract) -> AmplifyMilestoneReview:
    data = extract_json_object(result.summary) if result.status == "completed" else None
    objections: list[str] = []
    if not data:
        objections.append("H did not return structured Amplify creation evidence.")
        data = {}
    if data.get("app_name") != contract.resource_name:
        objections.append("Created Amplify app name does not match the contract.")
    if data.get("branch_name") != contract.branch_name:
        objections.append("Created Amplify branch does not match the contract.")
    if not data.get("app_id"):
        objections.append("Amplify app ID is missing.")
    url = str(data.get("public_app_url") or "")
    if not url.startswith("https://") or "console.aws.amazon.com" in url:
        objections.append("Amplify public app URL is missing or invalid.")
    if data.get("blockers"):
        objections.extend(str(item) for item in data["blockers"])
    return AmplifyMilestoneReview("blocked" if objections else "clear", data, tuple(objections))
