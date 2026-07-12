from __future__ import annotations

import asyncio
import base64
import json

from cloud_cua.voice_gradium import synthesize_tts_stream, transcribe_stt_stream


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def recv(self):
        return json.dumps({"type": "ready"})

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.messages:
            raise StopAsyncIteration
        return json.dumps(self.messages.pop(0))


def test_streaming_stt_sends_pcm_and_reports_partial_text(monkeypatch) -> None:
    socket = FakeWebSocket([
        {"type": "text", "text": "pause"},
        {"type": "end_text", "stop_s": 0.4},
        {"type": "end_of_stream"},
    ])
    monkeypatch.setattr("cloud_cua.voice_gradium.load_secret_values", lambda *_args: {"GRADIUM_API_KEY": "key"})

    async def connect(*_args):
        return socket

    monkeypatch.setattr("cloud_cua.voice_gradium._connect", connect)
    events = []

    async def chunks():
        yield b"\x01\x02" * 1920

    async def capture(event):
        events.append(event)

    result = asyncio.run(transcribe_stt_stream(chunks(), on_event=capture))

    assert result.status == "passed"
    assert result.transcript == "pause"
    assert socket.sent[0]["input_format"] == "pcm"
    assert base64.b64decode(socket.sent[1]["audio"]) == b"\x01\x02" * 1920
    assert any(event["type"] == "partial" and event["text"] == "pause" for event in events)
    assert socket.sent[-2]["type"] == "flush"
    assert socket.sent[-1]["type"] == "end_of_stream"


def test_streaming_tts_uses_documented_default_voice_and_pcm(monkeypatch) -> None:
    audio = b"\x10\x20" * 200
    socket = FakeWebSocket([
        {"type": "audio", "audio": base64.b64encode(audio).decode("ascii")},
        {"type": "end_of_stream"},
    ])
    monkeypatch.setattr("cloud_cua.voice_gradium.load_secret_values", lambda *_args: {"GRADIUM_API_KEY": "key"})

    async def connect(*_args):
        return socket

    monkeypatch.setattr("cloud_cua.voice_gradium._connect", connect)
    chunks = []

    async def capture(chunk):
        chunks.append(chunk)

    result = asyncio.run(synthesize_tts_stream("Deployment paused.", on_audio=capture))

    assert result.status == "passed"
    assert chunks == [audio]
    assert socket.sent[0]["voice_id"] == "YTpq7expH9539ERJ"
    assert socket.sent[0]["output_format"] == "pcm"


def test_streaming_gradium_setup_error_fails_closed(monkeypatch) -> None:
    socket = FakeWebSocket([])

    async def recv_error():
        return json.dumps({"type": "error", "message": "invalid format"})

    socket.recv = recv_error
    monkeypatch.setattr("cloud_cua.voice_gradium.load_secret_values", lambda *_args: {"GRADIUM_API_KEY": "key"})

    async def connect(*_args):
        return socket

    monkeypatch.setattr("cloud_cua.voice_gradium._connect", connect)

    async def chunks():
        yield b"audio"

    result = asyncio.run(transcribe_stt_stream(chunks()))
    assert result.status == "failed"
    assert result.summary == "invalid format"
