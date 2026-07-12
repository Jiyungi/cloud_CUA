from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from .aws_cli import aws_command, selected_aws_profile
from .browser_profile import find_chrome
from .codex_config import SERVER_NAME, codex_config_path, configured_mcp_command
from .credentials import inspect_credentials
from .h_admin import get_h_quota


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    summary: str


def run_doctor(repo_path: str | Path | None = None, *, include_network: bool = True) -> list[DoctorCheck]:
    repo = str(Path(repo_path or ".").resolve())
    container_mode = os.environ.get("CLOUD_CUA_CONTAINER") == "1"
    checks = [
        _python_check(),
        _command_check("node", ["node", "--version"]),
        _command_check("npm", ["npm", "--version"]),
        _command_check("aws_cli", ["aws", "--version"]),
        _aws_identity_check(),
        _command_check("gcloud", ["gcloud", "--version"], required=False),
        _chrome_check(required=not container_mode),
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
    command = aws_command(["sts", "get-caller-identity"])
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=30)
    except Exception as exc:
        return DoctorCheck("aws_identity", "failed", f"aws sts get-caller-identity failed: {type(exc).__name__}: {exc}")
    if proc.returncode != 0:
        return DoctorCheck("aws_identity", "failed", (proc.stderr or proc.stdout or "AWS identity check failed.").strip()[:500])
    profile = selected_aws_profile()
    profile_note = f" using profile {profile}" if profile else ""
    try:
        data = json.loads(proc.stdout)
        return DoctorCheck("aws_identity", "passed", f"Authenticated AWS account {data.get('Account', 'unknown')} as {data.get('Arn', 'unknown')}{profile_note}")
    except Exception:
        return DoctorCheck("aws_identity", "passed", f"AWS CLI identity is authenticated{profile_note}.")


def _chrome_check(*, required: bool = True) -> DoctorCheck:
    chrome = find_chrome()
    if not chrome:
        status = "failed" if required else "skipped"
        return DoctorCheck("chrome", status, "Chrome or Edge was not found. In Docker, use host-local mode for H browser takeover.")
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
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                source = "installed Chrome"
            except Exception:
                browser = playwright.chromium.launch(headless=True)
                source = "Playwright Chromium"
            browser.close()
    except Exception as exc:
        return DoctorCheck("playwright", "failed" if required else "skipped", f"Managed Playwright/Chrome launch failed: {type(exc).__name__}: {exc}")
    return DoctorCheck("playwright", "passed", f"Managed Python Playwright launched {source}.")


def _docker_check(*, required: bool) -> DoctorCheck:
    executable = shutil.which("docker")
    if not executable:
        return DoctorCheck("docker", "failed" if required else "skipped", "Docker is not installed or not in PATH.")
    version = subprocess.run([executable, "--version"], text=True, capture_output=True, timeout=20)
    if version.returncode != 0:
        return DoctorCheck("docker", "failed" if required else "skipped", (version.stdout or version.stderr or "Docker CLI check failed.").strip())
    daemon = subprocess.run([executable, "info", "--format", "{{.ServerVersion}}"], text=True, capture_output=True, timeout=20)
    server_version = daemon.stdout.strip()
    if daemon.returncode != 0 or not server_version:
        summary = (daemon.stderr or daemon.stdout or "Docker daemon is not reachable.").strip()
        return DoctorCheck("docker", "failed" if required else "skipped", f"Docker CLI is installed, but the daemon is not running: {summary[:220]}")
    return DoctorCheck("docker", "passed", f"{(version.stdout or '').strip()}; daemon {server_version}")


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
    configured = configured_mcp_command(text)
    if configured is None:
        return DoctorCheck("codex_mcp_config", "failed" if required else "skipped", f"{SERVER_NAME} is not installed in {path}.")
    command, args = configured
    try:
        proc = subprocess.run([command, *args, "--self-check"], text=True, capture_output=True, timeout=20)
    except Exception as exc:
        return DoctorCheck("codex_mcp_config", "failed", f"Configured MCP command cannot start: {type(exc).__name__}: {exc}")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "MCP self-check failed.").strip()[:400]
        return DoctorCheck("codex_mcp_config", "failed", detail)
    return DoctorCheck("codex_mcp_config", "passed", f"Configured MCP command starts from {command}.")
