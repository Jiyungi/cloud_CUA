from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .api_client import CloudCUAClient

mcp = FastMCP("cloud-cua")


def _client() -> CloudCUAClient:
    return CloudCUAClient()


@mcp.tool()
def cloud_cua_start_deployment(
    repo_path: str,
    cloud: str = "aws",
    mode: str = "vibe",
    deployment_scope: str = "auto",
) -> Any:
    """Start a deployment and open its dashboard. Fixture repos default to an honest frontend preview."""
    client = _client()
    run = client.post(
        "/runs",
        {"repo_path": repo_path, "cloud": cloud, "mode": mode, "deployment_scope": deployment_scope},
    )
    dashboard = client.open_dashboard(repo_path, run["run_id"])
    run = client.post(
        f"/runs/{run['run_id']}/dashboard",
        {"repo_path": repo_path, "dashboard_url": dashboard["dashboard_url"]},
    )
    return {**run, **dashboard}


@mcp.tool()
def cloud_cua_get_status(repo_path: str, run_id: str) -> Any:
    """Get current run status from the shared backend."""
    return _client().get(f"/runs/{run_id}", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_get_recent_events(repo_path: str, run_id: str, limit: int = 50) -> Any:
    """Get recent structured events from the shared backend."""
    return _client().get(f"/runs/{run_id}/events", {"repo_path": repo_path, "limit": limit})


@mcp.tool()
def cloud_cua_get_handoff(repo_path: str, run_id: str) -> Any:
    """Get the shared Codex-H-user-verifier owner, milestone, evidence, and exact next action."""
    return _client().get(f"/runs/{run_id}/handoff", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_watch_run(repo_path: str, run_id: str, cursor: int = 0, timeout_seconds: int = 20) -> Any:
    """Long-poll the shared run so Codex can supervise new H, user, and verifier events."""
    return _client().get(
        f"/runs/{run_id}/watch",
        {"repo_path": repo_path, "cursor": cursor, "timeout_seconds": timeout_seconds},
    )


@mcp.tool()
def cloud_cua_get_pending_actions(repo_path: str, run_id: str) -> Any:
    """List voice/text cloud requests that require a Codex plan and user approval."""
    return _client().get(f"/runs/{run_id}/pending-actions", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_get_lesson_candidate(repo_path: str, run_id: str) -> Any:
    return _client().get(f"/runs/{run_id}/lesson", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_set_mode(repo_path: str, run_id: str, mode: str) -> Any:
    return _client().post(f"/runs/{run_id}/mode", {"repo_path": repo_path, "mode": mode})


@mcp.tool()
def cloud_cua_open_dashboard(repo_path: str, run_id: str, open_browser: bool = True) -> Any:
    """Open the dashboard attached to this exact repository and run."""
    client = _client()
    dashboard = client.open_dashboard(repo_path, run_id, open_browser=open_browser)
    client.post(f"/runs/{run_id}/dashboard", {"repo_path": repo_path, "dashboard_url": dashboard["dashboard_url"]})
    return dashboard


@mcp.tool()
def cloud_cua_confirm_manual_login(repo_path: str, run_id: str) -> Any:
    return _client().post(f"/runs/{run_id}/continue-login", {"repo_path": repo_path}, timeout=300)


@mcp.tool()
def cloud_cua_send_user_message(repo_path: str, run_id: str, message: str) -> Any:
    return _client().post(f"/runs/{run_id}/voice", {"repo_path": repo_path, "text": message})


@mcp.tool()
def cloud_cua_speak(repo_path: str, run_id: str, text: str) -> Any:
    return _client().post(f"/runs/{run_id}/speak", {"repo_path": repo_path, "text": text}, timeout=120)


@mcp.tool()
def cloud_cua_get_voice_status(repo_path: str, run_id: str) -> Any:
    """Get the active voice turn, transcript state, response, and read-only Codex voice job."""
    return _client().get(f"/runs/{run_id}/voice-status", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_get_pending_voice_question(repo_path: str, run_id: str) -> Any:
    """Return the concise clarification currently requested by the Codex voice worker, if any."""
    status = cloud_cua_get_voice_status(repo_path, run_id)
    job = status.get("codex_job") or {}
    return {
        "status": job.get("status", "idle"),
        "job_id": job.get("job_id"),
        "clarification_question": job.get("clarification_question", ""),
    }


@mcp.tool()
def cloud_cua_submit_voice_clarification(repo_path: str, run_id: str, answer: str) -> Any:
    """Submit a user's clarification through the same guarded voice/text router; never sends raw text directly to H."""
    return _client().post(f"/runs/{run_id}/voice", {"repo_path": repo_path, "text": answer}, timeout=120)


@mcp.tool()
def cloud_cua_stop_speech(repo_path: str, run_id: str) -> Any:
    """Tell the dashboard voice flow to stop speech without cancelling the deployment."""
    return _client().post(f"/runs/{run_id}/voice", {"repo_path": repo_path, "text": "stop speaking"})


@mcp.tool()
def cloud_cua_cancel_codex_voice(repo_path: str, run_id: str) -> Any:
    """Cancel only the active read-only Codex voice job."""
    return _client().post(f"/runs/{run_id}/voice-cancel-codex", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_submit_codex_plan(repo_path: str, run_id: str, plan: str) -> Any:
    return _client().post(f"/runs/{run_id}/codex-plan", {"repo_path": repo_path, "message": plan})


@mcp.tool()
def cloud_cua_submit_objection(repo_path: str, run_id: str, objection: str) -> Any:
    return _client().post(f"/runs/{run_id}/codex-objection", {"repo_path": repo_path, "message": objection})


@mcp.tool()
def cloud_cua_get_aws_plan(repo_path: str, run_id: str) -> Any:
    return _client().get(f"/runs/{run_id}/aws-plan", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_get_gcp_plan(repo_path: str, run_id: str) -> Any:
    return _client().get(f"/runs/{run_id}/gcp-plan", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_h_inspect(repo_path: str, run_id: str, task: str | None = None) -> Any:
    return _client().post(f"/runs/{run_id}/h-inspect", {"repo_path": repo_path, "task": task}, timeout=360)


@mcp.tool()
def cloud_cua_run_aws_deployment_task(
    repo_path: str,
    run_id: str,
    task: str | None = None,
    target: str | None = None,
    max_spend_usd: float = 5.0,
) -> Any:
    return _client().post(
        f"/runs/{run_id}/aws-deploy",
        {"repo_path": repo_path, "task": task, "target": target, "max_spend_usd": max_spend_usd},
        timeout=360,
    )


@mcp.tool()
def cloud_cua_run_gcp_cloud_run_task(repo_path: str, run_id: str, task: str | None = None) -> Any:
    return _client().post(f"/runs/{run_id}/gcp-deploy", {"repo_path": repo_path, "task": task}, timeout=360)


@mcp.tool()
def cloud_cua_cleanup_h_sessions(repo_path: str) -> Any:
    return _client().post("/h-cleanup", {"repo_path": repo_path}, timeout=120)


@mcp.tool()
def cloud_cua_get_skill_status(repo_path: str) -> Any:
    return _client().get("/skills", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_sync_h_skills(repo_path: str, names: list[str] | None = None, dry_run: bool = False) -> Any:
    return _client().post("/skills/sync", {"repo_path": repo_path, "names": names, "dry_run": dry_run}, timeout=120)


@mcp.tool()
def cloud_cua_cleanup_aws_resources(repo_path: str, run_id: str | None = None, dry_run: bool = True) -> Any:
    return _client().post("/aws-cleanup", {"repo_path": repo_path, "run_id": run_id, "dry_run": dry_run}, timeout=300)


@mcp.tool()
def cloud_cua_request_approval(repo_path: str, run_id: str, action: str, reason: str, risk_level: str = "medium") -> Any:
    return _client().post(
        f"/runs/{run_id}/approvals",
        {"repo_path": repo_path, "action": action, "reason": reason, "risk_level": risk_level},
    )


@mcp.tool()
def cloud_cua_decide_approval(repo_path: str, run_id: str, approval_id: str, approved: bool) -> Any:
    return _client().post(
        f"/runs/{run_id}/approval-decision",
        {"repo_path": repo_path, "approval_id": approval_id, "approved": approved},
    )


@mcp.tool()
def cloud_cua_pause_h_cua(repo_path: str, run_id: str) -> Any:
    return _client().post(f"/runs/{run_id}/pause", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_resume_h_cua(repo_path: str, run_id: str) -> Any:
    return _client().post(f"/runs/{run_id}/resume", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_cancel_h_cua(repo_path: str, run_id: str) -> Any:
    """Cancel the active H session and local worker without deleting cloud resources."""
    return _client().post(f"/runs/{run_id}/cancel", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_get_runtime_configuration_status(repo_path: str, run_id: str) -> Any:
    """Return missing runtime variable names and cloud references; secret values are never accepted through MCP."""
    return _client().get(f"/runs/{run_id}/runtime-configuration", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_get_cost_status(repo_path: str, run_id: str) -> Any:
    """Return live-price assumptions, accrued estimate, deadline, and cleanup gate state."""
    return _client().get(f"/runs/{run_id}/cost", {"repo_path": repo_path})


@mcp.tool()
def cloud_cua_run_verifier(repo_path: str, run_id: str, verifier_name: str = "default", url: str | None = None) -> Any:
    return _client().post(
        f"/runs/{run_id}/verify",
        {"repo_path": repo_path, "verifier_name": verifier_name, "url": url},
        timeout=300,
    )


@mcp.tool()
def cloud_cua_write_report(repo_path: str, run_id: str) -> Any:
    return _client().post(f"/runs/{run_id}/report", {"repo_path": repo_path})


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
