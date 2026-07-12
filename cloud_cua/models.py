from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Mode = Literal["vibe", "teach", "expert"]
Cloud = Literal["aws", "gcp"]


@dataclass
class Run:
    run_id: str
    repo_path: str
    cloud: Cloud
    mode: Mode
    deployment_scope: str = "full"
    target: str = "unknown"
    status: str = "created"
    current_step: str = "created"
    dashboard_url: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Event:
    time: str
    source: str
    type: str
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class RepoContext:
    framework: str
    category: str
    package_manager: str
    build_command: str | None
    output_directory: str | None
    start_command: str | None
    dockerfile: bool
    env_vars: list[str]
    risks: list[str]
    recommendation: str
