from __future__ import annotations

import sys
import time
from types import SimpleNamespace

from cloud_cua.h_session_manager import HJob, HSessionManager
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


def test_pause_waits_for_remote_confirmation(tmp_path, monkeypatch):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    manager = HSessionManager()
    manager.schedule(tmp_path, run.run_id, "inspect", lambda: time.sleep(1) or {"status": "passed"})
    manager.observe_event(tmp_path, run.run_id, "inspect", {"type": "HSessionStarted", "data": {"session_id": "session-1"}})
    monkeypatch.setattr(manager, "_call_h_and_confirm", lambda *_args, **_kwargs: ("running", "pause not confirmed"))

    result = manager.pause(tmp_path, run.run_id)

    assert result["status"] == "failed"
    assert manager.get(tmp_path, run.run_id)["status"] == "running"


def test_cancel_stays_pending_when_remote_does_not_confirm(tmp_path, monkeypatch):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    manager = HSessionManager()
    manager.schedule(tmp_path, run.run_id, "inspect", lambda: time.sleep(1) or {"status": "passed"})
    manager.observe_event(tmp_path, run.run_id, "inspect", {"type": "HSessionStarted", "data": {"session_id": "session-1"}})
    monkeypatch.setattr(manager, "_call_h_and_confirm", lambda *_args, **_kwargs: ("running", "cancel not confirmed"))

    result = manager.cancel(tmp_path, run.run_id)

    assert result["status"] == "cancelling"
    assert manager.get(tmp_path, run.run_id)["status"] == "cancelling"


def test_h_control_retries_until_remote_state_is_confirmed(monkeypatch):
    calls = []
    statuses = iter([SimpleNamespace(status="running"), SimpleNamespace(status="paused")])

    class FakeHandle:
        def pause(self):
            calls.append("pause")

        def status(self):
            return next(statuses)

    fake_module = SimpleNamespace(Client=lambda **_kwargs: SimpleNamespace(session=lambda _session_id: FakeHandle()))
    monkeypatch.setitem(sys.modules, "hai_agents", fake_module)
    monkeypatch.setattr("cloud_cua.h_session_manager.load_secret_values", lambda: {"HAI_API_KEY": "test"})

    status, error = HSessionManager()._call_h_and_confirm(
        "session-1",
        "pause",
        timeout_seconds=1,
        poll_seconds=0,
        retry_seconds=0,
    )

    assert status == "paused"
    assert error is None
    assert calls == ["pause", "pause"]


def test_recovery_stops_unattachable_local_browser_session(tmp_path, monkeypatch):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    job = HJob(
        job_id="job-1",
        repo_path=str(tmp_path),
        run_id=run.run_id,
        operation="inspect",
        status="running",
        session_id="session-1",
        worker_pid=12345,
    )
    manager = HSessionManager()
    manager._save(store, job)
    fake_handle = SimpleNamespace(status=lambda: SimpleNamespace(status="running"))
    fake_module = SimpleNamespace(Client=lambda **_kwargs: SimpleNamespace(session=lambda _session_id: fake_handle))
    monkeypatch.setitem(sys.modules, "hai_agents", fake_module)
    monkeypatch.setattr("cloud_cua.h_session_manager.load_secret_values", lambda: {"HAI_API_KEY": "test"})
    monkeypatch.setattr(manager, "_call_h_and_confirm", lambda *_args, **_kwargs: ("interrupted", None))

    manager._recover_job(store, job)

    saved = manager.get(tmp_path, run.run_id)
    recovered_run = store.load_run(run.run_id)
    assert saved["status"] == "interrupted"
    assert recovered_run.status == "blocked"
    assert recovered_run.current_step == "h_job_recovery_required"
