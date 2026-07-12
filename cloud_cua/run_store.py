from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .models import Cloud, Event, Mode, Run
from .paths import resolve_repo_path, runs_dir

SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key\s*[=:]\s*)[^\s,;]+", re.I),
    re.compile(r"(secret\s*[=:]\s*)[^\s,;]+", re.I),
    re.compile(r"(token\s*[=:]\s*)[^\s,;]+", re.I),
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


def sanitize_text(value: str) -> str:
    text = value
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


def sanitize_obj(value):
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if "key" in k.lower() or "secret" in k.lower() or "token" in k.lower() else sanitize_obj(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_obj(v) for v in value]
    return value


class RunStore:
    def __init__(self, repo_path: str | Path):
        self.repo_path = resolve_repo_path(repo_path)
        self.root = runs_dir(self.repo_path)
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def run_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "run.json"

    def events_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "events.jsonl"

    def verifier_dir(self, run_id: str) -> Path:
        path = self.run_dir(run_id) / "verifier-results"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_run(self, cloud: Cloud, mode: Mode, dashboard_url: str | None = None) -> Run:
        run_id = new_run_id()
        created = now_iso()
        run = Run(
            run_id=run_id,
            repo_path=str(self.repo_path),
            cloud=cloud,
            mode=mode,
            dashboard_url=dashboard_url,
            created_at=created,
            updated_at=created,
        )
        self.run_dir(run_id).mkdir(parents=True, exist_ok=True)
        self.save_run(run)
        self.append_event(run_id, "system", "result", "Created Cloud CUA run.", {"cloud": cloud, "mode": mode})
        return run

    def save_run(self, run: Run) -> None:
        run.updated_at = now_iso()
        self.run_dir(run.run_id).mkdir(parents=True, exist_ok=True)
        self.run_path(run.run_id).write_text(json.dumps(asdict(run), indent=2), encoding="utf-8")

    def load_run(self, run_id: str) -> Run:
        data = json.loads(self.run_path(run_id).read_text(encoding="utf-8"))
        return Run(**data)

    def append_event(self, run_id: str, source: str, type_: str, message: str, evidence: dict | None = None) -> Event:
        event = Event(
            time=now_iso(),
            source=source,
            type=type_,
            message=sanitize_text(message),
            evidence=sanitize_obj(evidence or {}),
        )
        path = self.events_path(run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return event

    def read_events(self, run_id: str, limit: int = 100) -> list[dict]:
        path = self.events_path(run_id)
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        selected = lines[-limit:] if limit > 0 else lines
        return [json.loads(line) for line in selected if line.strip()]

    def list_runs(self) -> list[Run]:
        runs: list[Run] = []
        for run_file in sorted(self.root.glob("*/run.json"), reverse=True):
            try:
                runs.append(Run(**json.loads(run_file.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return runs
