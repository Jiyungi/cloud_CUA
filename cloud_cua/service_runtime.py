from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .paths import default_dashboard_port, service_state_path, service_stderr_path, service_stdout_path, user_config_dir


@dataclass(frozen=True)
class ServiceState:
    pid: int
    port: int
    base_url: str
    token: str
    python: str
    started_at: float
    version: str = "0.1.0"

    def to_dict(self) -> dict:
        return asdict(self)


def load_service_state() -> ServiceState | None:
    path = service_state_path()
    if not path.exists():
        return None
    try:
        return ServiceState(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def save_service_state(state: ServiceState) -> Path:
    path = service_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    temporary.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def service_is_healthy(state: ServiceState, timeout: float = 1.5) -> bool:
    try:
        request = Request(f"{state.base_url}/health", headers={"X-Cloud-CUA-Token": state.token})
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return response.status == 200 and data.get("ok") is True and data.get("service") == "cloud-cua"
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return False


def ensure_service(*, python_executable: str | None = None, preferred_port: int | None = None) -> ServiceState:
    current = load_service_state()
    if current and service_is_healthy(current):
        return current

    user_config_dir().mkdir(parents=True, exist_ok=True)
    port = _available_port(preferred_port or default_dashboard_port())
    token = secrets.token_urlsafe(32)
    python = python_executable or _managed_runtime_python() or sys.executable
    environment = os.environ.copy()
    environment["CLOUD_CUA_SERVICE_TOKEN"] = token
    environment["CLOUD_CUA_DASHBOARD_PORT"] = str(port)
    stdout = service_stdout_path().open("a", encoding="utf-8")
    stderr = service_stderr_path().open("a", encoding="utf-8")
    kwargs: dict = {"stdout": stdout, "stderr": stderr, "env": environment, "cwd": str(user_config_dir())}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [python, "-I", "-m", "uvicorn", "cloud_cua.server:app", "--host", "127.0.0.1", "--port", str(port)],
        **kwargs,
    )
    stdout.close()
    stderr.close()
    state = ServiceState(proc.pid, port, f"http://127.0.0.1:{port}", token, python, time.time())
    save_service_state(state)
    for _ in range(150):
        if service_is_healthy(state, timeout=0.4):
            listener_pid = _listener_pid(port)
            if listener_pid and listener_pid != state.pid:
                state = ServiceState(listener_pid, port, state.base_url, token, python, state.started_at)
                save_service_state(state)
            return state
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    detail = ""
    try:
        detail = service_stderr_path().read_text(encoding="utf-8")[-2000:].strip()
    except OSError:
        pass
    suffix = f" Last error: {detail}" if detail else ""
    raise RuntimeError(f"Cloud CUA backend did not become healthy within 30 seconds. See {service_stderr_path()}.{suffix}")


def stop_service() -> dict:
    state = load_service_state()
    if not state:
        return {"status": "stopped", "summary": "No Cloud CUA service is registered."}
    if service_is_healthy(state):
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(state.pid), "/T", "/F"], capture_output=True, timeout=15)
            else:
                os.kill(state.pid, signal.SIGTERM)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        service_state_path().unlink()
    except FileNotFoundError:
        pass
    return {"status": "stopped", "summary": f"Stopped Cloud CUA service process {state.pid}."}


def service_status() -> dict:
    state = load_service_state()
    if not state:
        return {"status": "stopped", "healthy": False, "summary": "Cloud CUA service is not running."}
    healthy = service_is_healthy(state)
    return {
        "status": "running" if healthy else "stale",
        "healthy": healthy,
        "pid": state.pid,
        "port": state.port,
        "base_url": state.base_url,
        "summary": "Cloud CUA service is healthy." if healthy else "Cloud CUA service registration is stale.",
    }


def _available_port(preferred: int) -> int:
    for port in range(preferred, preferred + 25):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No available loopback port found from {preferred} through {preferred + 24}.")


def _managed_runtime_python() -> str | None:
    runtime = user_config_dir() / "runtime-venv"
    candidate = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(candidate) if candidate.is_file() else None


def _listener_pid(port: int) -> int | None:
    if os.name != "nt":
        return None
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"(Get-NetTCPConnection -LocalPort {port} -State Listen | Select-Object -First 1).OwningProcess",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        value = result.stdout.strip()
        return int(value) if result.returncode == 0 and value.isdigit() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
