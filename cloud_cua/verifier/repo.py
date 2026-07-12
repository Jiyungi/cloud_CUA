from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path

from ..models import RepoContext
from .base import VerifierResult, run_command


def verify_git_diff(repo_path: str | Path) -> VerifierResult:
    return run_command("repo_git_status", ["git", "status", "--short"], timeout=15, cwd=str(Path(repo_path).resolve()))


def verify_repository(repo_path: str | Path, context: RepoContext, *, run_tests: bool = False) -> list[VerifierResult]:
    root = Path(repo_path).resolve()
    results = [verify_git_diff(root)]
    if context.build_command:
        results.append(_run_repo_command("repo_build", context.build_command, root, timeout=600))
    else:
        results.append(VerifierResult("repo_build", "skipped", "", "No deterministic build command was detected."))
    if run_tests:
        test_command = _test_command(root, context)
        if test_command:
            results.append(_run_repo_command("repo_tests", test_command, root, timeout=600))
        else:
            results.append(VerifierResult("repo_tests", "skipped", "", "No deterministic test command was detected."))
    return results


def _run_repo_command(name: str, command: str, root: Path, *, timeout: int) -> VerifierResult:
    try:
        args = shlex.split(command, posix=True)
    except ValueError as exc:
        return VerifierResult(name, "failed", command, f"Could not parse command: {exc}")
    if not args:
        return VerifierResult(name, "skipped", command, "Command was empty.")
    allowed = {"npm", "npm.cmd", "pnpm", "pnpm.cmd", "yarn", "yarn.cmd", "bun", "python", "python3", "pytest"}
    executable_name = Path(args[0]).name.lower()
    if executable_name not in allowed:
        return VerifierResult(name, "failed", command, f"Refused unrecognized repository command executable: {args[0]}")
    executable = shutil.which(args[0]) or shutil.which(executable_name)
    if not executable:
        return VerifierResult(name, "skipped", command, f"Required executable was not found: {args[0]}")
    return run_command(name, [executable, *args[1:]], timeout=timeout, cwd=str(root))


def _test_command(root: Path, context: RepoContext) -> str | None:
    package = root / "package.json"
    if package.exists() and context.package_manager:
        try:
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
        except (OSError, json.JSONDecodeError):
            scripts = {}
        if scripts.get("test"):
            manager = context.package_manager
            return f"{manager} test" if manager in {"npm", "yarn", "pnpm", "bun"} else None
    if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists() and (root / "tests").exists():
        return "python -m pytest"
    return None
