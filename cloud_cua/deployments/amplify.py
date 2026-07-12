from __future__ import annotations

from dataclasses import asdict, dataclass

from cloud_cua.models import RepoContext


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

    app_name = f"cloud-cua-{repo_name}".lower().replace(" ", "-")[:50]
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

