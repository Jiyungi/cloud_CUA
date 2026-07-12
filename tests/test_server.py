from __future__ import annotations

from fastapi.testclient import TestClient

from cloud_cua.container_image import ContainerImagePrepResult
from cloud_cua.h_runner import HTaskResult
from cloud_cua.run_store import RunStore
from cloud_cua.server import create_app
from cloud_cua.verifier.base import VerifierResult


def test_dashboard_health():
    client = TestClient(create_app())
    assert client.get("/health").json() == {"ok": True, "service": "cloud-cua"}
    page = client.get("/")
    assert page.status_code == 200
    assert "Log into AWS in this browser window. Click Continue when done." in page.text


def test_skill_api_lists_and_syncs(tmp_path, monkeypatch):
    report = {"status": "passed", "dry_run": False, "skills": [], "message": "synced"}
    monkeypatch.setattr("cloud_cua.orchestrator.Orchestrator.get_skill_status", lambda self: {**report, "skills": [{"name": "cloud-cua/aws-ecs-express"}]})
    monkeypatch.setattr("cloud_cua.orchestrator.Orchestrator.sync_h_skills", lambda self, names=None, dry_run=False: report)
    client = TestClient(create_app())
    listed = client.get("/skills", params={"repo_path": str(tmp_path)})
    synced = client.post("/skills/sync", json={"repo_path": str(tmp_path), "dry_run": False})
    assert listed.json()["skills"][0]["name"] == "cloud-cua/aws-ecs-express"
    assert synced.json()["status"] == "passed"


def test_start_mode_voice_report_flow(tmp_path):
    client = TestClient(create_app())
    (tmp_path / "package.json").write_text('{"scripts":{"build":"vite build"},"dependencies":{"vite":"^5.0.0"}}', encoding="utf-8")
    started = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "vibe"})
    assert started.status_code == 200
    run = started.json()
    assert run["target"] == "aws_amplify"

    changed = client.post(f"/runs/{run['run_id']}/mode", json={"repo_path": str(tmp_path), "mode": "teach"})
    assert changed.status_code == 200
    assert changed.json()["mode"] == "teach"

    routed = client.post(f"/runs/{run['run_id']}/voice", json={"repo_path": str(tmp_path), "text": "pause"})
    assert routed.status_code == 200
    assert routed.json()["classification"] == "direct_control"

    plan = client.get(f"/runs/{run['run_id']}/aws-plan", params={"repo_path": str(tmp_path)})
    assert plan.status_code == 200
    assert plan.json()["primary_target"] == "aws_amplify"

    caps = client.get("/capabilities", params={"repo_path": str(tmp_path)})
    assert caps.status_code == 200
    assert "gradium_api_key_present" in caps.json()

    approval = client.post(
        f"/runs/{run['run_id']}/approvals",
        json={"repo_path": str(tmp_path), "action": "Create AWS Amplify app", "reason": "Creates a cloud resource."},
    )
    assert approval.status_code == 200
    assert approval.json()["status"] == "pending"

    report = client.post(f"/runs/{run['run_id']}/report", json={"repo_path": str(tmp_path)})
    assert report.status_code == 200
    assert (tmp_path / "DEPLOYMENT_REPORT.md").exists()


def test_voice_transcribe_logs_transcript_and_route(tmp_path, monkeypatch):
    from cloud_cua.voice_gradium import STTResult

    client = TestClient(create_app())
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "teach"}).json()
    monkeypatch.setattr(
        "cloud_cua.orchestrator.transcribe_stt",
        lambda *args, **kwargs: STTResult("passed", "pause", "Transcribed audio."),
    )

    result = client.post(
        f"/runs/{run['run_id']}/voice-transcribe",
        json={"repo_path": str(tmp_path), "audio_base64": "cGF1c2U=", "input_format": "webm"},
    )

    assert result.status_code == 200
    events = client.get(f"/runs/{run['run_id']}/events", params={"repo_path": str(tmp_path), "limit": 20}).json()
    messages = [event["message"] for event in events]
    assert "Gradium STT heard: pause" in messages
    assert "STT routed to backend as direct_control." in messages


def test_frontend_aws_deploy_requires_approval(tmp_path):
    client = TestClient(create_app())
    (tmp_path / "package.json").write_text('{"scripts":{"build":"vite build"},"dependencies":{"vite":"^5.0.0"}}', encoding="utf-8")
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "vibe"}).json()
    store = RunStore(tmp_path)
    saved = store.load_run(run["run_id"])
    saved.status = "running"
    saved.current_step = "login_confirmed"
    store.save_run(saved)

    result = client.post(
        f"/runs/{run['run_id']}/aws-deploy",
        json={"repo_path": str(tmp_path), "target": "aws_amplify", "max_spend_usd": 5},
    )

    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "blocked"
    assert body["approval"]["status"] == "pending"


def test_general_aws_deploy_requires_approval(tmp_path, monkeypatch):
    client = TestClient(create_app())
    (tmp_path / "Dockerfile").write_text("FROM nginx:alpine\nEXPOSE 80\n", encoding="utf-8")
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "vibe"}).json()
    store = RunStore(tmp_path)
    saved = store.load_run(run["run_id"])
    saved.status = "running"
    saved.current_step = "login_confirmed"
    store.save_run(saved)

    plan = client.get(f"/runs/{run['run_id']}/aws-plan", params={"repo_path": str(tmp_path)})
    result = client.post(
        f"/runs/{run['run_id']}/aws-deploy",
        json={"repo_path": str(tmp_path), "task": "Deploy this safely", "target": "aws_ecs_express", "max_spend_usd": 5},
    )

    assert plan.status_code == 200
    assert plan.json()["primary_target"] == "aws_ecs_express"
    assert result.status_code == 200
    assert result.json()["status"] == "blocked"
    assert result.json()["approval"]["status"] == "pending"
    assert "paid_resources" in result.json()["approval"]["triggers"]

    monkeypatch.setattr(
        "cloud_cua.orchestrator.run_h_task",
        lambda *args, **kwargs: HTaskResult("blocked", "fake H handoff stopped for test"),
    )
    monkeypatch.setattr(
        "cloud_cua.orchestrator.prepare_ecr_image_with_progress",
        lambda *args, **kwargs: ContainerImagePrepResult(
            "passed",
            "fake image prepared",
            image_uri="123456789012.dkr.ecr.us-east-1.amazonaws.com/cloud-cua-demo:run-test",
            repository_name="cloud-cua-demo",
            registry="123456789012.dkr.ecr.us-east-1.amazonaws.com",
        ),
    )
    monkeypatch.setattr(
        "cloud_cua.orchestrator.sync_h_skills",
        lambda *args, **kwargs: type("Report", (), {"status": "passed", "message": "synced", "to_dict": lambda self: {"status": "passed", "skills": []}})(),
    )
    approved = client.post(
        f"/runs/{run['run_id']}/approval-decision",
        json={"repo_path": str(tmp_path), "approval_id": result.json()["approval"]["approval_id"], "approved": True},
    )
    assert approved.status_code == 200
    status = client.get(f"/runs/{run['run_id']}", params={"repo_path": str(tmp_path)}).json()
    assert status["status"] == "blocked"
    assert status["current_step"] == "ecs_form_contract_mismatch"
    assert (store.run_dir(run["run_id"]) / "contract.json").exists()
    lesson = client.get(f"/runs/{run['run_id']}/lesson", params={"repo_path": str(tmp_path)}).json()
    assert lesson["status"] == "pending_review"
    assert lesson["affected_skill"] == "cloud-cua/aws-ecs-express"
    events = client.get(f"/runs/{run['run_id']}/events", params={"repo_path": str(tmp_path)}).json()
    assert any(event["source"] == "h_cua" and event["type"] == "milestone" for event in events)


def test_aws_deploy_does_not_start_duplicate_work(tmp_path):
    client = TestClient(create_app())
    (tmp_path / "Dockerfile").write_text("FROM nginx:alpine\n", encoding="utf-8")
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "vibe"}).json()
    store = RunStore(tmp_path)
    saved = store.load_run(run["run_id"])
    saved.status = "running"
    saved.current_step = "container_image_pushing"
    store.save_run(saved)

    result = client.post(
        f"/runs/{run['run_id']}/aws-deploy",
        json={"repo_path": str(tmp_path), "target": "aws_ecs_express", "max_spend_usd": 5},
    )

    assert result.status_code == 200
    assert result.json()["status"] == "running"
    assert result.json()["current_step"] == "container_image_pushing"


def test_general_aws_deploy_blocks_over_budget(tmp_path):
    client = TestClient(create_app())
    (tmp_path / "Dockerfile").write_text("FROM nginx:alpine\nEXPOSE 80\n", encoding="utf-8")
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "vibe"}).json()
    store = RunStore(tmp_path)
    saved = store.load_run(run["run_id"])
    saved.status = "running"
    saved.current_step = "login_confirmed"
    store.save_run(saved)

    result = client.post(
        f"/runs/{run['run_id']}/aws-deploy",
        json={"repo_path": str(tmp_path), "task": "Deploy this safely", "target": "aws_ecs_express", "max_spend_usd": 25},
    )

    assert result.json()["status"] == "blocked"
    assert "$25.00" in result.json()["summary"]


def test_login_gate_blocks_h_until_continue(tmp_path, monkeypatch):
    client = TestClient(create_app())
    (tmp_path / "package.json").write_text('{"scripts":{"build":"vite build"},"dependencies":{"vite":"^5.0.0"}}', encoding="utf-8")
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "vibe"}).json()

    blocked = client.post(
        f"/runs/{run['run_id']}/h-inspect",
        json={"repo_path": str(tmp_path), "task": "inspect only"},
    )
    assert blocked.json()["status"] == "blocked"
    assert "login" in blocked.json()["summary"].lower()

    monkeypatch.setattr(
        "cloud_cua.orchestrator.verify_aws_identity",
        lambda: VerifierResult("aws_identity", "failed", "aws sts get-caller-identity", "not authenticated"),
    )
    continued = client.post(f"/runs/{run['run_id']}/continue-login", json={"repo_path": str(tmp_path)})
    assert continued.json()["status"] == "blocked"
    assert continued.json()["current_step"] == "identity_verifier_failed"


def test_dashboard_contains_supervision_sections():
    client = TestClient(create_app())
    page = client.get("/")
    assert "Control Loop" in page.text
    assert "Approvals" in page.text
    assert "Run Amplify step" not in page.text
    assert "Deploy" in page.text
    assert "Start mic" in page.text
    assert "Skills" in page.text
    assert "Sync H skills" in page.text
    assert "Lesson awaiting review" in page.text


def test_gcp_cloud_run_deploy_requires_approval(tmp_path):
    client = TestClient(create_app())
    (tmp_path / "Dockerfile").write_text("FROM nginx:alpine\n", encoding="utf-8")
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "gcp", "mode": "teach"}).json()
    store = RunStore(tmp_path)
    saved = store.load_run(run["run_id"])
    saved.status = "running"
    saved.current_step = "login_confirmed"
    store.save_run(saved)

    plan = client.get(f"/runs/{run['run_id']}/gcp-plan", params={"repo_path": str(tmp_path)})
    result = client.post(
        f"/runs/{run['run_id']}/gcp-deploy",
        json={"repo_path": str(tmp_path), "task": "Deploy this safely to Cloud Run"},
    )

    assert plan.status_code == 200
    assert plan.json()["supported"] is True
    assert result.status_code == 200
    assert result.json()["status"] == "blocked"
    assert result.json()["approval"]["status"] == "pending"
