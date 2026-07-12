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
        for item in sessions.json().get("items", []):
            if item.get("status") in NON_TERMINAL:
                sid = item.get("id")
                if sid and client.delete(f"/api/v2/sessions/{sid}").status_code in {200, 202, 204}:
                    cancelled.append(sid)

        trajectories = client.get("/api/v1/trajectories/")
        trajectories.raise_for_status()
        for item in trajectories.json().get("items", []):
            if item.get("status") in NON_TERMINAL and item.get("agent") == "surferh":
                tid = item.get("id")
                if tid and client.delete(f"/api/v1/trajectories/{tid}").status_code in {200, 202, 204}:
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


def _quota(client: httpx.Client) -> HQuota:
    resp = client.get("/api/v2/sessions/quota")
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    return HQuota(data.get("limit"), data.get("active"), data.get("available"))


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json", "Content-Type": "application/json"}
