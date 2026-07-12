from __future__ import annotations

from fastapi.testclient import TestClient

from cloud_cua.run_store import RunStore
from cloud_cua.server import create_app
from cloud_cua.verifier.base import VerifierResult


def test_dashboard_health():
    client = TestClient(create_app())
    assert client.get("/health").json() == {"ok": True}
    page = client.get("/")
    assert page.status_code == 200
    assert "Log into AWS in this browser window. Click Continue when done." in page.text


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

    plan = client.get(f"/runs/{run['run_id']}/amplify-plan", params={"repo_path": str(tmp_path)})
    assert plan.status_code == 200
    assert plan.json()["supported"] is True

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


def test_amplify_deploy_requires_approval(tmp_path):
    client = TestClient(create_app())
    (tmp_path / "package.json").write_text('{"scripts":{"build":"vite build"},"dependencies":{"vite":"^5.0.0"}}', encoding="utf-8")
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "vibe"}).json()
    store = RunStore(tmp_path)
    saved = store.load_run(run["run_id"])
    saved.status = "running"
    saved.current_step = "login_confirmed"
    store.save_run(saved)

    result = client.post(f"/runs/{run['run_id']}/amplify-deploy", json={"repo_path": str(tmp_path)})

    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "blocked"
    assert body["approval"]["status"] == "pending"


def test_general_aws_deploy_requires_approval(tmp_path):
    client = TestClient(create_app())
    (tmp_path / "Dockerfile").write_text("FROM nginx:alpine\n", encoding="utf-8")
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "vibe"}).json()
    store = RunStore(tmp_path)
    saved = store.load_run(run["run_id"])
    saved.status = "running"
    saved.current_step = "login_confirmed"
    store.save_run(saved)

    plan = client.get(f"/runs/{run['run_id']}/aws-plan", params={"repo_path": str(tmp_path)})
    result = client.post(
        f"/runs/{run['run_id']}/aws-deploy",
        json={"repo_path": str(tmp_path), "task": "Deploy this safely", "target": "aws_app_runner", "max_spend_usd": 5},
    )

    assert plan.status_code == 200
    assert plan.json()["primary_target"] == "aws_app_runner"
    assert result.status_code == 200
    assert result.json()["status"] == "blocked"
    assert result.json()["approval"]["status"] == "pending"
    assert "paid_resources" in result.json()["approval"]["triggers"]


def test_general_aws_deploy_blocks_over_budget(tmp_path):
    client = TestClient(create_app())
    (tmp_path / "Dockerfile").write_text("FROM nginx:alpine\n", encoding="utf-8")
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "vibe"}).json()
    store = RunStore(tmp_path)
    saved = store.load_run(run["run_id"])
    saved.status = "running"
    saved.current_step = "login_confirmed"
    store.save_run(saved)

    result = client.post(
        f"/runs/{run['run_id']}/aws-deploy",
        json={"repo_path": str(tmp_path), "task": "Deploy this safely", "target": "aws_app_runner", "max_spend_usd": 25},
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
    assert "Run Amplify step" in page.text
    assert "Start mic" in page.text


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
