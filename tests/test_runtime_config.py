from __future__ import annotations

import json

from cloud_cua.aws_runtime_config import load_runtime_configuration, provision_aws_runtime_configuration


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
