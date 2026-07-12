from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .paths import credentials_path, user_config_dir


@dataclass(frozen=True)
class Credentials:
    hai_api_key_present: bool
    gradium_api_key_present: bool
    source: str


def validate_secret_value(name: str, value: str, *, required: bool = True) -> str:
    cleaned = value.strip()
    if not cleaned:
        if required:
            raise ValueError(f"{name} is required.")
        return ""
    if any(char.isspace() for char in cleaned):
        raise ValueError(f"{name} must not contain whitespace.")
    if len(cleaned) < 12 or cleaned.lower() in {"default", "changeme", "your-api-key", "placeholder"}:
        raise ValueError(f"{name} does not look like a usable API key.")
    return cleaned


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_secret_values(repo_path: str | Path | None = None) -> dict[str, str]:
    """Load secrets without logging them.

    User-level credentials win over process env, then local .env is allowed only
    for hack/dev convenience. Callers should never print returned values.
    """
    merged: dict[str, str] = {}
    merged.update({k: v for k, v in os.environ.items() if k in {"HAI_API_KEY", "GRADIUM_API_KEY"}})

    local_env = Path(repo_path or ".").resolve() / ".env"
    merged.update(_parse_env_file(local_env))

    user_env = credentials_path()
    merged.update(_parse_env_file(user_env))
    return merged


def inspect_credentials(repo_path: str | Path | None = None) -> Credentials:
    values = load_secret_values(repo_path)
    source = "missing"
    if credentials_path().exists():
        source = str(credentials_path())
    elif (Path(repo_path or ".").resolve() / ".env").exists():
        source = str(Path(repo_path or ".").resolve() / ".env")
    elif os.environ.get("HAI_API_KEY") or os.environ.get("GRADIUM_API_KEY"):
        source = "environment"
    return Credentials(
        hai_api_key_present=bool(values.get("HAI_API_KEY")),
        gradium_api_key_present=bool(values.get("GRADIUM_API_KEY")),
        source=source,
    )


def save_credentials(hai_api_key: str, gradium_api_key: str | None = None) -> Path:
    user_config_dir().mkdir(parents=True, exist_ok=True)
    hai = validate_secret_value("HAI_API_KEY", hai_api_key)
    gradium = validate_secret_value("GRADIUM_API_KEY", gradium_api_key or "", required=False)
    lines = ["# Cloud CUA local credentials. Do not commit this file.", f"HAI_API_KEY={hai}"]
    if gradium:
        lines.append(f"GRADIUM_API_KEY={gradium}")
    path = credentials_path()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path
