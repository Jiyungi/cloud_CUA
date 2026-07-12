from __future__ import annotations

from cloud_cua.skill_registry import get_skill, load_skills, skill_for_target


def test_skill_registry_loads_unique_valid_skills():
    skills = load_skills()
    assert {skill.name for skill in skills} == {
        "cloud-cua/aws-amplify",
        "cloud-cua/aws-ecs-express",
        "cloud-cua/gcp-cloud-run",
    }
    assert len({skill.target for skill in skills}) == len(skills)
    assert all(len(skill.content_hash) == 64 for skill in skills)


def test_ecs_skill_requires_contract_facts_without_fixed_port():
    skill = skill_for_target("aws_ecs_express")
    assert skill is not None
    assert "selected_container_port" in skill.required_facts
    assert "container_image_uri" in skill.required_facts
    assert "3000" not in skill.body
    assert skill.autonomy_level == 2


def test_get_skill_can_omit_h_body_from_status_payload():
    skill = get_skill("cloud-cua/aws-ecs-express")
    payload = skill.to_dict(include_body=False)
    assert "body" not in payload
    assert payload["content_hash"] == skill.content_hash
