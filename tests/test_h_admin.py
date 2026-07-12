from __future__ import annotations

from cloud_cua.h_admin import cleanup_h_session, cleanup_h_sessions
from cloud_cua.h_runner import _acquire_local_browser_lock, _release_local_browser_lock


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeHClient:
    def __init__(self):
        self.deleted = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get(self, path, params=None):
        if path == "/api/v2/sessions/quota":
            return FakeResponse(payload={"limit": 3, "active": 2, "available": 1})
        if path == "/api/v2/sessions":
            return FakeResponse(
                payload={
                    "items": [
                        {"id": "cloud-1", "status": "running", "agent": "cloud-cua-local-browser"},
                        {"id": "other-1", "status": "running", "agent": "another-product"},
                    ]
                }
            )
        if path == "/api/v1/trajectories/":
            return FakeResponse(payload={"items": [{"id": "cloud-1", "status": "running"}, {"id": "other-1", "status": "running"}]})
        if path == "/api/v2/sessions/other-1":
            return FakeResponse(payload={"id": "other-1", "status": "running", "agent": "another-product"})
        return FakeResponse(status_code=404)

    def delete(self, path):
        self.deleted.append(path)
        return FakeResponse(status_code=204)


def test_cleanup_only_deletes_cloud_cua_sessions(monkeypatch):
    client = FakeHClient()
    monkeypatch.setattr("cloud_cua.h_admin.load_secret_values", lambda *_args: {"HAI_API_KEY": "test"})
    monkeypatch.setattr("cloud_cua.h_admin.httpx.Client", lambda **_kwargs: client)

    result = cleanup_h_sessions()

    assert result.status == "passed"
    assert "/api/v2/sessions/cloud-1" in client.deleted
    assert "/api/v1/trajectories/cloud-1" in client.deleted
    assert all("other-1" not in path for path in client.deleted)


def test_targeted_cleanup_refuses_unrelated_h_session(monkeypatch):
    client = FakeHClient()
    monkeypatch.setattr("cloud_cua.h_admin.load_secret_values", lambda *_args: {"HAI_API_KEY": "test"})
    monkeypatch.setattr("cloud_cua.h_admin.httpx.Client", lambda **_kwargs: client)

    result = cleanup_h_session("other-1")

    assert result.status == "failed"
    assert client.deleted == []


def test_local_browser_lock_has_one_owner(tmp_path, monkeypatch):
    monkeypatch.setattr("cloud_cua.h_runner.user_config_dir", lambda: tmp_path)

    first = _acquire_local_browser_lock()
    second = _acquire_local_browser_lock()
    assert first
    assert second is None

    _release_local_browser_lock(first)
    third = _acquire_local_browser_lock()
    assert third
    _release_local_browser_lock(third)
