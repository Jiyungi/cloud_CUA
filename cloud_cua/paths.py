from __future__ import annotations

import os
from pathlib import Path


def home_dir() -> Path:
    return Path.home()


def user_config_dir() -> Path:
    return home_dir() / ".cloud-cua"


def credentials_path() -> Path:
    return user_config_dir() / "credentials.env"


def service_state_path() -> Path:
    return user_config_dir() / "service.json"


def service_stdout_path() -> Path:
    return user_config_dir() / "service.out.log"


def service_stderr_path() -> Path:
    return user_config_dir() / "service.err.log"


def browser_profile_dir() -> Path:
    return user_config_dir() / "chrome-profile"


def repo_runtime_dir(repo_path: str | Path) -> Path:
    return resolve_repo_path(repo_path) / ".cloud-cua"


def runs_dir(repo_path: str | Path) -> Path:
    return repo_runtime_dir(repo_path) / "runs"


def resolve_repo_path(repo_path: str | Path) -> Path:
    path = Path(repo_path).expanduser().resolve()
    if path.exists() or os.environ.get("CLOUD_CUA_CONTAINER") != "1":
        return path
    workspace = Path(os.environ.get("CLOUD_CUA_WORKSPACE", "/workspace")).resolve()
    if workspace.exists():
        return workspace
    return path


def default_dashboard_port() -> int:
    return int(os.environ.get("CLOUD_CUA_DASHBOARD_PORT", "3000"))


def default_api_port() -> int:
    return int(os.environ.get("CLOUD_CUA_API_PORT", "8765"))
