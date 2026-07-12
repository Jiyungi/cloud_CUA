from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from .dashboard import render_dashboard
from .orchestrator import Orchestrator
from .h_session_manager import get_h_session_manager
from .cost_monitor import get_cost_monitor
from .paths import resolve_repo_path
from .voice_stream import handle_voice_stream


class StartRequest(BaseModel):
    repo_path: str
    cloud: str = "aws"
    mode: str = "vibe"


class ModeRequest(BaseModel):
    repo_path: str
    mode: str


class RepoRunRequest(BaseModel):
    repo_path: str


class VoiceRequest(BaseModel):
    repo_path: str
    text: str


class VoiceAudioRequest(BaseModel):
    repo_path: str
    audio_base64: str
    input_format: str = "webm"


class HTaskRequest(BaseModel):
    repo_path: str
    task: str | None = None


class AWSDeploymentTaskRequest(BaseModel):
    repo_path: str
    task: str | None = None
    target: str | None = None
    max_spend_usd: float = 5.0


class GCPDeploymentTaskRequest(BaseModel):
    repo_path: str
    task: str | None = None


class VerifierRequest(BaseModel):
    repo_path: str
    verifier_name: str = "default"
    url: str | None = None


class ApprovalRequest(BaseModel):
    repo_path: str
    action: str
    reason: str
    risk_level: str = "medium"


class ApprovalDecisionRequest(BaseModel):
    repo_path: str
    approval_id: str
    approved: bool


class CleanupRequest(BaseModel):
    repo_path: str
    run_id: str | None = None
    dry_run: bool = True


class SkillSyncRequest(BaseModel):
    repo_path: str
    names: list[str] | None = None
    dry_run: bool = False


class DashboardRequest(BaseModel):
    repo_path: str
    dashboard_url: str


class CodexMessageRequest(BaseModel):
    repo_path: str
    message: str


class RuntimeConfigurationRequest(BaseModel):
    repo_path: str
    values: dict[str, str] = Field(default_factory=dict)
    existing_references: dict[str, str] = Field(default_factory=dict)
    region: str = "us-east-1"


class CostExtensionRequest(BaseModel):
    repo_path: str
    new_cap_usd: float


def create_app() -> FastAPI:
    app = FastAPI(title="Cloud CUA")
    service_token = os.environ.get("CLOUD_CUA_SERVICE_TOKEN", "")
    launch_tokens: dict[str, tuple[float, str, str]] = {}
    if service_token or os.environ.get("CLOUD_CUA_CONTAINER") == "1":
        get_cost_monitor().recover()

    @app.middleware("http")
    async def local_service_auth(request: Request, call_next):
        if not service_token or request.url.path in {"/", "/health"}:
            return await call_next(request)
        supplied = request.headers.get("X-Cloud-CUA-Token") or request.cookies.get("cloud_cua_session")
        if not secrets.compare_digest(supplied or "", service_token):
            return JSONResponse({"detail": "Cloud CUA local service authentication failed."}, status_code=401)
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"ok": True, "service": "cloud-cua"}

    @app.get("/defaults")
    def defaults():
        return {"repo_path": str(Path.cwd())}

    @app.get("/capabilities")
    def capabilities(repo_path: str):
        return Orchestrator(repo_path).capabilities()

    @app.get("/skills")
    def skills(repo_path: str):
        return Orchestrator(repo_path).get_skill_status()

    @app.post("/skills/sync")
    def sync_skills(req: SkillSyncRequest):
        return Orchestrator(req.repo_path).sync_h_skills(req.names, req.dry_run)

    @app.post("/dashboard-launch")
    def dashboard_launch(req: RepoRunRequest, request: Request):
        launch_token = secrets.token_urlsafe(24)
        launch_tokens[launch_token] = (time.time() + 60, req.repo_path, request.query_params.get("run_id", ""))
        run_id = request.query_params.get("run_id", "")
        clean_query = urlencode({"repo_path": req.repo_path, "run_id": run_id})
        launch_query = clean_query + "&" + urlencode({"launch_token": launch_token})
        base = os.environ.get("CLOUD_CUA_PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
        return {"dashboard_url": f"{base}/?{clean_query}", "launch_url": f"{base}/?{launch_query}"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        launch_token = request.query_params.get("launch_token")
        if launch_token and service_token:
            entry = launch_tokens.pop(launch_token, None)
            if not entry or entry[0] < time.time():
                return HTMLResponse("Cloud CUA dashboard launch link expired. Ask Codex to open the dashboard again.", status_code=401)
            clean_query = urlencode({"repo_path": entry[1], "run_id": request.query_params.get("run_id", "")})
            response = RedirectResponse(f"/?{clean_query}", status_code=303)
            response.set_cookie("cloud_cua_session", service_token, httponly=True, samesite="strict")
            return response
        if service_token and not secrets.compare_digest(request.cookies.get("cloud_cua_session") or "", service_token):
            return HTMLResponse(
                "<!doctype html><title>Reconnect Cloud CUA</title>"
                "<main style='max-width:560px;margin:80px auto;font:16px system-ui;line-height:1.5'>"
                "<h1>Dashboard connection expired</h1>"
                "<p>This page is not authorized to control the local Cloud CUA backend.</p>"
                "<p>Ask Codex to open Cloud CUA again, or run <code>cloud-cua dashboard --repo-path &quot;C:\\path\\to\\repo&quot;</code>.</p>"
                "</main>",
                status_code=401,
            )
        return render_dashboard()

    @app.post("/runs")
    def start_run(req: StartRequest):
        repo = resolve_repo_path(req.repo_path)
        if not repo.is_dir():
            raise HTTPException(status_code=400, detail=f"Repository folder does not exist: {req.repo_path}")
        return Orchestrator(repo).start_deployment(req.cloud, req.mode)

    @app.get("/runs")
    def list_runs(repo_path: str):
        return Orchestrator(repo_path).list_runs()

    @app.get("/runs/{run_id}")
    def get_run(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_status(run_id)

    @app.post("/runs/{run_id}/dashboard")
    def set_dashboard(run_id: str, req: DashboardRequest):
        return Orchestrator(req.repo_path).set_dashboard_url(run_id, req.dashboard_url)

    @app.get("/runs/{run_id}/events")
    def get_events(run_id: str, repo_path: str, limit: int = 100):
        return Orchestrator(repo_path).get_events(run_id, limit)

    @app.get("/runs/{run_id}/handoff")
    def get_handoff(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_handoff_state(run_id)

    @app.get("/runs/{run_id}/watch")
    def watch_run(run_id: str, repo_path: str, cursor: int = 0, timeout_seconds: int = 20):
        return Orchestrator(repo_path).watch_run(run_id, cursor, timeout_seconds)

    @app.get("/runs/{run_id}/pending-actions")
    def pending_actions(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_pending_actions(run_id)

    @app.get("/runs/{run_id}/lesson")
    def get_lesson(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_lesson_candidate(run_id)

    @app.get("/runs/{run_id}/skill-state")
    def get_run_skill_state(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_run_skill_state(run_id)

    @app.post("/runs/{run_id}/mode")
    def set_mode(run_id: str, req: ModeRequest):
        return Orchestrator(req.repo_path).set_mode(run_id, req.mode)

    @app.post("/runs/{run_id}/open-browser")
    def open_browser(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).open_browser_for_login(run_id)

    @app.post("/runs/{run_id}/continue-login")
    def continue_login(run_id: str, req: RepoRunRequest):
        result = Orchestrator(req.repo_path).continue_after_login(run_id)
        if result.get("current_step") == "browser_identity_verifying":
            job = get_h_session_manager().schedule(
                req.repo_path,
                run_id,
                "browser-identity",
                lambda: Orchestrator(req.repo_path).inspect_browser_identity(run_id),
            )
            result["h_job"] = job.get("h_job")
        return result

    @app.get("/runs/{run_id}/browser-identity")
    def browser_identity(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_browser_identity(run_id)

    @app.post("/runs/{run_id}/pause")
    def pause(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).pause(run_id)

    @app.post("/runs/{run_id}/resume")
    def resume(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).resume(run_id)

    @app.post("/runs/{run_id}/cancel")
    def cancel(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).cancel(run_id)

    @app.get("/runs/{run_id}/h-job")
    def h_job(run_id: str, repo_path: str):
        return get_h_session_manager().get(repo_path, run_id) or {"status": "idle"}

    @app.get("/runs/{run_id}/runtime-configuration")
    def runtime_configuration(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_runtime_configuration(run_id)

    @app.get("/runs/{run_id}/cost")
    def cost_status(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_cost_status(run_id)

    @app.post("/runs/{run_id}/cost-extension")
    def cost_extension(run_id: str, req: CostExtensionRequest):
        return Orchestrator(req.repo_path).request_cost_extension(run_id, req.new_cap_usd)

    @app.post("/runs/{run_id}/runtime-configuration")
    def configure_runtime(run_id: str, req: RuntimeConfigurationRequest):
        result = Orchestrator(req.repo_path).configure_runtime(
            run_id,
            dict(req.values),
            dict(req.existing_references),
            req.region,
        )
        if result.get("status") == "ready":
            get_h_session_manager().schedule(
                req.repo_path,
                run_id,
                "approved-deployment",
                lambda: Orchestrator(req.repo_path).resume_approved_deployment(run_id),
            )
        return result

    @app.post("/runs/{run_id}/h-inspect")
    def h_inspect(run_id: str, req: HTaskRequest):
        status = Orchestrator(req.repo_path).get_status(run_id)
        if status["status"] == "waiting_for_login":
            return {"status": "blocked", "summary": "Manual cloud login is required before H CUA can run."}
        if status["status"] == "paused":
            return {"status": "skipped", "summary": "Run is paused."}
        return get_h_session_manager().schedule(
            req.repo_path,
            run_id,
            "inspect",
            lambda: Orchestrator(req.repo_path).run_h_inspect(run_id, req.task),
        )

    @app.post("/runs/{run_id}/aws-deploy")
    def aws_deploy(run_id: str, req: AWSDeploymentTaskRequest):
        orchestrator = Orchestrator(req.repo_path)
        approved = any(
            item.get("status") == "approved" and item.get("action", "").startswith("Run AWS deployment task:")
            for item in orchestrator.list_approvals(run_id)
        )
        if approved:
            return get_h_session_manager().schedule(
                req.repo_path,
                run_id,
                "aws-deployment-retry",
                lambda: Orchestrator(req.repo_path).run_aws_deployment_task(run_id, req.task, req.target, req.max_spend_usd),
            )
        return orchestrator.run_aws_deployment_task(run_id, req.task, req.target, req.max_spend_usd)

    @app.get("/runs/{run_id}/aws-plan")
    def aws_plan(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_aws_plan(run_id)

    @app.get("/runs/{run_id}/gcp-plan")
    def gcp_plan(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_gcp_plan(run_id)

    @app.post("/runs/{run_id}/gcp-deploy")
    def gcp_deploy(run_id: str, req: GCPDeploymentTaskRequest):
        return Orchestrator(req.repo_path).run_gcp_deployment_task(run_id, req.task)

    @app.post("/h-cleanup")
    def h_cleanup(req: RepoRunRequest):
        return Orchestrator(req.repo_path).cleanup_h_sessions()

    @app.post("/aws-cleanup")
    def aws_cleanup(req: CleanupRequest):
        return Orchestrator(req.repo_path).cleanup_aws_resources(req.run_id, req.dry_run)

    @app.get("/runs/{run_id}/approvals")
    def approvals(run_id: str, repo_path: str):
        return Orchestrator(repo_path).list_approvals(run_id)

    @app.post("/runs/{run_id}/approvals")
    def request_approval(run_id: str, req: ApprovalRequest):
        return Orchestrator(req.repo_path).request_approval(run_id, req.action, req.reason, req.risk_level)

    @app.post("/runs/{run_id}/approval-decision")
    def approval_decision(run_id: str, req: ApprovalDecisionRequest, background_tasks: BackgroundTasks):
        orchestrator = Orchestrator(req.repo_path)
        approval = orchestrator.decide_approval(run_id, req.approval_id, req.approved)
        if req.approved and (approval["action"].startswith("Run AWS deployment task:") or approval["action"] == "Run GCP Cloud Run deployment task"):
            get_h_session_manager().schedule(
                req.repo_path,
                run_id,
                "approved-deployment",
                lambda: Orchestrator(req.repo_path).resume_approved_deployment(run_id),
            )
        elif req.approved and approval["action"].startswith("Extend Cloud CUA cost policy to $"):
            new_cap = float(approval["action"].rsplit("$", 1)[1])
            approval["cost_policy"] = orchestrator.request_cost_extension(run_id, new_cap)
        return approval

    @app.post("/runs/{run_id}/resume-approved")
    def resume_approved(run_id: str, req: RepoRunRequest, background_tasks: BackgroundTasks):
        return get_h_session_manager().schedule(
            req.repo_path,
            run_id,
            "approved-deployment",
            lambda: Orchestrator(req.repo_path).resume_approved_deployment(run_id),
        )

    @app.post("/runs/{run_id}/voice")
    def voice(run_id: str, req: VoiceRequest):
        return Orchestrator(req.repo_path).voice_command(run_id, req.text)

    @app.websocket("/runs/{run_id}/voice-stream")
    async def voice_stream(websocket: WebSocket, run_id: str, repo_path: str):
        await handle_voice_stream(websocket, repo_path, run_id, service_token)

    @app.get("/runs/{run_id}/voice-status")
    def voice_status(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_voice_status(run_id)

    @app.post("/runs/{run_id}/voice-cancel-codex")
    def voice_cancel_codex(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).cancel_codex_voice(run_id)

    @app.post("/runs/{run_id}/voice-transcribe")
    def voice_transcribe(run_id: str, req: VoiceAudioRequest):
        return Orchestrator(req.repo_path).transcribe_voice(run_id, req.audio_base64, req.input_format)

    @app.post("/runs/{run_id}/speak")
    def speak(run_id: str, req: VoiceRequest):
        return Orchestrator(req.repo_path).speak(run_id, req.text)

    @app.post("/runs/{run_id}/codex-plan")
    def codex_plan(run_id: str, req: CodexMessageRequest):
        return Orchestrator(req.repo_path).submit_codex_plan(run_id, req.message)

    @app.post("/runs/{run_id}/codex-objection")
    def codex_objection(run_id: str, req: CodexMessageRequest):
        return Orchestrator(req.repo_path).submit_objection(run_id, req.message)

    @app.post("/runs/{run_id}/verify")
    def verify(run_id: str, req: VerifierRequest):
        return Orchestrator(req.repo_path).run_verifier(run_id, req.verifier_name, req.url)

    @app.post("/runs/{run_id}/report")
    def report(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).write_report(run_id)

    return app


app = create_app()
