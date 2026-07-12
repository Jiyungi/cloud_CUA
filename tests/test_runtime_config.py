from __future__ import annotations

import json

from cloud_cua.aws_runtime_config import load_runtime_configuration, provision_aws_runtime_configuration
from cloud_cua.cloud_identity import BrowserIdentityProof, save_browser_identity
from cloud_cua.deployment_contract import build_deployment_contract, save_contract
from cloud_cua.orchestrator import Orchestrator
from cloud_cua.repo_analyzer import analyze_repo
from cloud_cua.verifier.base import VerifierResult


class FakeSSM:
    def __init__(self):
        self.put_calls = []
        self.tag_calls = []

    def put_parameter(self, **kwargs):
        self.put_calls.append(kwargs)

    def add_tags_to_resource(self, **kwargs):
        self.tag_calls.append(kwargs)


def test_runtime_secrets_are_replaced_by_ssm_references(tmp_path):
    values = {"DATABASE_URL": "postgres://user:secret@example/db"}
    client = FakeSSM()
    result = provision_aws_runtime_configuration(
        tmp_path,
        "run-123",
        "demo",
        ["DATABASE_URL"],
        values,
        {},
        region="us-east-1",
        account_id="123456789012",
        ssm_client=client,
    )
    saved = (tmp_path / "runtime-config.json").read_text(encoding="utf-8")
    assert result.status == "ready"
    assert result.reference_map()["DATABASE_URL"].startswith("arn:aws:ssm:us-east-1:123456789012:parameter/")
    assert "postgres://" not in saved
    assert "secret" not in saved
    assert values == {}
    assert client.put_calls[0]["Type"] == "SecureString"
    assert client.put_calls[0]["Tier"] == "Standard"


def test_runtime_config_excludes_public_frontend_names(tmp_path):
    status = load_runtime_configuration(tmp_path, ["VITE_API_URL", "DATABASE_URL"])
    assert status.public_build_names == ["VITE_API_URL"]
    assert status.missing_names == ["DATABASE_URL"]


def test_existing_ssm_reference_must_match_account_and_region(tmp_path):
    result = provision_aws_runtime_configuration(
        tmp_path,
        "run-123",
        "demo",
        ["DATABASE_URL"],
        {},
        {"DATABASE_URL": "/production/database-url"},
        region="us-east-1",
        account_id="123456789012",
        ssm_client=FakeSSM(),
    )
    assert result.reference_map()["DATABASE_URL"] == "arn:aws:ssm:us-east-1:123456789012:parameter/production/database-url"
    assert "DATABASE_URL" in json.loads((tmp_path / "runtime-config.json").read_text(encoding="utf-8"))["required_names"]


def test_runtime_endpoint_rejects_secrets_before_approved_configuration_gate(tmp_path):
    (tmp_path / ".env.example").write_text("DATABASE_URL=\n", encoding="utf-8")
    orchestrator = Orchestrator(tmp_path)
    run = orchestrator.store.create_run("aws", "vibe")
    values = {"DATABASE_URL": "must-not-persist"}

    result = orchestrator.configure_runtime(run.run_id, values, {})

    assert result["status"] == "blocked"
    assert values == {}
    assert not (orchestrator.store.run_dir(run.run_id) / "runtime-config.json").exists()


def test_runtime_endpoint_rechecks_browser_account_before_ssm(tmp_path, monkeypatch):
    (tmp_path / ".env.example").write_text("DATABASE_URL=\n", encoding="utf-8")
    orchestrator = Orchestrator(tmp_path)
    run = orchestrator.store.create_run("aws", "vibe")
    run.status = "waiting_for_configuration"
    run.current_step = "runtime_configuration_required"
    orchestrator.store.save_run(run)
    contract = build_deployment_contract(tmp_path, analyze_repo(tmp_path), "aws_ecs_express").with_runtime_inputs(
        run_id=run.run_id,
        skill_name="cloud-cua/aws-ecs-express",
        skill_hash="test",
        autonomy_level=2,
        cloud_region="us-east-1",
        repo_name="demo",
    )
    save_contract(orchestrator.store.contract_path(run.run_id), contract)
    save_browser_identity(
        orchestrator.store.run_dir(run.run_id) / "browser-identity.json",
        BrowserIdentityProof("matched", "123456789012", "999999999999", checked_at="now", message="stale mismatch"),
    )
    monkeypatch.setattr(
        "cloud_cua.orchestrator.verify_aws_identity",
        lambda: VerifierResult("aws_identity", "passed", "aws sts", '{"Account":"123456789012"}'),
    )
    values = {"DATABASE_URL": "must-not-persist"}

    result = orchestrator.configure_runtime(run.run_id, values, {})

    assert result["status"] == "blocked"
    assert "no longer matches" in result["message"]
    assert values == {}
