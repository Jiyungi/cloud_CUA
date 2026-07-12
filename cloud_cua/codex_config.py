from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


SERVER_NAME = "cloud-cua"


@dataclass(frozen=True)
class MCPInstallResult:
    status: str
    config_path: str
    backup_path: str | None
    command: str
    args: list[str]
    summary: str
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "config_path": self.config_path,
            "backup_path": self.backup_path,
            "command": self.command,
            "args": self.args,
            "summary": self.summary,
            "dry_run": self.dry_run,
        }


def codex_config_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "config.toml"
    return Path.home() / ".codex" / "config.toml"


def install_cloud_cua_mcp(
    config_path: str | Path | None = None,
    *,
    python_executable: str | None = None,
    dry_run: bool = False,
) -> MCPInstallResult:
    path = Path(config_path).expanduser() if config_path else codex_config_path()
    command = python_executable or sys.executable
    args = ["-m", "cloud_cua.cli", "mcp"]
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = upsert_mcp_server(existing, SERVER_NAME, command, args)
    backup_path: Path | None = None

    if dry_run:
        return MCPInstallResult("passed", str(path), None, command, args, "Dry run only. Codex config was not changed.", True)

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and existing != updated:
        backup_path = path.with_suffix(path.suffix + ".cloud-cua.bak")
        shutil.copy2(path, backup_path)
    path.write_text(updated, encoding="utf-8")
    return MCPInstallResult(
        "passed",
        str(path),
        str(backup_path) if backup_path else None,
        command,
        args,
        f"Installed Codex MCP server '{SERVER_NAME}'. Restart Codex so it reloads MCP config.",
    )


def upsert_mcp_server(text: str, name: str, command: str, args: list[str]) -> str:
    lines = text.splitlines()
    section = f"[mcp_servers.{name}]"
    start = _find_section(lines, section)
    block = [section, f"command = {_toml_string(command)}", f"args = {_toml_array(args)}"]
    if start is None:
        prefix = "\n" if text and not text.endswith("\n") else ""
        trailer = "\n" if text else ""
        return f"{text}{prefix}{section}\n{block[1]}\n{block[2]}\n"

    end = start + 1
    while end < len(lines) and not (lines[end].startswith("[") and lines[end].endswith("]")):
        end += 1
    new_lines = lines[:start] + block + lines[end:]
    return "\n".join(new_lines).rstrip() + "\n"


def _find_section(lines: list[str], section: str) -> int | None:
    for index, line in enumerate(lines):
        if line.strip() == section:
            return index
    return None


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"
