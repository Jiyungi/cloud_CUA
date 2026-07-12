from __future__ import annotations

import time

from cloud_cua.h_session_manager import HSessionManager
from cloud_cua.run_store import RunStore


def test_h_job_is_durable_and_prevents_duplicates(tmp_path):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    manager = HSessionManager()

    first = manager.schedule(tmp_path, run.run_id, "inspect", lambda: (time.sleep(0.15) or {"status": "passed"}))
    duplicate = manager.schedule(tmp_path, run.run_id, "inspect", lambda: {"status": "should-not-run"})

    assert first["status"] == "scheduled"
    assert duplicate["status"] == "running"
    deadline = time.time() + 2
    while time.time() < deadline and manager.get(tmp_path, run.run_id)["status"] in {"queued", "running"}:
        time.sleep(0.02)
    job = manager.get(tmp_path, run.run_id)
    assert job["status"] == "completed"
    assert (store.run_dir(run.run_id) / "h-job.json").exists()


def test_h_job_records_session_and_worker_events(tmp_path):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    manager = HSessionManager()
    manager.schedule(tmp_path, run.run_id, "inspect", lambda: (time.sleep(0.2) or {"status": "passed"}))
    manager.observe_event(tmp_path, run.run_id, "inspect", {"type": "HWorkerStarted", "data": {"worker_pid": 12345}})
    manager.observe_event(tmp_path, run.run_id, "inspect", {"type": "HSessionStarted", "data": {"session_id": "session-1"}})
    job = manager.get(tmp_path, run.run_id)
    assert job["worker_pid"] == 12345
    assert job["session_id"] == "session-1"
    assert job["event_cursor"] == 2
    assert (store.run_dir(run.run_id) / "h-events.jsonl").exists()


def test_cancel_without_active_h_session_is_safe(tmp_path):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    manager = HSessionManager()
    result = manager.cancel(tmp_path, run.run_id)
    assert result["status"] == "cancelled"
