from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from typing import Any, AsyncIterable, Awaitable, Callable

import websockets

from .credentials import load_secret_values

TTS_WS_URL = "wss://api.gradium.ai/api/speech/tts"
STT_WS_URL = "wss://api.gradium.ai/api/speech/asr"
DEFAULT_TTS_VOICE_ID = "YTpq7expH9539ERJ"

STTEventCallback = Callable[[dict], Awaitable[None]]
TTSAudioCallback = Callable[[bytes], Awaitable[None]]


@dataclass(frozen=True)
class TTSResult:
    status: str
    audio_base64: str = ""
    text_segments: tuple[str, ...] = ()
    summary: str = ""


@dataclass(frozen=True)
class STTResult:
    status: str
    transcript: str = ""
    summary: str = ""


async def _noop_event(_event: dict) -> None:
    return None


async def _noop_audio(_audio: bytes) -> None:
    return None


async def _connect(url: str, api_key: str):
    try:
        return websockets.connect(url, additional_headers={"x-api-key": api_key})
    except TypeError:
        return websockets.connect(url, extra_headers={"x-api-key": api_key})


async def synthesize_tts_async(text: str, repo_path: str | None = None, voice_id: str | None = None) -> TTSResult:
    values = load_secret_values(repo_path)
    api_key = values.get("GRADIUM_API_KEY")
    if not api_key:
        return TTSResult("skipped", summary="GRADIUM_API_KEY is not configured.")

    audio_chunks: list[str] = []
    text_segments: list[str] = []
    try:
        async with await _connect(TTS_WS_URL, api_key) as ws:
            setup: dict[str, Any] = {"type": "setup", "model_name": "default", "output_format": "wav"}
            if voice_id:
                setup["voice_id"] = voice_id
            await ws.send(json.dumps(setup))
            await ws.send(json.dumps({"type": "text", "text": text}))
            await ws.send(json.dumps({"type": "end_of_stream"}))
            async for raw in ws:
                msg = json.loads(raw)
                msg_type = msg.get("type")
                if msg_type == "audio" and msg.get("audio"):
                    audio_chunks.append(msg["audio"])
                elif msg_type == "text" and msg.get("text"):
                    text_segments.append(msg["text"])
                elif msg_type == "error":
                    return TTSResult("failed", summary=msg.get("message", "Gradium TTS error."))
                elif msg_type == "end_of_stream":
                    break
    except Exception as exc:
        return TTSResult("failed", summary=f"Gradium TTS failed: {exc}")
    return TTSResult("passed", audio_base64="".join(audio_chunks), text_segments=tuple(text_segments), summary="Generated TTS audio.")


async def transcribe_stt_async(audio_bytes: bytes, repo_path: str | None = None, input_format: str = "wav") -> STTResult:
    values = load_secret_values(repo_path)
    api_key = values.get("GRADIUM_API_KEY")
    if not api_key:
        return STTResult("skipped", summary="GRADIUM_API_KEY is not configured.")

    transcript: list[str] = []
    try:
        async with await _connect(STT_WS_URL, api_key) as ws:
            await ws.send(json.dumps({"type": "setup", "model_name": "default", "input_format": input_format, "json_config": {"language": "en", "delay_in_frames": 16}}))
            await ws.send(json.dumps({"type": "audio", "audio": base64.b64encode(audio_bytes).decode("ascii")}))
            await ws.send(json.dumps({"type": "flush", "flush_id": 1}))
            await ws.send(json.dumps({"type": "end_of_stream"}))
            async for raw in ws:
                msg = json.loads(raw)
                msg_type = msg.get("type")
                if msg_type == "text" and msg.get("text"):
                    transcript.append(msg["text"])
                elif msg_type == "error":
                    return STTResult("failed", summary=msg.get("message", "Gradium STT error."))
                elif msg_type == "end_of_stream":
                    break
    except Exception as exc:
        return STTResult("failed", summary=f"Gradium STT failed: {exc}")
    return STTResult("passed", transcript=" ".join(t.strip() for t in transcript if t.strip()), summary="Transcribed audio.")


async def transcribe_stt_stream(
    audio_chunks: AsyncIterable[bytes],
    repo_path: str | None = None,
    on_event: STTEventCallback | None = None,
) -> STTResult:
    values = load_secret_values(repo_path)
    api_key = values.get("GRADIUM_API_KEY")
    if not api_key:
        return STTResult("skipped", summary="GRADIUM_API_KEY is not configured.")
    callback = on_event or _noop_event
    transcript: list[str] = []
    try:
        async with await _connect(STT_WS_URL, api_key) as ws:
            await ws.send(json.dumps({"type": "setup", "model_name": "default", "input_format": "pcm", "json_config": {"language": "en", "delay_in_frames": 16}}))
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if ready.get("type") == "error":
                return STTResult("failed", summary=ready.get("message", "Gradium STT setup failed."))
            if ready.get("type") != "ready":
                return STTResult("failed", summary=f"Gradium STT expected ready but received {ready.get('type', 'unknown')}.")
            await callback({"type": "ready"})

            async def produce() -> None:
                async for chunk in audio_chunks:
                    if chunk:
                        await ws.send(json.dumps({"type": "audio", "audio": base64.b64encode(chunk).decode("ascii")}))
                await ws.send(json.dumps({"type": "flush", "flush_id": 1}))
                await ws.send(json.dumps({"type": "end_of_stream"}))

            async def consume() -> str | None:
                async for raw in ws:
                    msg = json.loads(raw)
                    msg_type = msg.get("type")
                    if msg_type == "text" and msg.get("text"):
                        transcript.append(str(msg["text"]).strip())
                        await callback({"type": "partial", "text": " ".join(part for part in transcript if part)})
                    elif msg_type in {"step", "end_text", "flushed"}:
                        await callback(msg)
                    elif msg_type == "error":
                        return msg.get("message", "Gradium STT error.")
                    elif msg_type == "end_of_stream":
                        break
                return None

            _, error = await asyncio.gather(produce(), consume())
            if error:
                return STTResult("failed", summary=error)
    except Exception as exc:
        return STTResult("failed", summary=f"Gradium streaming STT failed: {exc}")
    final = " ".join(part for part in transcript if part).strip()
    await callback({"type": "final", "text": final})
    return STTResult("passed", transcript=final, summary="Streamed microphone audio to Gradium STT.")


async def synthesize_tts_stream(
    text: str,
    repo_path: str | None = None,
    voice_id: str | None = None,
    on_audio: TTSAudioCallback | None = None,
    on_event: STTEventCallback | None = None,
) -> TTSResult:
    values = load_secret_values(repo_path)
    api_key = values.get("GRADIUM_API_KEY")
    if not api_key:
        return TTSResult("skipped", summary="GRADIUM_API_KEY is not configured.")
    selected_voice = voice_id or values.get("GRADIUM_TTS_VOICE_ID") or DEFAULT_TTS_VOICE_ID
    audio_callback = on_audio or _noop_audio
    event_callback = on_event or _noop_event
    audio_chunks = 0
    text_segments: list[str] = []
    try:
        async with await _connect(TTS_WS_URL, api_key) as ws:
            await ws.send(json.dumps({"type": "setup", "model_name": "default", "voice_id": selected_voice, "output_format": "pcm"}))
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if ready.get("type") == "error":
                return TTSResult("failed", summary=ready.get("message", "Gradium TTS setup failed."))
            if ready.get("type") != "ready":
                return TTSResult("failed", summary=f"Gradium TTS expected ready but received {ready.get('type', 'unknown')}.")
            await event_callback({"type": "ready", "voice_id": selected_voice, "sample_rate": 48000})
            await ws.send(json.dumps({"type": "text", "text": text}))
            await ws.send(json.dumps({"type": "end_of_stream"}))
            async for raw in ws:
                msg = json.loads(raw)
                msg_type = msg.get("type")
                if msg_type == "audio" and msg.get("audio"):
                    chunk = base64.b64decode(msg["audio"])
                    audio_chunks += 1
                    await audio_callback(chunk)
                elif msg_type == "text" and msg.get("text"):
                    text_segments.append(str(msg["text"]))
                    await event_callback(msg)
                elif msg_type == "error":
                    return TTSResult("failed", summary=msg.get("message", "Gradium TTS error."))
                elif msg_type == "end_of_stream":
                    break
    except Exception as exc:
        return TTSResult("failed", summary=f"Gradium streaming TTS failed: {exc}")
    return TTSResult("passed", text_segments=tuple(text_segments), summary=f"Streamed {audio_chunks} TTS audio chunks.")


def synthesize_tts(text: str, repo_path: str | None = None, voice_id: str | None = None) -> TTSResult:
    return asyncio.run(synthesize_tts_async(text, repo_path, voice_id))


def transcribe_stt(audio_bytes: bytes, repo_path: str | None = None, input_format: str = "wav") -> STTResult:
    return asyncio.run(transcribe_stt_async(audio_bytes, repo_path, input_format))
