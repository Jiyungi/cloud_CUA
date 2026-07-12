from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from .aws_costs import load_cost_policy, save_cost_policy
from .run_store import RunStore
from .paths import user_config_dir


class CostMonitor:
    def __init__(self, interval_seconds: float = 30.0, *, persist: bool = False, registry_path: Path | None = None):
        self.interval_seconds = interval_seconds
        self.persist = persist
        self.registry_path = registry_path or (user_config_dir() / "cost-runs.json")
        self._guard = threading.RLock()
        self._runs: set[tuple[str, str]] = set()
        self._thread: threading.Thread | None = None

    def register(self, repo_path: str | Path, run_id: str) -> None:
        store = RunStore(repo_path)
        with self._guard:
            self._runs.add((str(store.repo_path), run_id))
            self._save_registry()
            if not self._thread or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, daemon=True, name="cloud-cua-cost-monitor")
                self._thread.start()

    def unregister(self, repo_path: str | Path, run_id: str) -> None:
        store = RunStore(repo_path)
        with self._guard:
            self._runs.discard((str(store.repo_path), run_id))
            self._save_registry()

    def recover(self) -> None:
        if not self.persist:
            return
        with self._guard:
            try:
                items = json.loads(self.registry_path.read_text(encoding="utf-8"))
                self._runs.update((str(item["repo_path"]), str(item["run_id"])) for item in items)
            except (OSError, TypeError, KeyError, json.JSONDecodeError):
                pass
            if self._runs and (not self._thread or not self._thread.is_alive()):
                self._thread = threading.Thread(target=self._loop, daemon=True, name="cloud-cua-cost-monitor")
                self._thread.start()

    def evaluate(self, repo_path: str | Path, run_id: str) -> dict:
        store = RunStore(repo_path)
        path = store.run_dir(run_id) / "cost-policy.json"
        policy = load_cost_policy(path)
        if not policy:
            return {"status": "not_configured", "message": "No cost policy has been created for this run."}
        save_cost_policy(path, policy)
        marker = store.run_dir(run_id) / f"cost-warning-{policy.warning_level}.marker"
        if policy.warning_level and not marker.exists():
            marker.write_text(policy.updated_at, encoding="utf-8")
            message = (
                f"Estimated run cost reached {policy.warning_level}% of the ${policy.max_spend_usd:.2f} policy cap."
                if policy.warning_level < 100
                else f"Estimated run cost reached the ${policy.max_spend_usd:.2f} policy cap. Cleanup or an approved extension is required."
            )
            store.append_event(run_id, "system", "cost_warning", message, {"cost_policy": policy.to_dict()})
        if policy.warning_level >= 100:
            try:
                run = store.load_run(run_id)
                if run.status not in {"cancelled", "cost_action_required"}:
                    run.status = "cost_action_required"
                    run.current_step = "cleanup_or_cost_extension_required"
                    store.save_run(run)
            except Exception:
                pass
        return policy.to_dict()

    def _loop(self) -> None:
        while True:
            with self._guard:
                runs = list(self._runs)
            for repo_path, run_id in runs:
                try:
                    self.evaluate(repo_path, run_id)
                except Exception:
                    continue
            time.sleep(self.interval_seconds)

    def _save_registry(self) -> None:
        if not self.persist:
            return
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.registry_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([{"repo_path": repo_path, "run_id": run_id} for repo_path, run_id in sorted(self._runs)], indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.registry_path)


_MONITOR = CostMonitor(persist=bool(os.environ.get("CLOUD_CUA_SERVICE_TOKEN") or os.environ.get("CLOUD_CUA_CONTAINER") == "1"))


def get_cost_monitor() -> CostMonitor:
    return _MONITOR
