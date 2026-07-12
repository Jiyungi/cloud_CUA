from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from cloud_cua.server import create_app

from cloud_cua.mcp_server import (
    cloud_cua_get_aws_plan,
    cloud_cua_get_gcp_plan,
    cloud_cua_get_recent_events,
    cloud_cua_get_skill_status,
    cloud_cua_get_status,
    cloud_cua_run_aws_deployment_task,
    cloud_cua_run_gcp_cloud_run_task,
    cloud_cua_set_mode,
    cloud_cua_start_deployment,
    cloud_cua_sync_h_skills,
)


class InProcessClient:
    def __init__(self):
        self.client = TestClient(create_app())

    def get(self, path, params=None):
        response = self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, path, payload=None, timeout=35):
        response = self.client.post(path, json=payload or {})
        response.raise_for_status()
        return response.json()

    def open_dashboard(self, repo_path, run_id, open_browser=True):
        return {
            "dashboard_url": f"http://127.0.0.1:3000/?repo_path={repo_path}&run_id={run_id}",
            "launch_url": f"http://127.0.0.1:3000/?repo_path={repo_path}&run_id={run_id}&launch_token=test",
            "repo_path": repo_path,
            "run_id": run_id,
            "opened": False,
        }


@pytest.fixture(autouse=True)
def in_process_mcp(monkeypatch):
    client = InProcessClient()
    monkeypatch.setattr("cloud_cua.mcp_server._client", lambda: client)
    return client


def test_mcp_tools_share_orchestrator_flow(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build"}, "dependencies": {"vite": "^5.0.0"}}),
        encoding="utf-8",
    )

    run = cloud_cua_start_deployment(str(tmp_path), "aws", "vibe")
    changed = cloud_cua_set_mode(str(tmp_path), run["run_id"], "expert")
    status = cloud_cua_get_status(str(tmp_path), run["run_id"])
    aws_plan = cloud_cua_get_aws_plan(str(tmp_path), run["run_id"])
    aws_blocked = cloud_cua_run_aws_deployment_task(str(tmp_path), run["run_id"], "Deploy safely", "aws_amplify", 5)
    events = cloud_cua_get_recent_events(str(tmp_path), run["run_id"])

    assert run["target"] == "aws_amplify"
    assert "launch_token=" in run["launch_url"]
    assert changed["mode"] == "expert"
    assert status["mode"] == "expert"
    assert aws_plan["primary_target"] == "aws_amplify"
    assert aws_blocked["status"] == "blocked"
    assert any(event["source"] == "system" for event in events)


def test_mcp_gcp_tools(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM nginx:alpine\n", encoding="utf-8")
    run = cloud_cua_start_deployment(str(tmp_path), "gcp", "teach")
    plan = cloud_cua_get_gcp_plan(str(tmp_path), run["run_id"])
    blocked = cloud_cua_run_gcp_cloud_run_task(str(tmp_path), run["run_id"], "Deploy safely")

    assert plan["supported"] is True
    assert blocked["status"] == "blocked"


def test_mcp_skill_tools(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "cloud_cua.orchestrator.get_h_skill_status",
        lambda *_args, **_kwargs: type("Report", (), {"to_dict": lambda self: {"status": "passed", "skills": [], "message": "ok", "dry_run": True}})(),
    )
    monkeypatch.setattr(
        "cloud_cua.orchestrator.sync_h_skills",
        lambda *_args, **_kwargs: type("Report", (), {"to_dict": lambda self: {"status": "passed", "skills": [], "message": "synced", "dry_run": False}})(),
    )
    status = cloud_cua_get_skill_status(str(tmp_path))
    synced = cloud_cua_sync_h_skills(str(tmp_path))
    assert status["status"] == "passed"
    assert len(status["skills"]) == 53
    assert synced["status"] == "passed"
