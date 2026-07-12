from __future__ import annotations

from dataclasses import dataclass

from cloud_cua.h_skills import get_h_skill_status, sync_h_skills
from cloud_cua.skill_registry import get_skill, load_skills, skill_for_target


def test_skill_registry_loads_unique_valid_skills():
    skills = load_skills()
    assert {skill.name for skill in skills} == {
        "cloud-cua/aws-amplify",
        "cloud-cua/aws-ecs-express",
        "cloud-cua/aws-s3-static",
        "cloud-cua/gcp-cloud-run",
    }
    assert len({skill.target for skill in skills}) == len(skills)
    assert all(len(skill.content_hash) == 64 for skill in skills)


def test_ecs_skill_requires_contract_facts_without_fixed_port():
    skill = skill_for_target("aws_ecs_express")
    assert skill is not None
    assert "selected_container_port" in skill.required_facts
    assert "one-pass evidence checklist" in skill.body
    assert "Do not scroll back" in skill.body
    assert "container_image_uri" in skill.required_facts
    assert "3000" not in skill.body
    assert skill.autonomy_level == 2


def test_get_skill_can_omit_h_body_from_status_payload():
    skill = get_skill("cloud-cua/aws-ecs-express")
    payload = skill.to_dict(include_body=False)
    assert "body" not in payload
    assert payload["content_hash"] == skill.content_hash


@dataclass
class FakePage:
    items: list


class FakeSkillsClient:
    def __init__(self, items=None):
        self.items = list(items or [])
        self.created = []
        self.updated = []

    def list_skills(self, **_kwargs):
        return FakePage(self.items)

    def create_skill(self, **kwargs):
        self.created.append(kwargs)

    def update_skill(self, name_, **kwargs):
        self.updated.append((name_, kwargs))


class FailingSkillsClient(FakeSkillsClient):
    def create_skill(self, **kwargs):
        raise RuntimeError("provider unavailable")


class FakeClient:
    def __init__(self, items=None):
        self.skills = FakeSkillsClient(items)


def test_h_skill_sync_creates_missing_skill():
    client = FakeClient()
    report = sync_h_skills(names=["cloud-cua/aws-ecs-express"], client=client)
    assert report.status == "passed"
    assert report.skills[0].status == "created"
    assert client.skills.created[0]["name"] == "cloud-cua/aws-ecs-express"


def test_h_skill_sync_updates_changed_skill():
    client = FakeClient(
        [
            {
                "name": "cloud-cua/aws-ecs-express",
                "description": "old",
                "body": "old",
                "source": None,
                "url_pattern": None,
            }
        ]
    )
    report = sync_h_skills(names=["cloud-cua/aws-ecs-express"], client=client)
    assert report.skills[0].status == "updated"
    assert client.skills.updated[0][0] == "cloud-cua/aws-ecs-express"


def test_h_skill_status_is_read_only_when_remote_matches():
    skill = get_skill("cloud-cua/aws-ecs-express")
    client = FakeClient(
        [
            {
                "name": skill.name,
                "description": skill.description,
                "body": skill.body,
                "source": skill.source,
                "url_pattern": skill.url_pattern,
            }
        ]
    )
    report = get_h_skill_status(names=[skill.name], client=client)
    assert report.skills[0].status == "synced"
    assert not client.skills.created
    assert not client.skills.updated


def test_h_skill_sync_returns_blocked_report_on_provider_error():
    client = FakeClient()
    client.skills = FailingSkillsClient()
    report = sync_h_skills(names=["cloud-cua/aws-ecs-express"], client=client)
    assert report.status == "blocked"
    assert report.skills[0].status == "failed"
    assert "provider unavailable" in report.skills[0].message
