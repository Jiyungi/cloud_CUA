from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .dashboard import render_dashboard
from .orchestrator import Orchestrator


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


def create_app() -> FastAPI:
    app = FastAPI(title="Cloud CUA")

    @app.get("/health")
    def health():
        return {"ok": True}

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

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return render_dashboard()

    @app.post("/runs")
    def start_run(req: StartRequest):
        return Orchestrator(req.repo_path).start_deployment(req.cloud, req.mode)

    @app.get("/runs")
    def list_runs(repo_path: str):
        return Orchestrator(repo_path).list_runs()

    @app.get("/runs/{run_id}")
    def get_run(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_status(run_id)

    @app.get("/runs/{run_id}/events")
    def get_events(run_id: str, repo_path: str, limit: int = 100):
        return Orchestrator(repo_path).get_events(run_id, limit)

    @app.get("/runs/{run_id}/lesson")
    def get_lesson(run_id: str, repo_path: str):
        return Orchestrator(repo_path).get_lesson_candidate(run_id)

    @app.post("/runs/{run_id}/mode")
    def set_mode(run_id: str, req: ModeRequest):
        return Orchestrator(req.repo_path).set_mode(run_id, req.mode)

    @app.post("/runs/{run_id}/open-browser")
    def open_browser(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).open_browser_for_login(run_id)

    @app.post("/runs/{run_id}/continue-login")
    def continue_login(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).continue_after_login(run_id)

    @app.post("/runs/{run_id}/pause")
    def pause(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).pause(run_id)

    @app.post("/runs/{run_id}/resume")
    def resume(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).resume(run_id)

    @app.post("/runs/{run_id}/h-inspect")
    def h_inspect(run_id: str, req: HTaskRequest):
        return Orchestrator(req.repo_path).run_h_inspect(run_id, req.task)

    @app.post("/runs/{run_id}/aws-deploy")
    def aws_deploy(run_id: str, req: AWSDeploymentTaskRequest):
        return Orchestrator(req.repo_path).run_aws_deployment_task(run_id, req.task, req.target, req.max_spend_usd)

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
        approval = Orchestrator(req.repo_path).decide_approval(run_id, req.approval_id, req.approved)
        if req.approved:
            background_tasks.add_task(Orchestrator(req.repo_path).resume_approved_deployment, run_id)
        return approval

    @app.post("/runs/{run_id}/resume-approved")
    def resume_approved(run_id: str, req: RepoRunRequest, background_tasks: BackgroundTasks):
        background_tasks.add_task(Orchestrator(req.repo_path).resume_approved_deployment, run_id)
        return {"status": "scheduled", "summary": "Approved deployment gate resume was scheduled."}

    @app.post("/runs/{run_id}/voice")
    def voice(run_id: str, req: VoiceRequest):
        return Orchestrator(req.repo_path).voice_command(run_id, req.text)

    @app.post("/runs/{run_id}/voice-transcribe")
    def voice_transcribe(run_id: str, req: VoiceAudioRequest):
        return Orchestrator(req.repo_path).transcribe_voice(run_id, req.audio_base64, req.input_format)

    @app.post("/runs/{run_id}/speak")
    def speak(run_id: str, req: VoiceRequest):
        return Orchestrator(req.repo_path).speak(run_id, req.text)

    @app.post("/runs/{run_id}/verify")
    def verify(run_id: str, req: VerifierRequest):
        return Orchestrator(req.repo_path).run_verifier(run_id, req.verifier_name, req.url)

    @app.post("/runs/{run_id}/report")
    def report(run_id: str, req: RepoRunRequest):
        return Orchestrator(req.repo_path).write_report(run_id)

    return app


app = create_app()
