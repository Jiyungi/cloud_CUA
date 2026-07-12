from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import Run
from .run_store import now_iso, sanitize_obj


ACTIVE_CODEX_STATES = {"queued", "running"}
ACTIVE_H_STATES = {"queued", "running", "paused", "cancelling", "recovering"}


def build_handoff_state(
    run: Run,
    *,
    events: list[dict],
    approvals: list[Any],
    pending_actions: list[dict],
    h_job: dict | None,
    codex_job: Any | None,
    contract: dict | None,
) -> dict:
    pending_approvals = [
        asdict(item) if not isinstance(item, dict) else item
        for item in approvals
        if (item.get("status") if isinstance(item, dict) else item.status) == "pending"
    ]
    open_actions = [item for item in pending_actions if item.get("status") == "needs_plan_and_approval"]
    codex_data = asdict(codex_job) if codex_job and not isinstance(codex_job, dict) else codex_job
    h_data = h_job or None

    owner, state, next_action = _routing_state(run, pending_approvals, open_actions, h_data, codex_data)
    result = {
        "run_id": run.run_id,
        "repo_path": run.repo_path,
        "owner": owner,
        "state": state,
        "next_action": next_action,
        "current_step": run.current_step,
        "target": run.target,
        "contract": _contract_summary(contract),
        "pending_approvals": pending_approvals,
        "pending_actions": open_actions,
        "codex_job": codex_data,
        "h_job": h_data,
        "latest": {
            source: _latest_event(events, source)
            for source in ("codex", "h_cua", "user", "verifier", "system")
        },
        "updated_at": now_iso(),
    }
    return sanitize_obj(result)


def save_handoff(path: Path, state: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(sanitize_obj(state), indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def _routing_state(
    run: Run,
    pending_approvals: list[dict],
    pending_actions: list[dict],
    h_job: dict | None,
    codex_job: dict | None,
) -> tuple[str, str, str]:
    if run.status == "completed":
        return "none", "completed", "Review the verified URL, report, and cleanup state."
    if run.status == "cancelled":
        return "user", "cancelled", "Review whether any created cloud resources need cleanup."
    if run.status == "waiting_for_login":
        return "user", "manual_login_required", "Open the cloud login window, sign in, then confirm login."
    if run.status == "waiting_for_configuration":
        return "user", "runtime_configuration_required", "Provide the missing runtime configuration in the secure dashboard form."
    if run.status == "cost_action_required":
        return "user", "cost_action_required", "Choose cleanup or approve a higher cost limit before work continues."
    if pending_approvals:
        action = pending_approvals[0].get("action", "the pending action")
        return "user", "approval_required", f"Approve or reject: {action}."
    if codex_job and codex_job.get("status") in ACTIVE_CODEX_STATES:
        return "codex", "codex_reasoning", "Codex is answering or planning from repository and run evidence."
    if h_job and h_job.get("status") in ACTIVE_H_STATES:
        if h_job.get("status") == "paused":
            return "user", "h_paused", "Resume or cancel the paused H browser session."
        milestone = h_job.get("milestone") or h_job.get("operation") or "current milestone"
        return "h_cua", "h_operating", f"H is executing {milestone}; Codex will review its result before the next milestone."
    if pending_actions:
        return "codex", "plan_required", "Codex must turn the user's request into a bounded plan and approval gate."
    if run.status in {"blocked", "failed"}:
        return "codex", "replan_required", "Codex must inspect the blocker, preserve evidence, and propose the next safe action."
    if run.status == "verifying" or "verif" in run.current_step:
        return "verifier", "verification_running", "Independent checks must prove the exact resource and live application."
    return "codex", "planning", "Codex should prepare the next bounded H milestone from repository facts and verifier requirements."


def _contract_summary(contract: dict | None) -> dict | None:
    if not contract:
        return None
    fields = (
        "skill_name",
        "target",
        "cloud_region",
        "container_image_uri",
        "container_port",
        "health_path",
        "required_tags",
        "missing_facts",
        "expected_public_url",
    )
    return {key: contract.get(key) for key in fields if key in contract}


def _latest_event(events: list[dict], source: str) -> dict | None:
    for event in reversed(events):
        if event.get("source") == source:
            return {
                "time": event.get("time"),
                "type": event.get("type"),
                "message": event.get("message"),
                "evidence": event.get("evidence", {}),
            }
    return None
