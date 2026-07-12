from __future__ import annotations

import os
from pathlib import Path


def home_dir() -> Path:
    return Path.home()


def user_config_dir() -> Path:
    return home_dir() / ".cloud-cua"


def credentials_path() -> Path:
    return user_config_dir() / "credentials.env"


def browser_profile_dir() -> Path:
    return user_config_dir() / "chrome-profile"


def repo_runtime_dir(repo_path: str | Path) -> Path:
    return Path(repo_path).resolve() / ".cloud-cua"


def runs_dir(repo_path: str | Path) -> Path:
    return repo_runtime_dir(repo_path) / "runs"


def default_dashboard_port() -> int:
    return int(os.environ.get("CLOUD_CUA_DASHBOARD_PORT", "3000"))


def default_api_port() -> int:
    return int(os.environ.get("CLOUD_CUA_API_PORT", "8765"))

