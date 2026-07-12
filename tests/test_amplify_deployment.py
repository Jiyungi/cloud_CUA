from __future__ import annotations

import json
import zipfile

from cloud_cua.amplify_artifact import stage_amplify_artifact
from cloud_cua.deployment_contract import DeploymentContract
from cloud_cua.deployments.amplify import review_amplify_creation, review_amplify_inspection, review_amplify_prepared
from cloud_cua.h_runner import HTaskResult


class FakeS3:
    def __init__(self):
        self.created = []
        self.uploaded = []

    def create_bucket(self, **kwargs):
        self.created.append(kwargs)

    def put_bucket_ownership_controls(self, **kwargs):
        pass

    def put_bucket_tagging(self, **kwargs):
        self.tags = kwargs

    def upload_file(self, *args, **kwargs):
        self.uploaded.append((args, kwargs))


def amplify_contract() -> DeploymentContract:
    return DeploymentContract(
        "aws_amplify",
        cloud_region="us-east-1",
        resource_name="cloud-cua-demo",
        branch_name="main",
        artifact_reference="s3://cloud-cua-stage-demo/artifact.zip",
    )


def test_amplify_artifact_zips_output_contents_and_stages_private_object(tmp_path):
    output = tmp_path / "dist"
    output.mkdir()
    (output / "index.html").write_text("hello", encoding="utf-8")
    client = FakeS3()
    result = stage_amplify_artifact(tmp_path, output, "demo", "run-123", "us-east-1", s3_client=client)
    assert result.status == "passed"
    with zipfile.ZipFile(result.archive_path) as bundle:
        assert bundle.namelist() == ["index.html"]
    assert client.uploaded
    assert client.tags["Tagging"]["TagSet"][1] == {"Key": "cloud-cua-run", "Value": "run-123"}


def test_amplify_three_milestones_require_contract_evidence():
    contract = amplify_contract()
    inspection = review_amplify_inspection(
        HTaskResult("completed", json.dumps({"manual_deploy_available": True, "s3_source_available": True, "region": "us-east-1", "blockers": []})),
        contract,
    )
    prepared = review_amplify_prepared(
        HTaskResult("completed", json.dumps({"app_name": "cloud-cua-demo", "branch_name": "main", "artifact_reference": contract.artifact_reference, "ready_to_submit": True, "submitted": False, "blockers": []})),
        contract,
    )
    created = review_amplify_creation(
        HTaskResult("completed", json.dumps({"app_id": "app-1", "app_name": "cloud-cua-demo", "branch_name": "main", "public_app_url": "https://main.example.amplifyapp.com", "blockers": []})),
        contract,
    )
    assert inspection.status == "clear"
    assert prepared.status == "clear"
    assert created.status == "clear"


def test_amplify_prepare_blocks_if_h_submitted_early():
    contract = amplify_contract()
    review = review_amplify_prepared(
        HTaskResult("completed", json.dumps({"app_name": contract.resource_name, "branch_name": "main", "artifact_reference": contract.artifact_reference, "ready_to_submit": True, "submitted": True})),
        contract,
    )
    assert review.status == "blocked"
