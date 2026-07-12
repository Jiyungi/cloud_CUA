from __future__ import annotations

import json

from cloud_cua.mcp_server import (
    cloud_cua_get_aws_plan,
    cloud_cua_get_gcp_plan,
    cloud_cua_get_recent_events,
    cloud_cua_get_status,
    cloud_cua_run_aws_deployment_task,
    cloud_cua_run_gcp_cloud_run_task,
    cloud_cua_set_mode,
    cloud_cua_start_deployment,
)


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
