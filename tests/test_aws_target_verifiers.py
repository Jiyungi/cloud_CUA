from __future__ import annotations

import json

from cloud_cua.deployment_contract import DeploymentContract
from cloud_cua.verifier.aws import verify_amplify_run, verify_runtime_secret_references, verify_s3_static_run


def test_amplify_verifier_requires_exact_run_tag_branch_job_and_url(monkeypatch):
    def fake(command, timeout=30):
        joined = " ".join(command)
        if "list-apps" in joined:
            return {"apps": [{"appId": "app-1", "appArn": "arn:aws:amplify:us-east-1:123:apps/app-1", "name": "cloud-cua-demo", "defaultDomain": "example.amplifyapp.com"}]}
        if "list-tags-for-resource" in joined:
            return {"tags": {"cloud-cua-run": "run-1", "cloud-cua": "true"}}
        if "list-branches" in joined:
            return {"branches": [{"branchName": "main"}]}
        if "list-jobs" in joined:
            return {"jobSummaries": [{"jobId": "1", "status": "SUCCEED"}]}
        return {}

    monkeypatch.setattr("cloud_cua.verifier.aws._aws_json", fake)
    result = verify_amplify_run("run-1", "cloud-cua-demo")
    assert result.status == "passed"
    assert "https://main.example.amplifyapp.com" in result.summary


def test_s3_verifier_requires_run_tag_website_and_index(monkeypatch):
    def fake(command, timeout=30):
        joined = " ".join(command)
        if "list-buckets" in joined:
            return {"Buckets": [{"Name": "cloud-cua-demo-run-1"}]}
        if "get-bucket-tagging" in joined:
            return {"TagSet": [{"Key": "cloud-cua-run", "Value": "run-1"}]}
        if "get-bucket-website" in joined:
            return {"IndexDocument": {"Suffix": "index.html"}}
        if "head-object" in joined:
            return {"ContentLength": 100}
        return {}

    monkeypatch.setattr("cloud_cua.verifier.aws._aws_json", fake)
    result = verify_s3_static_run("run-1")
    assert result.status == "passed"
    assert "s3-website-us-east-1" in result.summary


def test_runtime_secret_verifier_never_decrypts_values(monkeypatch):
    commands = []

    def fake(command, timeout=30):
        commands.append(command)
        return {"Parameter": {"Name": "/cloud-cua/run-1/DATABASE_URL", "Type": "SecureString", "Version": 1}}

    monkeypatch.setattr("cloud_cua.verifier.aws._aws_json", fake)
    contract = DeploymentContract(
        "aws_ecs_express",
        runtime_secret_references={"DATABASE_URL": "arn:aws:ssm:us-east-1:123456789012:parameter/cloud-cua/run-1/DATABASE_URL"},
    )
    result = verify_runtime_secret_references(contract)
    assert result.status == "passed"
    assert all("--with-decryption" not in command for command in commands)
    assert "DATABASE_URL" in json.loads(result.summary)["references"][0]["name"]
