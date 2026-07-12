from __future__ import annotations

from dataclasses import dataclass, asdict
import logging
from typing import Any

import httpx

from .credentials import load_secret_values

H_BASE_URL = "https://agp.eu.hcompany.ai"
NON_TERMINAL = {"queued", "pending", "running", "paused", "idle", "awaiting_tool_results"}
logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass(frozen=True)
class HQuota:
    limit: int | None
    active: int | None
    available: int | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class HCleanupResult:
    status: str
    before: HQuota | None
    after: HQuota | None
    deleted_trajectory_ids: list[str]
    cancelled_session_ids: list[str]
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


def get_h_quota(repo_path: str | None = None) -> HQuota | None:
    api_key = load_secret_values(repo_path).get("HAI_API_KEY")
    if not api_key:
        return None
    with httpx.Client(base_url=H_BASE_URL, headers=_headers(api_key), timeout=20, follow_redirects=True) as client:
        resp = client.get("/api/v2/sessions/quota")
        resp.raise_for_status()
        data = resp.json()
    return HQuota(data.get("limit"), data.get("active"), data.get("available"))


def cleanup_h_sessions(repo_path: str | None = None) -> HCleanupResult:
    api_key = load_secret_values(repo_path).get("HAI_API_KEY")
    if not api_key:
        return HCleanupResult("skipped", None, None, [], [], "HAI_API_KEY is not configured.")

    deleted: list[str] = []
    cancelled: list[str] = []
    with httpx.Client(base_url=H_BASE_URL, headers=_headers(api_key), timeout=20, follow_redirects=True) as client:
        before = _quota(client)
        sessions = client.get("/api/v2/sessions", params={"size": 50})
        sessions.raise_for_status()
        cloud_cua_ids: set[str] = set()
        bridge_ids: set[str] = set()
        for item in sessions.json().get("items", []):
            sid = item.get("id")
            if not sid:
                continue
            detail = client.get(f"/api/v2/sessions/{sid}")
            full = detail.json() if detail.status_code == 200 else item
            if _session_agent_name(full) != "cloud-cua-local-browser":
                continue
            cloud_cua_ids.add(sid)
            bridge_ids.update(_session_bridge_ids(full))
            status = _session_status(full) or str(item.get("status") or "")
            if status in NON_TERMINAL and _delete_ok(client, f"/api/v2/sessions/{sid}"):
                cancelled.append(sid)

        trajectories = client.get("/api/v1/trajectories/")
        trajectories.raise_for_status()
        for item in trajectories.json().get("items", []):
            if item.get("status") in NON_TERMINAL and item.get("id") in (cloud_cua_ids | bridge_ids):
                tid = item.get("id")
                if tid and _delete_ok(client, f"/api/v1/trajectories/{tid}"):
                    deleted.append(tid)
        after = _quota(client)

    return HCleanupResult(
        "passed",
        before,
        after,
        deleted,
        cancelled,
        f"Cleaned {len(cancelled)} sessions and {len(deleted)} local browser bridge trajectories.",
    )


def cleanup_h_session(session_id: str, repo_path: str | None = None) -> HCleanupResult:
    """Stop one Cloud CUA session and its matching local-browser trajectory."""
    api_key = load_secret_values(repo_path).get("HAI_API_KEY")
    if not api_key:
        return HCleanupResult("skipped", None, None, [], [], "HAI_API_KEY is not configured.")
    deleted: list[str] = []
    cancelled: list[str] = []
    with httpx.Client(base_url=H_BASE_URL, headers=_headers(api_key), timeout=20, follow_redirects=True) as client:
        before = _quota(client)
        session = client.get(f"/api/v2/sessions/{session_id}")
        if session.status_code == 200:
            item = session.json()
            if _session_agent_name(item) != "cloud-cua-local-browser":
                return HCleanupResult("failed", before, before, [], [], "Refused to clean a session not owned by Cloud CUA.")
            if _session_status(item) in NON_TERMINAL and _delete_ok(client, f"/api/v2/sessions/{session_id}"):
                cancelled.append(session_id)
            bridge_ids = _session_bridge_ids(item) | {session_id}
        else:
            bridge_ids = {session_id}
        for bridge_id in bridge_ids:
            if _delete_ok(client, f"/api/v1/trajectories/{bridge_id}", allow_not_found=True):
                deleted.append(bridge_id)
        after = _quota(client)
    return HCleanupResult(
        "passed",
        before,
        after,
        deleted,
        cancelled,
        f"Cleaned Cloud CUA session {session_id} and its local browser trajectory.",
    )


def _quota(client: httpx.Client) -> HQuota:
    resp = client.get("/api/v2/sessions/quota")
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    return HQuota(data.get("limit"), data.get("active"), data.get("available"))


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json", "Content-Type": "application/json"}


def _delete_ok(client: httpx.Client, path: str, *, allow_not_found: bool = False) -> bool:
    status = client.delete(path).status_code
    return status in {200, 202, 204} or (allow_not_found and status == 404)


def _session_agent_name(item: dict) -> str:
    agent = item.get("agent")
    if isinstance(agent, str):
        return agent
    if isinstance(agent, dict) and agent.get("name"):
        return str(agent["name"])
    request = item.get("request") if isinstance(item.get("request"), dict) else {}
    inline_agent = request.get("agent") if isinstance(request.get("agent"), dict) else {}
    return str(inline_agent.get("name") or "")


def _session_status(item: dict) -> str:
    status = item.get("status")
    if isinstance(status, str):
        return status
    if isinstance(status, dict):
        return str(status.get("status") or "")
    return ""


def _session_bridge_ids(item: dict) -> set[str]:
    request = item.get("request") if isinstance(item.get("request"), dict) else {}
    agent = request.get("agent") if isinstance(request.get("agent"), dict) else {}
    environments = agent.get("environments") if isinstance(agent.get("environments"), list) else []
    return {
        str(environment.get("session_id"))
        for environment in environments
        if isinstance(environment, dict) and environment.get("session_id")
    }
