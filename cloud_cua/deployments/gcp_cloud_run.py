from __future__ import annotations

from dataclasses import asdict, dataclass

from cloud_cua.models import RepoContext


DEFAULT_GCP_REGION = "us-central1"


@dataclass(frozen=True)
class GCPCloudRunPlan:
    target: str
    service_name: str
    region: str
    supported: bool
    reason: str
    commands_or_console: list[str]
    risks: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def build_gcp_cloud_run_plan(repo_name: str, ctx: RepoContext, *, region: str = DEFAULT_GCP_REGION) -> GCPCloudRunPlan:
    supported = ctx.dockerfile or ctx.category in {"node_api", "python_api", "containerized_web", "nextjs"}
    service_name = _service_name(repo_name)
    reason = "Cloud Run is a fit for containerized or HTTP service repos." if supported else "Repo is not clearly deployable as a Cloud Run HTTP service yet."
    return GCPCloudRunPlan(
        target="gcp_cloud_run",
        service_name=service_name,
        region=region,
        supported=supported,
        reason=reason,
        commands_or_console=[
            "Confirm gcloud auth and selected project.",
            f"Use Cloud Run in region {region}.",
            f"Create or update service {service_name}.",
            "Stop before public unauthenticated access unless user approved it.",
        ],
        risks=[
            "Cloud Run may need Artifact Registry, Cloud Build, IAM service accounts, and public endpoint approval.",
            "GCP billing must be enabled on the selected project.",
            "Container port/env var settings may need repo-specific input.",
        ],
    )


def build_gcp_cloud_run_h_task(repo_name: str, ctx: RepoContext, plan: GCPCloudRunPlan, user_task: str | None = None) -> str:
    requested = user_task.strip() if user_task and user_task.strip() else f"Deploy {repo_name} to GCP Cloud Run if it is safe and supported."
    return (
        "You are operating the GCP Console for Cloud CUA.\n"
        "Goal: complete a safe Cloud Run deployment task or stop with a precise blocker.\n\n"
        f"Requested task:\n{requested}\n\n"
        f"Service name: {plan.service_name}\n"
        f"Region: {plan.region}\n"
        f"Repo category: {ctx.category}\n"
        f"Framework: {ctx.framework}\n"
        f"Dockerfile present: {ctx.dockerfile}\n"
        f"Build command: {ctx.build_command or 'not detected'}\n"
        f"Start command: {ctx.start_command or 'not detected'}\n"
        f"Env var names only: {', '.join(ctx.env_vars) if ctx.env_vars else 'none detected'}\n\n"
        "Safety constraints:\n"
        "- Do not enable billing or increase quotas.\n"
        "- Stop before unauthenticated public access unless approval was granted.\n"
        "- Stop before creating broad IAM/service account permissions unless approval was granted.\n"
        "- Add labels cloud-cua=true and cloud-cua-repo when the console exposes labels.\n"
        "- Final answer must include service name, region, URL, and blockers.\n"
    )


def _service_name(repo_name: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in repo_name).strip("-")
    return ("cloud-cua-" + safe)[:60].rstrip("-")
