from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from .aws_cli import aws_command
from .models import RepoContext
from .verifier.repo import verify_repository


@dataclass(frozen=True)
class StaticArtifactResult:
    status: str
    summary: str
    output_directory: str = ""
    files: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


STATIC_ROOT_EXCLUDES = {".git", ".cloud-cua", "node_modules", ".venv", "venv", "__pycache__"}


def prepare_static_artifact(
    repo_path: str | Path,
    context: RepoContext,
    staging_directory: str | Path | None = None,
) -> StaticArtifactResult:
    root = Path(repo_path).resolve()
    if not context.output_directory:
        return StaticArtifactResult("blocked", "No static build output directory was detected.")
    build_results = verify_repository(root, context)
    build = next((item for item in build_results if item.name == "repo_build"), None)
    if build and build.status not in {"passed", "skipped"}:
        return StaticArtifactResult("blocked", f"Static build failed: {build.summary}")
    output = (root / context.output_directory).resolve()
    if not output.is_dir() or (output != root and root not in output.parents):
        return StaticArtifactResult("blocked", f"Static output directory does not exist inside the repo: {output}")
    if output == root:
        output = _stage_static_root(root, staging_directory)
    files = sum(1 for path in output.rglob("*") if path.is_file())
    if files == 0 or not (output / "index.html").exists():
        return StaticArtifactResult("blocked", "Static output must contain index.html and at least one file.", str(output), files)
    return StaticArtifactResult("passed", f"Prepared {files} static artifact files.", str(output), files)


def _stage_static_root(root: Path, staging_directory: str | Path | None) -> Path:
    stage = Path(staging_directory).resolve() if staging_directory else Path(tempfile.mkdtemp(prefix="cloud-cua-static-"))
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    for source in root.rglob("*"):
        relative = source.relative_to(root)
        if not source.is_file() or any(part in STATIC_ROOT_EXCLUDES for part in relative.parts):
            continue
        if source.name == ".env" or source.name.startswith(".env."):
            continue
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return stage


def upload_static_artifact(output_directory: str | Path, bucket_name: str) -> StaticArtifactResult:
    output = Path(output_directory).resolve()
    command = aws_command(["s3", "sync", str(output), f"s3://{bucket_name}", "--delete", "--only-show-errors"])
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=600)
    except Exception as exc:
        return StaticArtifactResult("failed", f"S3 artifact upload failed: {type(exc).__name__}: {exc}", str(output))
    if proc.returncode != 0:
        return StaticArtifactResult("failed", (proc.stderr or proc.stdout or "S3 upload failed.").strip()[:1500], str(output))
    return StaticArtifactResult("passed", f"Uploaded static artifact to s3://{bucket_name}.", str(output), sum(1 for path in output.rglob("*") if path.is_file()))
