from __future__ import annotations

from dataclasses import asdict, dataclass

from cloud_cua.deployment_contract import DeploymentContract
from cloud_cua.models import RepoContext


DEFAULT_MAX_SPEND_USD = 5.0
DEFAULT_AWS_REGION = "us-east-1"
RESOURCE_PREFIX = "cloud-cua"


@dataclass(frozen=True)
class AWSDeploymentOption:
    target: str
    label: str
    fit: str
    console_url: str
    why: str
    h_task_goal: str
    verifier_names: list[str]
    risks: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AWSDeploymentPlan:
    repo_category: str
    framework: str
    primary_target: str
    max_spend_usd: float
    region: str
    resource_prefix: str
    options: list[AWSDeploymentOption]
    approval_required: bool
    global_constraints: list[str]
    unknowns: list[str]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["options"] = [option.to_dict() for option in self.options]
        return data

    def option(self, target: str | None) -> AWSDeploymentOption:
        if target:
            for option in self.options:
                if option.target == target:
                    return option
        for option in self.options:
            if option.target == self.primary_target:
                return option
        return self.options[0]


def build_aws_deployment_plan(
    repo_name: str,
    ctx: RepoContext,
    *,
    max_spend_usd: float = DEFAULT_MAX_SPEND_USD,
    region: str = DEFAULT_AWS_REGION,
) -> AWSDeploymentPlan:
    options = _options_for_context(repo_name, ctx)
    if not options:
        options = [_fallback_option(repo_name, ctx)]
    primary = options[0].target
    unknowns = list(ctx.risks)
    if not ctx.env_vars:
        unknowns.append("No env example found; runtime secrets may be missing.")
    if ctx.category in {"containerized_web", "node_api", "python_api"}:
        unknowns.append("AWS App Runner is closed to new customers; use ECS Express Mode or another active AWS service.")

    return AWSDeploymentPlan(
        repo_category=ctx.category,
        framework=ctx.framework,
        primary_target=primary,
        max_spend_usd=max_spend_usd,
        region=region,
        resource_prefix=RESOURCE_PREFIX,
        options=options,
        approval_required=True,
        global_constraints=[
            f"Do not create resources expected to cost more than ${max_spend_usd:.2f}.",
            f"Prefer region {region} unless the AWS console forces another region.",
            f"Name created resources with the prefix {RESOURCE_PREFIX}-{repo_name}.",
            "Add tag cloud-cua=true and cloud-cua-repo to resources whenever the console exposes tags.",
            "Add tag cloud-cua-run when Cloud CUA provides a run id.",
            "Stop before billing plan changes, broad administrator IAM, deleting existing non-cloud-cua resources, or GitHub OAuth/account linking.",
            "If the selected service is not appropriate, stop and explain the better AWS service instead of improvising an unsafe deployment.",
            "Do not choose AWS App Runner for new accounts; AWS says App Runner is no longer open to new customers.",
        ],
        unknowns=unknowns,
    )


def build_general_aws_h_task(
    repo_name: str,
    ctx: RepoContext,
    plan: AWSDeploymentPlan,
    *,
    target: str | None = None,
    user_task: str | None = None,
    run_id: str | None = None,
    prepared_inputs: dict[str, str] | None = None,
    contract: DeploymentContract | None = None,
) -> str:
    option = plan.option(target)
    repo_details = [
        f"Repo name: {repo_name}",
        f"Detected framework: {ctx.framework}",
        f"Detected category: {ctx.category}",
        f"Package manager: {ctx.package_manager}",
        f"Build command: {ctx.build_command or 'not detected'}",
        f"Start command: {ctx.start_command or 'not detected'}",
        f"Output directory: {ctx.output_directory or 'not detected'}",
        f"Dockerfile present: {ctx.dockerfile}",
        f"Env var names only: {', '.join(ctx.env_vars) if ctx.env_vars else 'none detected'}",
    ]
    constraints_items = list(plan.global_constraints)
    if run_id:
        constraints_items.append(f"Use cloud-cua-run={run_id} as the run tag value whenever tags are available.")
    constraints = "\n".join(f"- {item}" for item in constraints_items)
    risks = "\n".join(f"- {item}" for item in option.risks)
    requested = user_task.strip() if user_task and user_task.strip() else option.h_task_goal
    prepared = ""
    if prepared_inputs:
        prepared_lines = [f"- {key}: {value}" for key, value in prepared_inputs.items() if value]
        if prepared_lines:
            prepared = "\n\nPrepared inputs from Codex/local repo tools:\n" + "\n".join(prepared_lines)
    contract_text = ""
    if contract:
        contract_text = "\n\n" + contract.h_instructions()
    return (
        "You are operating the AWS Console for Cloud CUA.\n"
        "Goal: complete a safe deployment task or stop with a precise blocker.\n\n"
        f"Requested task:\n{requested}\n\n"
        f"Recommended AWS target: {option.label} ({option.target})\n"
        f"Open or navigate to: {option.console_url}\n\n"
        "Repo facts:\n"
        + "\n".join(f"- {item}" for item in repo_details)
        + prepared
        + contract_text
        + "\n\nSafety constraints:\n"
        + constraints
        + "\n\nKnown risks for this target:\n"
        + risks
        + "\n\nRequired final answer:\n"
        "- What AWS service/page you used.\n"
        "- Every created or modified resource name.\n"
        "- Region.\n"
        "- Any live URL or deployment status URL.\n"
        "- The public application URL separately from any AWS Console URL.\n"
        "- Any blocker that needs the user, Codex, or AWS CLI.\n"
        "- Current task count/target health if ECS is used.\n"
        "- Whether the run stayed under the $5 budget constraint.\n"
    )


def _options_for_context(repo_name: str, ctx: RepoContext) -> list[AWSDeploymentOption]:
    if ctx.category == "frontend_static":
        return [
            _amplify_option(repo_name),
            _s3_static_option(repo_name),
        ]
    if ctx.category == "nextjs":
        return [
            _amplify_option(repo_name),
            _ecs_express_option(repo_name, "Next.js can run as a containerized web service if Amplify is blocked."),
        ]
    if ctx.category == "containerized_web":
        return [
            _ecs_express_option(repo_name, "Dockerfile detected; ECS Express Mode is AWS's active simple-path service for containerized web apps."),
            _ecs_fargate_option(repo_name),
            _app_runner_deprecated_option(repo_name),
        ]
    if ctx.category in {"node_api", "python_api"}:
        return [
            _lambda_option(repo_name),
            _ecs_express_option(repo_name, "API service detected; ECS Express Mode is the active AWS simple-path container option if the app is containerized."),
            _app_runner_deprecated_option(repo_name),
        ]
    if ctx.category == "serverless":
        return [_lambda_option(repo_name)]
    if ctx.category == "iac":
        return [_iac_option(repo_name)]
    return []


def _amplify_option(repo_name: str) -> AWSDeploymentOption:
    return AWSDeploymentOption(
        target="aws_amplify",
        label="AWS Amplify",
        fit="frontend or Next.js app",
        console_url="https://console.aws.amazon.com/amplify/apps",
        why="Best first UI path for frontend repos and Git-backed web app hosting.",
        h_task_goal=f"Create or configure an Amplify app for {repo_name}, stopping before GitHub OAuth or billing prompts.",
        verifier_names=["aws_identity", "aws_amplify_list_apps", "http_live_url", "playwright_render"],
        risks=["GitHub OAuth may require the user.", "Build settings can be wrong if the repo lacks scripts.", "Public URL is created."],
    )


def _s3_static_option(repo_name: str) -> AWSDeploymentOption:
    return AWSDeploymentOption(
        target="aws_s3_static_site",
        label="S3 static website",
        fit="static frontend artifact",
        console_url="https://s3.console.aws.amazon.com/s3/home",
        why="Useful for static builds when Amplify is not desired.",
        h_task_goal=f"Create a low-cost S3 static website bucket for {repo_name} only if the user explicitly wants S3 hosting.",
        verifier_names=["aws_identity", "aws_s3_list_buckets", "http_live_url"],
        risks=["Bucket/public access settings can expose files.", "CloudFront/custom domain should be skipped under the $5 budget unless approved."],
    )


def _app_runner_deprecated_option(repo_name: str) -> AWSDeploymentOption:
    return AWSDeploymentOption(
        target="aws_app_runner_deprecated",
        label="AWS App Runner (deprecated for new customers)",
        fit="existing App Runner customers only",
        console_url="https://console.aws.amazon.com/apprunner/home",
        why="AWS says App Runner is no longer open to new customers. This option is listed only to explain why Cloud CUA will not choose it.",
        h_task_goal=f"Do not create an App Runner service for {repo_name}. Report that App Runner is closed to new customers and recommend ECS Express Mode.",
        verifier_names=["aws_identity", "aws_app_runner_services"],
        risks=["Blocked for new AWS customers.", "No new feature roadmap.", "Should not be used as the default deployment path."],
    )


def _ecs_express_option(repo_name: str, why: str) -> AWSDeploymentOption:
    return AWSDeploymentOption(
        target="aws_ecs_express",
        label="Amazon ECS Express Mode",
        fit="Dockerized web app or API",
        console_url="https://console.aws.amazon.com/ecs/v2/express",
        why=why,
        h_task_goal=(
            f"Create an Amazon ECS Express Mode service for {repo_name} only after a container image URI, task execution role, "
            "and infrastructure role are available. If any of those inputs are missing, stop and report exactly what Codex must prepare."
        ),
        verifier_names=["aws_identity", "aws_tagged_run_resources", "aws_ecs_clusters", "http_live_url"],
        risks=[
            "Requires a container image in ECR or another registry.",
            "Requires ECS task execution and infrastructure IAM roles.",
            "Creates Fargate, load balancer, security group, logging, and networking resources.",
            "Can exceed $5 if left running; cleanup must be easy.",
        ],
    )


def _ecs_fargate_option(repo_name: str) -> AWSDeploymentOption:
    return AWSDeploymentOption(
        target="aws_ecs_fargate",
        label="ECS Fargate",
        fit="containerized production service",
        console_url="https://console.aws.amazon.com/ecs/v2/clusters",
        why="More flexible than App Runner, but has more IAM/networking/cost surface.",
        h_task_goal=f"Inspect ECS deployment feasibility for {repo_name}; do not create a cluster unless the user explicitly approves ECS.",
        verifier_names=["aws_identity", "aws_ecs_clusters"],
        risks=["Can create load balancers, NAT, networking, and IAM roles.", "Easy to exceed $5 if left running."],
    )


def _lambda_option(repo_name: str) -> AWSDeploymentOption:
    return AWSDeploymentOption(
        target="aws_lambda",
        label="AWS Lambda",
        fit="serverless function or small API",
        console_url="https://console.aws.amazon.com/lambda/home",
        why="Good for function-style apps and low idle cost.",
        h_task_goal=f"Inspect whether {repo_name} can be deployed to Lambda; stop before creating IAM roles or API Gateway unless approved.",
        verifier_names=["aws_identity", "aws_lambda_functions"],
        risks=["Needs IAM execution role.", "May need API Gateway for public HTTP.", "Packaging can be runtime-specific."],
    )


def _iac_option(repo_name: str) -> AWSDeploymentOption:
    return AWSDeploymentOption(
        target="aws_iac_review",
        label="Infrastructure-as-Code review",
        fit="Terraform/SAM/CDK repo",
        console_url="https://console.aws.amazon.com/cloudformation/home",
        why="IaC repos should usually be planned and verified before any console action.",
        h_task_goal=f"Use AWS console only to inspect existing stacks/resources for {repo_name}; do not apply IaC through the console.",
        verifier_names=["aws_identity", "aws_cloudformation_stacks"],
        risks=["Applying IaC can create many resources.", "Console drift can conflict with repo state."],
    )


def _fallback_option(repo_name: str, ctx: RepoContext) -> AWSDeploymentOption:
    return AWSDeploymentOption(
        target="aws_cua_discovery",
        label="AWS console discovery",
        fit="unknown deployment task",
        console_url="https://console.aws.amazon.com/",
        why="Repo type is not confidently classified; CUA should inspect and ask for a safer target.",
        h_task_goal=f"Inspect AWS console options for deploying {repo_name}, then stop with a recommended service and needed inputs.",
        verifier_names=["aws_identity"],
        risks=[f"Repo category is {ctx.category}.", "Deployment target is not known enough for automatic creation."],
    )
