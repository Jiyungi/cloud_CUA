from __future__ import annotations

import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .aws_cli import selected_aws_profile


@dataclass(frozen=True)
class AmplifyArtifactResult:
    status: str
    summary: str
    archive_path: str = ""
    bucket_name: str = ""
    object_key: str = ""
    s3_uri: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def stage_amplify_artifact(
    run_dir: Path,
    output_directory: str | Path,
    repo_name: str,
    run_id: str,
    region: str,
    *,
    s3_client: Any | None = None,
) -> AmplifyArtifactResult:
    output = Path(output_directory).resolve()
    archive = run_dir / "amplify-artifact.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(output).as_posix())
    if not archive.exists() or archive.stat().st_size == 0:
        return AmplifyArtifactResult("blocked", "Amplify artifact archive is empty.")
    bucket = _bucket_name(repo_name, run_id)
    key = "amplify-artifact.zip"
    client = s3_client or _s3_client(region)
    try:
        create: dict = {"Bucket": bucket}
        if region != "us-east-1":
            create["CreateBucketConfiguration"] = {"LocationConstraint": region}
        try:
            client.create_bucket(**create)
        except Exception as exc:
            if "BucketAlreadyOwnedByYou" not in str(exc):
                raise
        client.put_bucket_ownership_controls(Bucket=bucket, OwnershipControls={"Rules": [{"ObjectOwnership": "BucketOwnerPreferred"}]})
        client.put_bucket_tagging(
            Bucket=bucket,
            Tagging={
                "TagSet": [
                    {"Key": "cloud-cua", "Value": "true"},
                    {"Key": "cloud-cua-run", "Value": run_id},
                    {"Key": "cloud-cua-repo", "Value": repo_name[:256]},
                    {"Key": "cloud-cua-purpose", "Value": "amplify-staging"},
                ]
            },
        )
        client.upload_file(
            str(archive),
            bucket,
            key,
            ExtraArgs={"ContentType": "application/zip", "ACL": "bucket-owner-full-control"},
        )
    except Exception as exc:
        return AmplifyArtifactResult("blocked", f"Could not stage Amplify artifact: {type(exc).__name__}: {exc}", str(archive), bucket, key)
    return AmplifyArtifactResult("passed", f"Staged Amplify artifact at s3://{bucket}/{key}.", str(archive), bucket, key, f"s3://{bucket}/{key}")


def _s3_client(region: str):
    import boto3

    profile = selected_aws_profile()
    session = boto3.Session(profile_name=profile, region_name=region) if profile else boto3.Session(region_name=region)
    return session.client("s3", region_name=region)


def _bucket_name(repo_name: str, run_id: str) -> str:
    repo = re.sub(r"[^a-z0-9-]+", "-", repo_name.lower()).strip("-")[:24] or "app"
    suffix = re.sub(r"[^a-z0-9]+", "", run_id.lower())[-12:]
    return f"cloud-cua-stage-{repo}-{suffix}"[:63].rstrip("-")
