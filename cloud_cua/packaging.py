from __future__ import annotations

import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path


EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", ".cloud-cua", ".kiro", ".pytest_cache", "cloud_cua.egg-info", "readme files"}
EXCLUDED_SUFFIXES = {".pyc", ".log"}
EXCLUDED_FILES = {".env"}


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
    return PackageResult("passed", str(out_path), count, f"Created shareable package with {count} files.")


def _excluded(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & EXCLUDED_DIRS:
        return True
    if rel.name in EXCLUDED_FILES:
        return True
    if rel.suffix in EXCLUDED_SUFFIXES:
        return True
    return False
