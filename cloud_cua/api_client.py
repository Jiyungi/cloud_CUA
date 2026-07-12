from __future__ import annotations

import os
import webbrowser
from typing import Any
from urllib.parse import urlencode

import httpx

from .service_runtime import ServiceState, ensure_service


class CloudCUAClient:
    def __init__(self, state: ServiceState | None = None):
        self.state = state or ensure_service()

    def get(self, path: str, params: dict | None = None) -> Any:
        response = httpx.get(self.state.base_url + path, params=params, headers=self._headers(), timeout=35)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict | None = None, timeout: float = 35) -> Any:
        response = httpx.post(self.state.base_url + path, json=payload or {}, headers=self._headers(), timeout=timeout)
        response.raise_for_status()
        return response.json()

    def dashboard_url(self, repo_path: str, run_id: str) -> str:
        return f"{self.state.base_url}/?{urlencode({'repo_path': repo_path, 'run_id': run_id})}"

    def open_dashboard(self, repo_path: str, run_id: str, *, open_browser: bool = True) -> dict:
        launch = self.post(f"/dashboard-launch?{urlencode({'run_id': run_id})}", {"repo_path": repo_path})
        url = launch["dashboard_url"]
        opened = False
        if open_browser and os.environ.get("CLOUD_CUA_NO_BROWSER") != "1":
            opened = bool(webbrowser.open(launch["launch_url"]))
        return {"dashboard_url": url, "run_id": run_id, "repo_path": repo_path, "opened": opened}

    def _headers(self) -> dict[str, str]:
        return {"X-Cloud-CUA-Token": self.state.token}
