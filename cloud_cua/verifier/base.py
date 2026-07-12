from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class VerifierResult:
    name: str
    status: str
    command: str
    summary: str
    raw_path: str | None = None
    risk: str | None = None

    def save(self, directory: Path) -> "VerifierResult":
        directory.mkdir(parents=True, exist_ok=True)
        self.command = _redact(self.command)
        self.summary = _redact(self.summary)
        self.risk = _redact(self.risk) if self.risk else self.risk
        path = directory / f"{self.name}.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        self.raw_path = str(path)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return self


def _redact(value: str) -> str:
    redacted = re.sub(
        r"(?i)(api[_-]?key|secret|token|password|authorization|access[_-]?key)(\s*[=:]\s*)([^\s,\"']+)",
        r"\1\2[REDACTED]",
        value,
    )
    redacted = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA[REDACTED]", redacted)
    return redacted


def run_command(name: str, command: list[str], timeout: int = 30, cwd: str | None = None) -> VerifierResult:
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        return VerifierResult(name, "skipped", " ".join(command), f"Command not found: {command[0]}")
    except subprocess.TimeoutExpired:
        return VerifierResult(name, "failed", " ".join(command), "Command timed out.")
    output = (proc.stdout or proc.stderr or "").strip()
    summary = output[:1500] if output else f"Exit code {proc.returncode}"
    return VerifierResult(name, "passed" if proc.returncode == 0 else "failed", " ".join(command), summary)
