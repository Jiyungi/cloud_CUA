from __future__ import annotations

import zipfile
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", ".cloud-cua", ".kiro", ".pytest_cache", "cloud_cua.egg-info", "readme files", "dist", "artifacts"}
EXCLUDED_SUFFIXES = {".pyc", ".log"}
EXCLUDED_FILES = {".env", "Conversation.md", "DEPLOYMENT_REPORT.md"}


@dataclass(frozen=True)
class PackageResult:
    status: str
    path: str
    files: int
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


def build_shareable_package(root: str | Path, output: str | Path | None = None) -> PackageResult:
    project_root = Path(root).resolve()
    out_path = Path(output).resolve() if output else project_root / "dist" / "cloud-cua-shareable.zip"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wheel = _build_wheel(project_root) if (project_root / "pyproject.toml").exists() else None
    count = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(project_root.rglob("*")):
            if path == out_path or not path.is_file():
                continue
            rel = path.relative_to(project_root)
            if _excluded(rel):
                continue
            archive.write(path, rel.as_posix())
            count += 1
        if wheel:
            archive.write(wheel, f"wheel/{wheel.name}")
            count += 1
    return PackageResult("passed", str(out_path), count, f"Created shareable package with {count} files.")


def _build_wheel(project_root: Path) -> Path:
    wheel_dir = project_root / "dist" / "wheels"
    if wheel_dir.exists():
        shutil.rmtree(wheel_dir)
    wheel_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(project_root), "--no-deps", "--wheel-dir", str(wheel_dir)],
        check=True,
        text=True,
        capture_output=True,
        timeout=180,
    )
    wheels = sorted(wheel_dir.glob("cloud_cua-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"Expected one Cloud CUA wheel, found {len(wheels)} in {wheel_dir}.")
    return wheels[0]


def _excluded(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & EXCLUDED_DIRS:
        return True
    if rel.name in EXCLUDED_FILES:
        return True
    if rel.suffix in EXCLUDED_SUFFIXES:
        return True
    return False
