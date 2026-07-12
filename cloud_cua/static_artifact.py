from __future__ import annotations

import subprocess
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


def prepare_static_artifact(repo_path: str | Path, context: RepoContext) -> StaticArtifactResult:
    root = Path(repo_path).resolve()
    if not context.output_directory:
        return StaticArtifactResult("blocked", "No static build output directory was detected.")
    build_results = verify_repository(root, context)
    build = next((item for item in build_results if item.name == "repo_build"), None)
    if build and build.status not in {"passed", "skipped"}:
        return StaticArtifactResult("blocked", f"Static build failed: {build.summary}")
    output = (root / context.output_directory).resolve()
    if not output.is_dir() or root not in output.parents:
        return StaticArtifactResult("blocked", f"Static output directory does not exist inside the repo: {output}")
    files = sum(1 for path in output.rglob("*") if path.is_file())
    if files == 0 or not (output / "index.html").exists():
        return StaticArtifactResult("blocked", "Static output must contain index.html and at least one file.", str(output), files)
    return StaticArtifactResult("passed", f"Prepared {files} static artifact files.", str(output), files)


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
