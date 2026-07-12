from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from cloud_cua.server import create_app
from cloud_cua.voice_gradium import STTResult
from cloud_cua.voice_state import VoiceTurnStore


def test_authenticated_voice_stream_routes_pcm_command(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CLOUD_CUA_SERVICE_TOKEN", "local-token")
    received_audio = []

    async def fake_stt(chunks, _repo_path, on_event):
        async for chunk in chunks:
            received_audio.append(chunk)
        await on_event({"type": "partial", "text": "pause"})
        await on_event({"type": "final", "text": "pause"})
        return STTResult("passed", "pause", "ok")

    monkeypatch.setattr("cloud_cua.voice_stream.transcribe_stt_stream", fake_stt)
    client = TestClient(create_app(), headers={"X-Cloud-CUA-Token": "local-token"})
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "teach"}).json()
    messages = []

    with client.websocket_connect(
        f"/runs/{run['run_id']}/voice-stream?repo_path={tmp_path}",
        headers={"X-Cloud-CUA-Token": "local-token"},
    ) as websocket:
        assert websocket.receive_json()["state"] == "listening"
        websocket.send_bytes(b"\x00\x01" * 1920)
        websocket.send_json({"type": "end"})
        while True:
            message = websocket.receive_json()
            messages.append(message)
            if message["type"] == "done":
                break

    assert received_audio == [b"\x00\x01" * 1920]
    assert any(item["type"] == "partial_transcript" and item["text"] == "pause" for item in messages)
    action = next(item for item in messages if item["type"] == "action_result")
    assert action["result"]["action"] == "pause"
    assert action["result"]["executed"] is True
    assert VoiceTurnStore(tmp_path / ".cloud-cua" / "runs" / run["run_id"]).current().state == "completed"


def test_voice_stream_requires_local_dashboard_authentication(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CLOUD_CUA_SERVICE_TOKEN", "local-token")
    app = create_app()
    client = TestClient(app, headers={"X-Cloud-CUA-Token": "local-token"})
    run = client.post("/runs", json={"repo_path": str(tmp_path), "cloud": "aws", "mode": "teach"}).json()
    unauthorized = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as error:
        with unauthorized.websocket_connect(f"/runs/{run['run_id']}/voice-stream?repo_path={tmp_path}"):
            pass

    assert error.value.code == 4401
