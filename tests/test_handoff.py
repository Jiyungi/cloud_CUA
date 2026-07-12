from __future__ import annotations

import json
from cloud_cua.approvals import Approval
from cloud_cua.handoff import build_handoff_state, save_handoff
from cloud_cua.models import Run


def run(status: str = "running", step: str = "login_verified") -> Run:
    return Run("run-1", "C:/repo", "aws", "vibe", target="aws_ecs_express", status=status, current_step=step)


def test_handoff_routes_login_and_approval_to_user():
    login = build_handoff_state(run("waiting_for_login"), events=[], approvals=[], pending_actions=[], h_job=None, codex_job=None, contract=None)
    approval = build_handoff_state(
        run("blocked", "approval_required"),
        events=[],
        approvals=[Approval("a1", "Create service", "cost", "high", "pending", [])],
        pending_actions=[],
        h_job=None,
        codex_job=None,
        contract=None,
    )

    assert (login["owner"], login["state"]) == ("user", "manual_login_required")
    assert (approval["owner"], approval["state"]) == ("user", "approval_required")
    assert "Create service" in approval["next_action"]


def test_handoff_routes_active_h_and_codex_jobs():
    codex = build_handoff_state(
        run(), events=[], approvals=[], pending_actions=[], h_job=None, codex_job={"status": "running", "question": "Deploy"}, contract=None
    )
    h_cua = build_handoff_state(
        run(),
        events=[],
        approvals=[],
        pending_actions=[],
        h_job={"status": "running", "milestone": "inspect_form", "session_id": "s1"},
        codex_job=None,
        contract=None,
    )

    assert (codex["owner"], codex["state"]) == ("codex", "codex_reasoning")
    assert (h_cua["owner"], h_cua["state"]) == ("h_cua", "h_operating")
    assert "inspect_form" in h_cua["next_action"]


def test_handoff_preserves_latest_evidence_and_saves_atomically(tmp_path):
    state = build_handoff_state(
        run("blocked", "h_cua_rate_limited"),
        events=[{"time": "now", "source": "h_cua", "type": "observation", "message": "H returned HTTP 429.", "evidence": {"status": "blocked"}}],
        approvals=[],
        pending_actions=[],
        h_job={"status": "completed", "result": {"status": "blocked"}},
        codex_job=None,
        contract={"skill_name": "cloud-cua/aws-ecs-express", "container_port": 3000, "secret_value": "not-retained"},
    )
    path = save_handoff(tmp_path / "handoff.json", state)
    stored = json.loads(path.read_text(encoding="utf-8"))

    assert stored["owner"] == "codex"
    assert stored["latest"]["h_cua"]["message"] == "H returned HTTP 429."
    assert stored["contract"]["container_port"] == 3000
    assert "secret_value" not in stored["contract"]
