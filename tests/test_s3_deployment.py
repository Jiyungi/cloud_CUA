from __future__ import annotations

import json
from pathlib import Path

from cloud_cua.deployment_contract import DeploymentContract
from cloud_cua.deployments.s3_static import review_s3_creation, s3_bucket_name
from cloud_cua.h_runner import HTaskResult
from cloud_cua.models import RepoContext
from cloud_cua.static_artifact import prepare_static_artifact


def test_s3_bucket_name_is_unique_and_valid():
    name = s3_bucket_name("My Frontend App", "20260712T120000Z-abcdef12")
    assert name.startswith("cloud-cua-my-frontend-app-")
    assert len(name) <= 63


def test_s3_creation_must_match_contract():
    contract = DeploymentContract(
        "aws_s3_static_site",
        cloud_region="us-east-1",
        resource_name="cloud-cua-demo-abc",
        required_tags={"cloud-cua": "true", "cloud-cua-run": "run-1"},
    )
    result = HTaskResult(
        "completed",
        json.dumps(
            {
                "milestone": "create_s3_static_website",
                "status": "completed",
                "bucket_name": "cloud-cua-demo-abc",
                "region": "us-east-1",
                "tags": {"cloud-cua": "true", "cloud-cua-run": "run-1"},
                "website_enabled": True,
                "public_app_url": "http://cloud-cua-demo-abc.s3-website-us-east-1.amazonaws.com",
                "blockers": [],
            }
        ),
    )
    assert review_s3_creation(result, contract).status == "clear"


def test_static_artifact_requires_index_html(tmp_path):
    output = tmp_path / "dist"
    output.mkdir()
    context = RepoContext("static", "frontend_static", "", None, "dist", None, False, [], [], "aws_s3_static_site")
    blocked = prepare_static_artifact(tmp_path, context)
    assert blocked.status == "blocked"
    (output / "index.html").write_text("hello", encoding="utf-8")
    ready = prepare_static_artifact(tmp_path, context)
    assert ready.status == "passed"


def test_plain_static_root_is_staged_without_local_or_secret_files(tmp_path):
    (tmp_path / "index.html").write_text("<h1>ready</h1>", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=do-not-stage\n", encoding="utf-8")
    (tmp_path / ".cloud-cua" / "runs").mkdir(parents=True)
    (tmp_path / ".cloud-cua" / "runs" / "event.json").write_text("private", encoding="utf-8")
    context = RepoContext("static", "frontend_static", "unknown", None, ".", None, False, [], [], "aws_amplify")

    result = prepare_static_artifact(tmp_path, context, tmp_path / ".cloud-cua" / "staged")

    staged = Path(result.output_directory)
    assert result.status == "passed"
    assert (staged / "index.html").exists()
    assert not (staged / ".env").exists()
    assert not (staged / ".cloud-cua").exists()
