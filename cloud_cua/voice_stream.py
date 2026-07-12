from __future__ import annotations

import asyncio
import json
import secrets
import time
from contextlib import suppress

from fastapi import WebSocket, WebSocketDisconnect

from .orchestrator import Orchestrator
from .voice_gradium import synthesize_tts_stream, transcribe_stt_stream
from .voice_router import classify_voice_command
from .voice_state import VoiceTurnStore

MAX_VOICE_SECONDS = 60
MAX_PCM_BYTES = 24_000 * 2 * MAX_VOICE_SECONDS
MAX_FRAME_BYTES = 24_000 * 2


async def handle_voice_stream(websocket: WebSocket, repo_path: str, run_id: str, service_token: str) -> None:
    supplied = websocket.cookies.get("cloud_cua_session") or websocket.headers.get("x-cloud-cua-token")
    if service_token and not secrets.compare_digest(supplied or "", service_token):
        await websocket.close(code=4401, reason="Cloud CUA dashboard authorization is required.")
        return

    orchestrator = Orchestrator(repo_path)
    try:
        orchestrator.store.load_run(run_id)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        await websocket.close(code=4404, reason="Cloud CUA run was not found for this repository.")
        return
    if not orchestrator.store.acquire_lock(run_id, "voice-stream"):
        await websocket.accept()
        await websocket.send_json({"type": "error", "state": "failed", "message": "Another voice turn is already active for this run."})
        await websocket.close(code=4409)
        return

    await websocket.accept()
    turns = VoiceTurnStore(orchestrator.store.run_dir(run_id))
    turn = turns.create(run_id, "listening")
    queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=400)
    total_bytes = 0
    started = time.monotonic()

    async def audio_chunks():
        while True:
            chunk = await queue.get()
            if chunk is None:
                return
            yield chunk

    async def stt_event(event: dict) -> None:
        event_type = event.get("type")
        if event_type == "partial":
            partial = str(event.get("text", ""))
            turns.update(turn.turn_id, state="transcribing", partial_transcript=partial)
            await websocket.send_json({"type": "partial_transcript", "state": "transcribing", "turn_id": turn.turn_id, "text": partial})

    stt_task = asyncio.create_task(transcribe_stt_stream(audio_chunks(), repo_path, stt_event))
    try:
        await websocket.send_json({"type": "state", "state": "listening", "turn_id": turn.turn_id, "sample_rate": 24000, "max_seconds": MAX_VOICE_SECONDS})
        while True:
            remaining = MAX_VOICE_SECONDS - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("Voice recording reached the 60-second limit.")
            message = await asyncio.wait_for(websocket.receive(), timeout=remaining)
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))
            chunk = message.get("bytes")
            if chunk is not None:
                if len(chunk) > MAX_FRAME_BYTES:
                    raise ValueError("Microphone frame is too large.")
                total_bytes += len(chunk)
                if total_bytes > MAX_PCM_BYTES:
                    raise ValueError("Voice recording exceeded the 60-second PCM limit.")
                await queue.put(chunk)
                continue
            payload = json.loads(message.get("text") or "{}")
            if payload.get("type") == "end":
                await queue.put(None)
                break
            if payload.get("type") == "cancel":
                turns.update(turn.turn_id, state="cancelled", error="Voice turn cancelled by user.")
                await queue.put(None)
                await websocket.send_json({"type": "state", "state": "cancelled", "turn_id": turn.turn_id})
                return

        turns.update(turn.turn_id, state="transcribing")
        await websocket.send_json({"type": "state", "state": "transcribing", "turn_id": turn.turn_id})
        stt = await asyncio.wait_for(stt_task, timeout=20)
        if stt.status != "passed" or not stt.transcript.strip():
            message = stt.summary if stt.status != "passed" else "No speech was detected."
            turns.update(turn.turn_id, state="failed", error=message)
            await websocket.send_json({"type": "error", "state": "failed", "turn_id": turn.turn_id, "message": message})
            return

        transcript = stt.transcript.strip()
        turns.update(turn.turn_id, state="routing", transcript=transcript, partial_transcript="")
        await websocket.send_json({"type": "final_transcript", "state": "routing", "turn_id": turn.turn_id, "text": transcript})
        preview = classify_voice_command(transcript)
        next_state = "answering" if preview.classification in {"reasoning_question", "planned_cloud_action"} else "executing"
        turns.update(turn.turn_id, state=next_state, classification=preview.classification, action=preview.action or "")
        await websocket.send_json({"type": "state", "state": next_state, "turn_id": turn.turn_id, "classification": preview.classification})
        result = await asyncio.to_thread(orchestrator.voice_command, run_id, transcript, turn_id=turn.turn_id)
        await websocket.send_json({"type": "action_result", "state": "completed" if result.get("executed") else "failed", "turn_id": turn.turn_id, "result": result})

        if result.get("speak") and result.get("response"):
            turns.update(turn.turn_id, state="speaking")

            async def tts_event(event: dict) -> None:
                if event.get("type") == "ready":
                    await websocket.send_json({"type": "tts_start", "state": "speaking", "turn_id": turn.turn_id, "sample_rate": event.get("sample_rate", 48000)})

            async def tts_audio(chunk: bytes) -> None:
                await websocket.send_bytes(chunk)

            tts = await synthesize_tts_stream(result["response"], repo_path, on_audio=tts_audio, on_event=tts_event)
            await websocket.send_json({"type": "tts_end", "state": "completed" if tts.status == "passed" else "failed", "turn_id": turn.turn_id, "status": tts.status, "message": tts.summary})
        current = turns.current()
        if current and current.turn_id == turn.turn_id and current.state not in {"failed", "cancelled"}:
            turns.update(turn.turn_id, state="completed")
        await websocket.send_json({"type": "done", "state": "completed", "turn_id": turn.turn_id})
    except WebSocketDisconnect:
        get_job = orchestrator.get_voice_status(run_id).get("codex_job")
        if get_job and get_job.get("status") in {"queued", "running"}:
            orchestrator.cancel_codex_voice(run_id)
        with suppress(KeyError):
            turns.update(turn.turn_id, state="cancelled", error="Dashboard disconnected during voice turn.")
    except Exception as exc:
        with suppress(KeyError):
            turns.update(turn.turn_id, state="failed", error=str(exc))
        with suppress(RuntimeError, WebSocketDisconnect):
            await websocket.send_json({"type": "error", "state": "failed", "turn_id": turn.turn_id, "message": str(exc)})
    finally:
        if not stt_task.done():
            stt_task.cancel()
            with suppress(asyncio.CancelledError):
                await stt_task
        orchestrator.store.release_lock(run_id, "voice-stream")
