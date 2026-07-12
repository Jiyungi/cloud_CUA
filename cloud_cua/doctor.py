from __future__ import annotations

import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .browser_profile import find_chrome
from .codex_config import SERVER_NAME, codex_config_path
from .credentials import inspect_credentials
from .h_admin import get_h_quota


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    summary: str


def run_doctor(repo_path: str | Path | None = None, *, include_network: bool = True) -> list[DoctorCheck]:
    repo = str(Path(repo_path or ".").resolve())
    checks = [
        _python_check(),
        _command_check("node", ["node", "--version"]),
        _command_check("npm", ["npm", "--version"]),
        _command_check("aws_cli", ["aws", "--version"]),
        _aws_identity_check(),
        _command_check("gcloud", ["gcloud", "--version"], required=False),
        _chrome_check(),
        _chrome_debug_check(required=False),
        _playwright_check(required=False),
        _docker_check(required=False),
        _credential_check(repo),
        _codex_mcp_config_check(required=False),
    ]
    if include_network:
        checks.append(_h_quota_check(repo))
    return checks


def run_doctor_dict(repo_path: str | Path | None = None, *, include_network: bool = True) -> list[dict]:
    return [asdict(check) for check in run_doctor(repo_path, include_network=include_network)]


def _python_check() -> DoctorCheck:
    version = ".".join(str(part) for part in sys.version_info[:3])
    if sys.version_info < (3, 11):
        return DoctorCheck("python", "failed", f"Python {version} found. Cloud CUA needs Python 3.11+.")
    return DoctorCheck("python", "passed", f"Python {version}")


def _command_check(name: str, command: list[str], *, required: bool = True) -> DoctorCheck:
    executable = shutil.which(command[0])
    if not executable:
        return DoctorCheck(name, "failed" if required else "skipped", f"{command[0]} not found in PATH.")
    try:
        proc = subprocess.run([executable, *command[1:]], text=True, capture_output=True, timeout=20)
    except Exception as exc:
        return DoctorCheck(name, "failed" if required else "skipped", f"{command[0]} check failed: {type(exc).__name__}: {exc}")
    output = (proc.stdout or proc.stderr or "").splitlines()
    summary = output[0] if output else f"{command[0]} exited {proc.returncode}"
    return DoctorCheck(name, "passed" if proc.returncode == 0 else "failed", summary[:300])


def _aws_identity_check() -> DoctorCheck:
    if not shutil.which("aws"):
        return DoctorCheck("aws_identity", "skipped", "AWS CLI is not installed.")
    try:
        proc = subprocess.run(["aws", "sts", "get-caller-identity"], text=True, capture_output=True, timeout=30)
    except Exception as exc:
        return DoctorCheck("aws_identity", "failed", f"aws sts get-caller-identity failed: {type(exc).__name__}: {exc}")
    if proc.returncode != 0:
        return DoctorCheck("aws_identity", "failed", (proc.stderr or proc.stdout or "AWS identity check failed.").strip()[:500])
    try:
        data = json.loads(proc.stdout)
        return DoctorCheck("aws_identity", "passed", f"Authenticated AWS account {data.get('Account', 'unknown')} as {data.get('Arn', 'unknown')}")
    except Exception:
        return DoctorCheck("aws_identity", "passed", "AWS CLI identity is authenticated.")


def _chrome_check() -> DoctorCheck:
    chrome = find_chrome()
    if not chrome:
        return DoctorCheck("chrome", "failed", "Chrome or Edge was not found.")
    return DoctorCheck("chrome", "passed", chrome)


def _chrome_debug_check(*, required: bool) -> DoctorCheck:
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        return DoctorCheck("chrome_debug_port", "passed", f"Remote debugging is reachable: {data.get('Browser', 'browser')}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return DoctorCheck(
            "chrome_debug_port",
            "failed" if required else "skipped",
            "Chrome remote debugging is not reachable on 127.0.0.1:9222. Use the dashboard Open cloud login button when running local browser control.",
        )


def _playwright_check(*, required: bool) -> DoctorCheck:
    if not shutil.which("node"):
        return DoctorCheck("playwright", "failed" if required else "skipped", "Node is required before checking Playwright.")
    script = "const p=require('playwright'); console.log(Boolean(p.chromium));"
    proc = subprocess.run(["node", "-e", script], text=True, capture_output=True, timeout=20)
    if proc.returncode != 0:
        return DoctorCheck("playwright", "failed" if required else "skipped", "Playwright node package is not installed. Run npm install.")
    return DoctorCheck("playwright", "passed", "Playwright package is available.")


def _docker_check(*, required: bool) -> DoctorCheck:
    if not shutil.which("docker"):
        return DoctorCheck("docker", "failed" if required else "skipped", "Docker is not installed or not in PATH.")
    proc = subprocess.run(["docker", "--version"], text=True, capture_output=True, timeout=20)
    status = "passed" if proc.returncode == 0 else ("failed" if required else "skipped")
    return DoctorCheck("docker", status, (proc.stdout or proc.stderr or "Docker check finished.").strip())


def _credential_check(repo_path: str) -> DoctorCheck:
    creds = inspect_credentials(repo_path)
    missing: list[str] = []
    if not creds.hai_api_key_present:
        missing.append("HAI_API_KEY")
    summary = f"source={creds.source}; HAI_API_KEY={creds.hai_api_key_present}; GRADIUM_API_KEY={creds.gradium_api_key_present}"
    return DoctorCheck("credentials", "failed" if missing else "passed", summary)


def _h_quota_check(repo_path: str) -> DoctorCheck:
    quota = get_h_quota(repo_path)
    if quota is None:
        return DoctorCheck("h_quota", "skipped", "HAI_API_KEY missing or H quota endpoint unavailable.")
    status = "passed" if quota.available is None or quota.available > 0 else "failed"
    return DoctorCheck("h_quota", status, f"limit={quota.limit} active={quota.active} available={quota.available}")


def _codex_mcp_config_check(*, required: bool) -> DoctorCheck:
    path = codex_config_path()
    if not path.exists():
        return DoctorCheck("codex_mcp_config", "failed" if required else "skipped", f"{path} does not exist.")
    text = path.read_text(encoding="utf-8", errors="replace")
    if f"[mcp_servers.{SERVER_NAME}]" not in text:
        return DoctorCheck("codex_mcp_config", "failed" if required else "skipped", f"{SERVER_NAME} is not installed in {path}.")
    return DoctorCheck("codex_mcp_config", "passed", f"{SERVER_NAME} is installed in {path}.")
