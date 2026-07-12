from __future__ import annotations

import json

from cloud_cua.mcp_server import (
    cloud_cua_get_recent_events,
    cloud_cua_get_status,
    cloud_cua_run_amplify_deployment,
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
    blocked = cloud_cua_run_amplify_deployment(str(tmp_path), run["run_id"])
    events = cloud_cua_get_recent_events(str(tmp_path), run["run_id"])

    assert run["target"] == "aws_amplify"
    assert changed["mode"] == "expert"
    assert status["mode"] == "expert"
    assert blocked["status"] == "blocked"
    assert any(event["source"] == "system" for event in events)
