from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .credentials import load_secret_values
from .h_admin import cleanup_h_session
from .run_store import RunStore, now_iso, sanitize_obj


ACTIVE_JOB_STATES = {"queued", "running", "paused", "cancelling", "recovering"}
H_TERMINAL_STATES = {"completed", "failed", "timed_out", "interrupted"}


@dataclass
class HJob:
    job_id: str
    repo_path: str
    run_id: str
    operation: str
    status: str = "queued"
    milestone: str = "queued"
    worker_pid: int | None = None
    session_id: str | None = None
    event_cursor: int = 0
    heartbeat_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    error: str = ""
    result: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class HSessionManager:
    def __init__(self):
        self._guard = threading.RLock()
        self._jobs: dict[tuple[str, str], HJob] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._recovered_repos: set[str] = set()

    def schedule(self, repo_path: str | Path, run_id: str, operation: str, target: Callable[[], dict]) -> dict:
        store = RunStore(repo_path)
        key = self._key(store.repo_path, run_id)
        with self._guard:
            self._recovered_repos.add(str(store.repo_path).lower())
            existing = self._load_or_memory(store, run_id)
            if existing and existing.status in ACTIVE_JOB_STATES:
                return {"status": "running", "summary": "An H workflow job is already active for this run.", "h_job": existing.to_dict()}
            job = HJob(
                job_id=uuid4().hex,
                repo_path=str(store.repo_path),
                run_id=run_id,
                operation=operation,
                heartbeat_at=now_iso(),
                started_at=now_iso(),
            )
            self._jobs[key] = job
            self._save(store, job)
            thread = threading.Thread(target=self._run_target, args=(store, job, target), daemon=True, name=f"cloud-cua-{run_id}")
            self._threads[job.job_id] = thread
            thread.start()
        return {"status": "scheduled", "summary": f"Scheduled {operation} as an asynchronous H workflow job.", "h_job": job.to_dict()}

    def get(self, repo_path: str | Path, run_id: str) -> dict | None:
        store = RunStore(repo_path)
        with self._guard:
            job = self._load_or_memory(store, run_id)
            return job.to_dict() if job else None

    def observe_event(self, repo_path: str | Path, run_id: str, milestone: str, event: dict) -> None:
        store = RunStore(repo_path)
        with self._guard:
            job = self._load_or_memory(store, run_id)
            if not job:
                return
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            if event.get("type") == "HSessionStarted" and data.get("session_id"):
                job.session_id = str(data["session_id"])
            if event.get("type") == "HWorkerStarted" and data.get("worker_pid"):
                job.worker_pid = int(data["worker_pid"])
            job.status = "running" if job.status != "paused" else job.status
            job.milestone = milestone
            job.event_cursor += 1
            job.heartbeat_at = now_iso()
            self._save(store, job)
            spool = store.run_dir(run_id) / "h-events.jsonl"
            with spool.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(sanitize_obj(event), ensure_ascii=False) + "\n")

    def pause(self, repo_path: str | Path, run_id: str) -> dict:
        return self._control(repo_path, run_id, "pause")

    def resume(self, repo_path: str | Path, run_id: str) -> dict:
        return self._control(repo_path, run_id, "resume")

    def cancel(self, repo_path: str | Path, run_id: str) -> dict:
        store = RunStore(repo_path)
        with self._guard:
            job = self._load_or_memory(store, run_id)
            if not job:
                return {"status": "cancelled", "summary": "No active H job existed; the run was cancelled."}
            job.status = "cancelling"
            job.heartbeat_at = now_iso()
            self._save(store, job)
        if job.session_id:
            remote_status, error = self._call_h_and_confirm(job.session_id, "cancel")
            if error:
                fallback = cleanup_h_session(job.session_id, str(store.repo_path))
                if fallback.status == "passed":
                    if job.worker_pid:
                        _terminate_worker(job.worker_pid)
                    with self._guard:
                        job.status = "cancelled"
                        job.milestone = "targeted_cleanup_after_cancel_timeout"
                        job.error = ""
                        job.finished_at = now_iso()
                        job.heartbeat_at = now_iso()
                        self._save(store, job)
                    return {
                        "status": "cancelled",
                        "summary": "H did not confirm cancellation in time, so Cloud CUA stopped its owned session with targeted cleanup.",
                        "h_job": job.to_dict(),
                        "cleanup": fallback.to_dict(),
                    }
                with self._guard:
                    job.status = "cancelling"
                    job.error = error
                    job.heartbeat_at = now_iso()
                    self._save(store, job)
                return {"status": "cancelling", "summary": error, "h_job": job.to_dict()}
        if job.worker_pid:
            _terminate_worker(job.worker_pid)
        with self._guard:
            job.status = "cancelled"
            job.milestone = f"remote_{remote_status}" if job.session_id else "cancelled_before_session_start"
            job.finished_at = now_iso()
            self._save(store, job)
        return {"status": "cancelled", "summary": "Cancelled the hosted H session and its local worker.", "h_job": job.to_dict()}

    def recover_repo(self, repo_path: str | Path) -> None:
        store = RunStore(repo_path)
        repo_key = str(store.repo_path).lower()
        with self._guard:
            if repo_key in self._recovered_repos:
                return
            self._recovered_repos.add(repo_key)
        for path in store.root.glob("*/h-job.json"):
            try:
                job = HJob(**json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            if job.status not in ACTIVE_JOB_STATES:
                continue
            key = self._key(store.repo_path, job.run_id)
            with self._guard:
                self._jobs[key] = job
            thread = threading.Thread(target=self._recover_job, args=(store, job), daemon=True, name=f"cloud-cua-recover-{job.run_id}")
            thread.start()

    def _run_target(self, store: RunStore, job: HJob, target: Callable[[], dict]) -> None:
        with self._guard:
            job.status = "running"
            job.heartbeat_at = now_iso()
            self._save(store, job)
        try:
            result = target()
            with self._guard:
                if job.status != "cancelled":
                    job.status = "completed"
                    job.result = sanitize_obj(result)
        except Exception as exc:
            with self._guard:
                if job.status != "cancelled":
                    job.status = "failed"
                    job.error = f"{type(exc).__name__}: {exc}"
                    try:
                        run = store.load_run(job.run_id)
                        run.status = "failed"
                        run.current_step = "h_job_failed"
                        store.save_run(run)
                        store.append_event(job.run_id, "system", "error", f"Asynchronous H workflow failed: {job.error}")
                    except Exception:
                        pass
        finally:
            with self._guard:
                job.finished_at = now_iso()
                job.heartbeat_at = now_iso()
                self._save(store, job)

    def _control(self, repo_path: str | Path, run_id: str, action: str) -> dict:
        store = RunStore(repo_path)
        with self._guard:
            job = self._load_or_memory(store, run_id)
            if not job or job.status not in ACTIVE_JOB_STATES:
                return {"status": "skipped", "summary": f"No active H session is available to {action}."}
            session_id = job.session_id
        if session_id:
            remote_status, error = self._call_h_and_confirm(session_id, action)
            if error:
                return {"status": "failed", "summary": error, "h_job": job.to_dict()}
        with self._guard:
            job.status = "paused" if action == "pause" else "running"
            if session_id:
                job.milestone = f"remote_{remote_status}"
            job.heartbeat_at = now_iso()
            self._save(store, job)
        return {"status": job.status, "summary": f"H workflow {job.status}.", "h_job": job.to_dict()}

    def _call_h(self, session_id: str, action: str) -> str | None:
        api_key = load_secret_values().get("HAI_API_KEY")
        if not api_key:
            return "HAI_API_KEY is missing, so the hosted H session could not be controlled."
        try:
            from hai_agents import Client

            handle = Client(api_key=api_key).session(session_id)
            getattr(handle, action)()
            return None
        except Exception as exc:
            return f"H session {action} failed: {type(exc).__name__}: {exc}"

    def _call_h_and_confirm(
        self,
        session_id: str,
        action: str,
        *,
        timeout_seconds: float = 45,
        poll_seconds: float = 2,
        retry_seconds: float = 10,
    ) -> tuple[str, str | None]:
        api_key = load_secret_values().get("HAI_API_KEY")
        if not api_key:
            return "unknown", "HAI_API_KEY is missing, so the hosted H session could not be controlled."
        try:
            from hai_agents import Client

            handle = Client(api_key=api_key).session(session_id)
            getattr(handle, action)()
            attempts = 1
            next_retry = time.monotonic() + retry_seconds
            expected = {"paused"} if action == "pause" else ({"running", "idle"} if action == "resume" else H_TERMINAL_STATES)
            deadline = time.monotonic() + timeout_seconds
            last_status = "unknown"
            while time.monotonic() < deadline:
                snapshot = handle.status()
                last_status = str(getattr(snapshot, "status", snapshot)).lower()
                if last_status in expected:
                    return last_status, None
                if action != "cancel" and last_status in H_TERMINAL_STATES:
                    return last_status, f"H session became {last_status} before {action} was confirmed."
                if time.monotonic() >= next_retry:
                    # H control endpoints acknowledge delivery asynchronously. Repeating these
                    # state-setting requests is safe and recovers a command lost before execution.
                    getattr(handle, action)()
                    attempts += 1
                    next_retry = time.monotonic() + retry_seconds
                time.sleep(poll_seconds)
            return last_status, (
                f"H accepted the {action} request but did not confirm the expected remote state within "
                f"{timeout_seconds:g} seconds after {attempts} attempts (last state: {last_status})."
            )
        except Exception as exc:
            if action == "cancel" and getattr(exc, "status_code", None) == 404:
                return "completed", None
            return "unknown", f"H session {action} failed: {type(exc).__name__}: {exc}"

    def _recover_job(self, store: RunStore, job: HJob) -> None:
        job.status = "recovering"
        job.heartbeat_at = now_iso()
        self._save(store, job)
        if not job.session_id:
            self._block_interrupted(store, job, "Backend restarted before H returned a session id.")
            return
        api_key = load_secret_values().get("HAI_API_KEY")
        if not api_key:
            self._block_interrupted(store, job, "Backend restarted and H credentials are unavailable for session recovery.")
            return
        try:
            from hai_agents import Client

            handle = Client(api_key=api_key).session(job.session_id)
            snapshot = handle.status()
            status = str(getattr(snapshot, "status", snapshot)).lower()
        except Exception as exc:
            self._block_interrupted(store, job, f"Could not reconnect to H session: {type(exc).__name__}: {exc}")
            return
        if status in H_TERMINAL_STATES:
            self._block_interrupted(store, job, f"Recovered H session was already terminal ({status}); rerun the saved milestone.")
            return
        remote_status, error = self._call_h_and_confirm(job.session_id, "cancel")
        if error:
            targeted = cleanup_h_session(job.session_id, str(store.repo_path))
            self._block_interrupted(
                store,
                job,
                "Backend restarted during H local-browser control. The browser bridge cannot be reattached and "
                f"normal cancellation was not confirmed. Targeted cleanup status: {targeted.status}. {error}",
            )
            return
        self._block_interrupted(
            store,
            job,
            "Backend restarted during H local-browser control. Cloud CUA stopped the hosted H session "
            f"({remote_status}) and preserved the last milestone for a safe retry.",
        )

    def _block_interrupted(self, store: RunStore, job: HJob, message: str) -> None:
        job.status = "interrupted"
        job.error = message
        job.finished_at = now_iso()
        self._save(store, job)
        try:
            run = store.load_run(job.run_id)
            run.status = "blocked"
            run.current_step = "h_job_recovery_required"
            store.save_run(run)
            store.append_event(job.run_id, "system", "error", message)
        except Exception:
            pass

    def _load_or_memory(self, store: RunStore, run_id: str) -> HJob | None:
        key = self._key(store.repo_path, run_id)
        if key in self._jobs:
            return self._jobs[key]
        path = store.run_dir(run_id) / "h-job.json"
        if not path.exists():
            return None
        try:
            job = HJob(**json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None
        self._jobs[key] = job
        return job

    @staticmethod
    def _key(repo_path: Path, run_id: str) -> tuple[str, str]:
        return str(repo_path).lower(), run_id

    @staticmethod
    def _save(store: RunStore, job: HJob) -> None:
        path = store.run_dir(job.run_id) / "h-job.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
        temporary.replace(path)


def _terminate_worker(pid: int) -> None:
    if pid <= 0 or pid == os.getpid():
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=15)
        else:
            os.kill(pid, 15)
    except (OSError, subprocess.SubprocessError):
        return


_MANAGER = HSessionManager()


def get_h_session_manager() -> HSessionManager:
    return _MANAGER
