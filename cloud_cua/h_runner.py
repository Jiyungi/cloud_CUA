from __future__ import annotations

import json
import os
import subprocess
import sys
import queue
import threading
import time
import traceback
from uuid import uuid4
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import asdict
from typing import Any

from pydantic import BaseModel, Field

from .credentials import load_secret_values
from .h_admin import cleanup_h_session, get_h_quota
from .mode_policy import policy_for
from .models import Mode
from .paths import user_config_dir


@dataclass(frozen=True)
class HTaskResult:
    status: str
    summary: str
    raw: str = ""
    session_id: str | None = None
    agent_view_url: str | None = None
    outcome: str | None = None
    error: str | None = None


class HSessionStalled(RuntimeError):
    """Raised when a hosted H session stops producing a bounded result."""


class ECSVisibleDefaults(BaseModel):
    image_uri: str | None = None
    container_port: int | None = None
    health_check_path: str | None = None
    public_exposure: str | None = None
    iam_scope: str | None = None
    estimated_cost: str | None = None


class ECSInspectionAnswer(BaseModel):
    milestone: str
    status: str
    service_target: str
    region: str | None = None
    visible_defaults: ECSVisibleDefaults = Field(default_factory=ECSVisibleDefaults)
    required_inputs_visible: list[str] | None = None
    can_apply_contract: bool
    required_corrections: list[str] | None = None
    blockers: list[str] | None = None
    console_url: str | None = None


class ECSCreationAnswer(BaseModel):
    milestone: str
    status: str
    region: str | None = None
    service_name: str | None = None
    service_arn: str | None = None
    task_definition_arn: str | None = None
    image_uri: str | None = None
    container_port: int | None = None
    target_health: str | None = None
    public_app_url: str | None = None
    console_url: str | None = None
    created_resources: list[str] | None = None
    blockers: list[str] | None = None
    assumptions: list[str] | None = None


class ECSPreparedFormAnswer(BaseModel):
    milestone: str
    status: str
    image_uri: str | None = None
    container_port: int | None = None
    health_check_path: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    ready_to_submit: bool
    blockers: list[str] | None = None
    console_url: str | None = None


class AWSBrowserIdentityAnswer(BaseModel):
    milestone: str
    status: str
    account_id: str | None = None
    account_alias: str | None = None
    console_url: str | None = None
    blockers: list[str] | None = None


class S3CreationAnswer(BaseModel):
    milestone: str
    status: str
    bucket_name: str | None = None
    region: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    website_enabled: bool = False
    public_app_url: str | None = None
    console_url: str | None = None
    blockers: list[str] | None = None


class AmplifyInspectionAnswer(BaseModel):
    milestone: str
    status: str
    region: str | None = None
    manual_deploy_available: bool = False
    s3_source_available: bool = False
    blockers: list[str] | None = None
    console_url: str | None = None


class AmplifyPreparedAnswer(BaseModel):
    milestone: str
    status: str
    app_name: str | None = None
    branch_name: str | None = None
    artifact_reference: str | None = None
    ready_to_submit: bool = False
    submitted: bool = False
    blockers: list[str] | None = None
    console_url: str | None = None


class AmplifyCreationAnswer(BaseModel):
    milestone: str
    status: str
    app_id: str | None = None
    app_name: str | None = None
    branch_name: str | None = None
    deployment_status: str | None = None
    public_app_url: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    console_url: str | None = None
    blockers: list[str] | None = None


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
    answer_schema_name: str | None = None,
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
    owned_session_id: str | None = None
    try:
        orphaned_drivers = cleanup_orphaned_chromedrivers()
        if orphaned_drivers and event_callback:
            event_callback(
                {
                    "type": "LocalBridgeCleanup",
                    "data": {"status": "finished", "message": f"Stopped {len(orphaned_drivers)} orphaned ChromeDriver process(es) before H startup."},
                }
            )
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

        result = None
        for attempt in (1, 2):
            try:
                client = Client(api_key=api_key)
                create_params = {
                    "agent": _inline_browser_agent(mode, skill_names),
                    "messages": full_task,
                    "max_steps": max_steps,
                    "max_time_s": max_time_s,
                    "queue": False,
                }
                answer_schema = _answer_schema_for(answer_schema_name)
                if event_callback:
                    handle = client.start_session(**create_params, answer_schema=answer_schema)
                    owned_session_id = handle.id
                    event_callback(
                        {
                            "type": "HSessionStarted",
                            "data": {
                                "status": "running",
                                "session_id": handle.id,
                                "agent_view_url": getattr(handle, "agent_view_url", None),
                            },
                        }
                    )
                    for event in handle.stream(wait_for_seconds=5, until="settled", timeout_seconds=max_time_s + 60):
                        event_callback(_event_dict(event))
                    result = handle.wait_for_completion(wait_for_seconds=5, timeout_seconds=60, include_events=True)
                else:
                    result = client.run_session(
                        **create_params,
                        answer_schema=answer_schema,
                        wait_for_seconds=5,
                        timeout_seconds=max_time_s + 60,
                        include_events=True,
                    )
                break
            except Exception as exc:
                if attempt == 1 and "local web bridge" in str(exc).lower():
                    stopped = cleanup_orphaned_chromedrivers()
                    if event_callback:
                        event_callback(
                            {
                                "type": "LocalBridgeRetry",
                                "data": {
                                    "status": "retrying",
                                    "message": f"H local bridge startup failed; cleared {len(stopped)} orphaned driver(s) and will retry once.",
                                },
                            }
                        )
                    continue
                raise
        if result is None:
            raise RuntimeError("H session did not return a result after local bridge retry.")
        owned_session_id = result.id
        if result.outcome in {"blocked", "infeasible"}:
            status = "blocked"
        elif result.status in {"completed", "idle"}:
            status = "completed"
        else:
            status = str(result.status)
        if result.answer is None:
            answer = ""
        elif hasattr(result.answer, "model_dump"):
            answer = json.dumps(result.answer.model_dump(mode="json"))
        else:
            answer = str(result.answer)
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
        if owned_session_id:
            try:
                cleanup_h_session(owned_session_id)
            except Exception:
                pass
        cleanup_orphaned_chromedrivers()


def run_h_task(
    task: str,
    mode: Mode = "vibe",
    max_steps: int = 20,
    max_time_s: int = 180,
    skill_names: list[str] | None = None,
    event_callback: Callable[[dict[str, Any]], None] | None = None,
    answer_schema_name: str | None = None,
) -> HTaskResult:
    lock_token = _acquire_local_browser_lock()
    if not lock_token:
        return HTaskResult(
            status="blocked",
            summary="Another Cloud CUA run already owns the host-local H browser bridge. Finish or cancel that H job before retrying.",
        )
    payload = {
        "task": task,
        "mode": mode,
        "max_steps": max_steps,
        "max_time_s": max_time_s,
        "skill_names": skill_names or [],
        "answer_schema_name": answer_schema_name,
    }
    outer_timeout = max(45, max_time_s + 30)
    command = [sys.executable, "-m", "cloud_cua.h_runner_worker"]
    proc = None
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
            event_callback({"type": "HWorkerStarted", "data": {"status": "running", "worker_pid": proc.pid}})
        if event_callback:
            stdout, stderr = _stream_worker(proc, payload, event_callback, outer_timeout)
        else:
            stdout, stderr = proc.communicate(json.dumps(payload), timeout=outer_timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        return HTaskResult(status="timed_out", summary=f"H browser session exceeded outer timeout of {outer_timeout}s and was stopped.")
    except HSessionStalled as exc:
        _kill_process_tree(proc)
        return HTaskResult(status="timed_out", summary=str(exc))
    except Exception as exc:
        return HTaskResult(status="failed", summary=f"H worker failed to start: {type(exc).__name__}: {exc}", error=str(exc))
    finally:
        _release_local_browser_lock(lock_token)
    if proc.returncode != 0:
        raw = ((stdout or "") + "\n" + (stderr or "")).strip()
        return HTaskResult(status="failed", summary=f"H worker failed with exit code {proc.returncode}.", raw=raw[-2000:])
    try:
        data = json.loads(stdout or "{}")
        return HTaskResult(**data)
    except Exception as exc:
        raw = ((stdout or "") + "\n" + (stderr or "")).strip()
        return HTaskResult(status="failed", summary=f"H worker returned invalid output: {exc}", raw=raw[-2000:])


def _acquire_local_browser_lock() -> str | None:
    path = user_config_dir() / "h-local-browser.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex
    for _ in range(2):
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                owner = json.loads(path.read_text(encoding="utf-8"))
                if _pid_alive(int(owner.get("pid", 0))):
                    return None
                path.unlink()
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                try:
                    path.unlink()
                except OSError:
                    return None
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "token": token}, handle)
        return token
    return None


def _release_local_browser_lock(token: str) -> None:
    path = user_config_dir() / "h-local-browser.lock"
    try:
        owner = json.loads(path.read_text(encoding="utf-8"))
        if owner.get("token") == token:
            path.unlink()
    except (OSError, json.JSONDecodeError):
        return


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except (AttributeError, OSError):
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


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
        payload.get("answer_schema_name"),
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
    stderr_lines: list[str] = []

    def read_stdout() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()

    def read_stderr() -> None:
        if proc.stderr is not None:
            for line in proc.stderr:
                stderr_lines.append(line)

    stderr_reader = threading.Thread(target=read_stderr, daemon=True)
    stderr_reader.start()
    deadline = time.monotonic() + timeout_seconds
    last_event_at = time.monotonic()
    session_id: str | None = None
    intervention_at: float | None = None
    submit_clicked = False
    duplicate_guard_sent = False
    structured_milestone = bool(payload.get("answer_schema_name"))
    result_json = ""
    finished = False
    while not finished:
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired(cmd="cloud_cua.h_runner_worker", timeout=timeout_seconds)
        if structured_milestone and session_id and intervention_at is None and time.monotonic() - last_event_at >= 75:
            reason = "H produced no trajectory event for 75 seconds during a bounded milestone."
            event_callback(_supervisor_event(session_id, reason, "forcing_answer"))
            _intervene_h_session(session_id, reason)
            intervention_at = time.monotonic()
        if intervention_at is not None and time.monotonic() - intervention_at >= 45:
            raise HSessionStalled(
                "H session remained unresponsive for 45 seconds after the supervisor requested a final structured answer; the local worker was stopped."
            )
        try:
            line = lines.get(timeout=0.25)
        except queue.Empty:
            if proc.poll() is not None:
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
            event = message["event"]
            last_event_at = time.monotonic()
            if event.get("type") == "HSessionStarted":
                data = event.get("data") or {}
                session_id = str(data.get("session_id") or "") or None
            event_callback(event)
            if _is_submit_click_event(event):
                submit_clicked = True
            if submit_clicked and not duplicate_guard_sent and session_id and _is_repeat_submit_intent(event):
                reason = "H proposed repeating a Create/Submit click after one submission attempt."
                event_callback(_supervisor_event(session_id, reason, "duplicate_submit_blocked"))
                _send_h_supervisor_message(
                    session_id,
                    "Cloud CUA supervisor: a Create/Submit click was already attempted in this milestone. "
                    "Do not click it again. Wait for or inspect the existing AWS response, then return the resource receipt or a precise blocker.",
                )
                duplicate_guard_sent = True
            if structured_milestone and session_id and intervention_at is None and _is_agent_error_event(event):
                reason = "H reported an agent/tool observation error during a bounded milestone."
                event_callback(_supervisor_event(session_id, reason, "forcing_answer"))
                _intervene_h_session(session_id, reason)
                intervention_at = time.monotonic()
        elif message.get("kind") == "result":
            result_json = json.dumps(message.get("result") or {})
    proc.wait(timeout=5)
    return result_json, "".join(stderr_lines)


def _is_agent_error_event(event: dict[str, Any]) -> bool:
    data = event.get("data")
    if isinstance(data, dict) and data.get("kind") == "error_event":
        return True
    return str(event.get("type", "")).lower() == "errorevent"


def _is_submit_click_event(event: dict[str, Any]) -> bool:
    data = event.get("data")
    if not isinstance(data, dict) or data.get("kind") != "tool_result":
        return False
    request = data.get("tool_req")
    if not isinstance(request, dict) or request.get("tool_name") != "click_web":
        return False
    args = request.get("args") if isinstance(request.get("args"), dict) else {}
    label = str(args.get("element") or "").lower()
    return "create" in label or "submit" in label


def _is_repeat_submit_intent(event: dict[str, Any]) -> bool:
    data = event.get("data")
    if not isinstance(data, dict) or data.get("kind") != "policy_event":
        return False
    text = f"{data.get('reasoning_content', '')} {data.get('content', '')}".lower()
    return ("click" in text and ("create" in text or "submit" in text) and any(word in text for word in ("again", "retry", "previous click")))


def _supervisor_event(session_id: str, reason: str, status: str) -> dict[str, Any]:
    return {
        "type": "SupervisorIntervention",
        "data": {"status": status, "session_id": session_id, "message": reason},
    }


def _intervene_h_session(session_id: str, reason: str) -> None:
    _send_h_supervisor_message(
        session_id,
        "Cloud CUA supervisor: stop the current action loop. "
        f"Reason: {reason} Return the required structured answer now using only directly observed facts. "
        "Report missing facts or blockers instead of guessing, and do not perform another browser action.",
        force_answer=True,
    )


def _send_h_supervisor_message(session_id: str, message: str, force_answer: bool = False) -> None:
    values = load_secret_values()
    api_key = values.get("HAI_API_KEY")
    if not api_key:
        return
    try:
        from hai_agents import Client

        handle = Client(api_key=api_key).session(session_id)
        handle.send_message(message)
        if force_answer:
            handle.force_answer()
    except Exception:
        return


def _kill_process_tree(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        if proc.pid and os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, text=True, timeout=10)
            return
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def cleanup_orphaned_chromedrivers() -> list[int]:
    if os.name != "nt":
        return []
    worker_pid = os.getpid()
    script = (
        "$stopped=@(); "
        "Get-CimInstance Win32_Process -Filter \"Name='chromedriver.exe'\" | ForEach-Object { "
        "$parent=Get-Process -Id $_.ParentProcessId -ErrorAction SilentlyContinue; "
        f"if ((-not $parent) -or ($_.ParentProcessId -eq {worker_pid})) {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $stopped += $_.ProcessId }} }}; "
        "$stopped -join ','"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=15,
        )
    except Exception:
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    return [int(item) for item in proc.stdout.strip().split(",") if item.strip().isdigit()]


def _answer_schema_for(name: str | None):
    return {
        "aws_browser_identity": AWSBrowserIdentityAnswer,
        "s3_creation": S3CreationAnswer,
        "amplify_inspection": AmplifyInspectionAnswer,
        "amplify_prepared": AmplifyPreparedAnswer,
        "amplify_creation": AmplifyCreationAnswer,
        "ecs_inspection": ECSInspectionAnswer,
        "ecs_prepared_form": ECSPreparedFormAnswer,
        "ecs_creation": ECSCreationAnswer,
    }.get(name)
