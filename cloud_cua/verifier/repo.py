from __future__ import annotations

from pathlib import Path

from .base import VerifierResult, run_command


def verify_git_diff(repo_path: str | Path) -> VerifierResult:
    return run_command("repo_git_status", ["git", "status", "--short"], timeout=15, cwd=str(Path(repo_path).resolve()))
