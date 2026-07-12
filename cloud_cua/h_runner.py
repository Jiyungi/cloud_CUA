from __future__ import annotations

import json
import os
import subprocess
import sys
import queue
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import asdict
from typing import Any

from .credentials import load_secret_values
from .h_admin import cleanup_h_sessions, get_h_quota
from .mode_policy import policy_for
from .models import Mode


@dataclass(frozen=True)
class HTaskResult:
    status: str
    summary: str
    raw: str = ""
    session_id: str | None = None
    agent_view_url: str | None = None
    outcome: str | None = None
    error: str | None = None


def _event_excerpt(events: list[Any], limit: int = 8) -> str:
    lines: list[str] = []
    for event in events[-limit:]:
        if hasattr(event, "model_dump"):
            event = event.model_dump()
        if not isinstance(event, dict):
            lines.append(str(event)[:400])
            continue
        event_type = event.get("type", "event")
        data = event.get("data")
        lines.append(f"{event_type}: {str(data)[:500]}")
    return "\n".join(lines)


def _inline_browser_agent(mode: Mode, skill_names: list[str] | None = None) -> dict[str, Any]:
    agent = {
        "name": "cloud-cua-local-browser",
        "description": "Use the user's local browser to inspect or operate a cloud console under Cloud CUA supervision.",
        "instructions": (
            "You are Cloud CUA's browser operator. Follow the task exactly. "
            "Never enter secrets. Never bypass login, MFA, captcha, billing prompts, OAuth prompts, or permission prompts. "
            "For inspect tasks, do not create, edit, delete, connect accounts, or change settings. "
            "For modify tasks, stop and report if the task requires paid resources, broad IAM, public exposure, deletion, or account linking unless the prompt explicitly says approval was granted. "
            "At the end, answer with a concise summary of what you saw or did, any blockers, and the exact visible page/result. "
            f"Mode policy: {policy_for(mode)}"
        ),
        "environments": [
            {
                "kind": "web",
                "id": "cloud-cua-browser",
                "host": "user_device",
                "start_url": "https://console.aws.amazon.com/",
                "headless": False,
                "mode": {"type": "visual", "width": 1440, "height": 1000, "markdown": True},
            }
        ],
    }
    if skill_names:
        agent["skills"] = skill_names
    return agent


def _run_h_task_sdk(
    task: str,
    mode: Mode = "vibe",
    max_steps: int = 20,
    max_time_s: int = 180,
    skill_names: list[str] | None = None,
    event_callback: Callable[[dict[str, Any]], None] | None = None,
) -> HTaskResult:
    if os.environ.get("CLOUD_CUA_CONTAINER") == "1":
        return HTaskResult(
            status="blocked",
            summary=(
                "H CUA local browser takeover is host-local and is disabled in Docker mode. "
                "Run `python -m cloud_cua.cli start` on the host machine for real H browser control. "
                "Docker mode is for the dashboard, MCP surface, repo analysis, AWS/Docker CLI checks, and verifiers."
            ),
        )
    values = load_secret_values()
    api_key = values.get("HAI_API_KEY")
    if not api_key:
        return HTaskResult(
            status="blocked",
            summary="HAI_API_KEY is not configured. Add it before running H browser control.",
        )
    try:
        cleanup_h_sessions()
        quota = get_h_quota()
        if quota and quota.available is not None and quota.available <= 0:
            return HTaskResult(
                status="blocked",
                summary=(
                    "H has no available concurrent session slots. "
                    f"Limit={quota.limit}, active={quota.active}, available={quota.available}. "
                    "Run H cleanup or cancel stale sessions before starting another CUA task."
                ),
            )
    except Exception:
        pass

    full_task = (
        f"{task}\n\n"
        "Success criteria: report the current page, the action result, and any visible blocker. "
        "If the user is not logged in, stop and say login is required."
    )
    try:
        from hai_agents import Client

        client = Client(api_key=api_key)
        create_params = {
            "agent": _inline_browser_agent(mode, skill_names),
            "messages": full_task,
            "max_steps": max_steps,
            "max_time_s": max_time_s,
            "queue": False,
        }
        if event_callback:
            handle = client.start_session(**create_params)
            for event in handle.stream(wait_for_seconds=5, until="settled", timeout_seconds=max_time_s + 60):
                event_callback(_event_dict(event))
            result = handle.wait_for_completion(wait_for_seconds=5, timeout_seconds=60, include_events=True)
        else:
            result = client.run_session(
                **create_params,
                wait_for_seconds=5,
                timeout_seconds=max_time_s + 60,
                include_events=True,
            )
        status = "completed" if result.status in {"completed", "idle"} and result.outcome not in {"blocked", "infeasible"} else str(result.status)
        answer = "" if result.answer is None else str(result.answer)
        summary = answer.strip() or result.error or _event_excerpt(result.events) or f"H session ended with status {result.status}."
        raw = _event_excerpt(result.events, limit=20)
        return HTaskResult(
            status=status,
            summary=summary[-8000:],
            raw=raw,
            session_id=result.id,
            outcome=result.outcome,
            error=result.error,
        )
    except TimeoutError as exc:
        return HTaskResult(status="timed_out", summary=f"H task timed out: {exc}")
    except Exception as exc:
        trace = traceback.format_exc()
        if "HTTPStatusError" in trace and "429" in trace:
            return HTaskResult(
                status="blocked",
                summary=(
                    "H API rate limited this run while creating the local browser session. "
                    "Chrome/Selenium is available locally, but H's hosted trajectory channel returned HTTP 429. "
                    "Wait for the rate limit to reset or use a key/account with available quota."
                ),
                raw=trace[-4000:],
                error=str(exc),
            )
        return HTaskResult(
            status="failed",
            summary=f"H browser session failed: {type(exc).__name__}: {exc}",
            raw=trace[-4000:],
            error=str(exc),
        )
    finally:
        try:
            cleanup_h_sessions()
        except Exception:
            pass


def run_h_task(
    task: str,
    mode: Mode = "vibe",
    max_steps: int = 20,
    max_time_s: int = 180,
    skill_names: list[str] | None = None,
    event_callback: Callable[[dict[str, Any]], None] | None = None,
) -> HTaskResult:
    payload = {"task": task, "mode": mode, "max_steps": max_steps, "max_time_s": max_time_s, "skill_names": skill_names or []}
    outer_timeout = max(45, max_time_s + 30)
    command = [sys.executable, "-m", "cloud_cua.h_runner_worker"]
    try:
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        if event_callback:
            stdout, stderr = _stream_worker(proc, payload, event_callback, outer_timeout)
        else:
            stdout, stderr = proc.communicate(json.dumps(payload), timeout=outer_timeout)
    except subprocess.TimeoutExpired:
        try:
            if proc.pid:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, text=True, timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        return HTaskResult(status="timed_out", summary=f"H browser session exceeded outer timeout of {outer_timeout}s and was stopped.")
    except Exception as exc:
        return HTaskResult(status="failed", summary=f"H worker failed to start: {type(exc).__name__}: {exc}", error=str(exc))
    if proc.returncode != 0:
        raw = ((stdout or "") + "\n" + (stderr or "")).strip()
        return HTaskResult(status="failed", summary=f"H worker failed with exit code {proc.returncode}.", raw=raw[-2000:])
    try:
        data = json.loads(stdout or "{}")
        return HTaskResult(**data)
    except Exception as exc:
        raw = ((stdout or "") + "\n" + (stderr or "")).strip()
        return HTaskResult(status="failed", summary=f"H worker returned invalid output: {exc}", raw=raw[-2000:])


def run_h_task_worker(
    payload: dict[str, Any],
    event_callback: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    result = _run_h_task_sdk(
        payload["task"],
        payload.get("mode", "vibe"),
        int(payload.get("max_steps", 20)),
        int(payload.get("max_time_s", 180)),
        list(payload.get("skill_names") or []),
        event_callback,
    )
    return json.dumps(asdict(result))


def summarize_h_event(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or event.get("event_type") or "trajectory_event")
    data = event.get("data")
    if isinstance(data, dict):
        interesting = []
        for key in ("status", "action", "name", "message", "url", "outcome"):
            value = data.get(key)
            if value not in {None, ""}:
                interesting.append(f"{key}={str(value)[:240]}")
        if interesting:
            return f"{event_type}: " + ", ".join(interesting)
    if data is not None and data != "":
        return f"{event_type}: {str(data)[:400]}"
    return event_type


def _event_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        return event.model_dump(mode="json")
    if isinstance(event, dict):
        return event
    return {"type": type(event).__name__, "data": str(event)}


def _stream_worker(
    proc: subprocess.Popen,
    payload: dict[str, Any],
    event_callback: Callable[[dict[str, Any]], None],
    timeout_seconds: int,
) -> tuple[str, str]:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(payload))
    proc.stdin.close()
    lines: queue.Queue[str | None] = queue.Queue()

    def read_stdout() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout_seconds
    result_json = ""
    finished = False
    while not finished:
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired(cmd="cloud_cua.h_runner_worker", timeout=timeout_seconds)
        try:
            line = lines.get(timeout=0.25)
        except queue.Empty:
            if proc.poll() is not None and not reader.is_alive():
                break
            continue
        if line is None:
            finished = True
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("kind") == "event" and isinstance(message.get("event"), dict):
            event_callback(message["event"])
        elif message.get("kind") == "result":
            result_json = json.dumps(message.get("result") or {})
    proc.wait(timeout=5)
    stderr = proc.stderr.read() if proc.stderr is not None else ""
    return result_json, stderr
