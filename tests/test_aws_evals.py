from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from cloud_cua.aws_evals import (
    CASE_TYPES,
    build_h_eval_task,
    build_review_only_skill_seed,
    evaluate_aws_eval_submission,
    get_aws_eval_case,
    get_aws_eval_service,
    load_aws_eval_catalog,
)
from cloud_cua.aws_skill_generation import RULES_MARKER, materialize_aws_eval_skills
from cloud_cua.skill_registry import get_skill, load_skills


CATALOG = load_aws_eval_catalog()
ALL_CASE_IDS = [case.id for case in CATALOG.cases]


def _passing_submission(case_id: str) -> dict[str, object]:
    _service, case = get_aws_eval_case(case_id)
    status = {"complete": "completed", "block": "blocked", "recover": "recovered"}[case.expected_outcome]
    return {
        "case_id": case.id,
        "status": status,
        "facts": {key: "verified" for key in case.required_fact_keys},
        "warnings_detected": list(case.warning_ids),
        "actions_taken": [],
        "evidence": {key: "verified" for key in case.required_evidence_keys},
        "cleanup_evidence": {key: "verified" for key in case.cleanup_evidence_keys},
        "blockers": [],
    }


def test_catalog_has_fifty_services_and_three_case_types_each() -> None:
    catalog = load_aws_eval_catalog()
    assert len(catalog.services) == 50
    assert len(catalog.cases) == 150
    assert {"ec2", "s3", "ecr", "app-runner"} <= {service.id for service in catalog.services}
    for service in catalog.services:
        assert len(service.cases) == 3
        assert {case.case_type for case in service.cases} == CASE_TYPES


def test_app_runner_case_blocks_new_customers_and_recommends_ecs_express() -> None:
    service = get_aws_eval_service("app-runner")
    _service, case = get_aws_eval_case("app-runner-misconfiguration-trap")
    assert service.lifecycle == "restricted_new_customers"
    assert "April 30 2026" in service.lifecycle_note
    assert {"new_customer_restriction", "container_port_unknown"} <= set(case.warning_ids)
    assert "attempt_new_customer_creation" in case.forbidden_action_ids
    assert any("ECS Express Mode" in rule for rule in case.skill_rules)


def test_ecr_case_requires_downstream_container_port_and_never_guesses() -> None:
    _service, case = get_aws_eval_case("ecr-misconfiguration-trap")
    assert "downstream_container_port" in case.required_fact_keys
    assert "container_port_unknown" in case.warning_ids
    assert "guess_port_80" in case.forbidden_action_ids


def test_prompt_is_structured_and_contains_safety_contract() -> None:
    prompt = build_h_eval_task("s3-misconfiguration-trap", {"account_id": "123456789012"})
    assert "Return only structured JSON" in prompt
    assert '"warnings_detected"' in prompt
    assert '"cleanup_evidence"' in prompt
    assert "Do not infer missing values" in prompt


def test_complete_safe_submission_passes() -> None:
    result = evaluate_aws_eval_submission("ec2-guided-provision", _passing_submission("ec2-guided-provision"))
    assert result.passed is True
    assert result.score == 100
    assert result.objections == []


def test_missing_fact_and_forbidden_action_fail() -> None:
    case_id = "ecr-misconfiguration-trap"
    submission = _passing_submission(case_id)
    facts = dict(submission["facts"])  # type: ignore[arg-type]
    facts["downstream_container_port"] = "unknown"
    submission["facts"] = facts
    submission["actions_taken"] = ["guess_port_80"]
    result = evaluate_aws_eval_submission(case_id, submission)
    assert result.passed is False
    assert "downstream_container_port" in result.missing_facts
    assert result.forbidden_actions == ["guess_port_80"]


def test_nested_evidence_values_do_not_crash_missing_checks() -> None:
    submission = _passing_submission("s3-guided-provision")
    evidence = dict(submission["evidence"])  # type: ignore[arg-type]
    evidence[next(iter(evidence))] = {"resource_id": "verified"}
    submission["evidence"] = evidence
    assert evaluate_aws_eval_submission("s3-guided-provision", submission).passed is True


def test_generated_skill_is_review_only() -> None:
    seed = build_review_only_skill_seed("ecr")
    assert seed["status"] == "candidate_pending_review"
    assert seed["autonomy_level"] == 1
    assert "downstream_container_port" in seed["required_facts"]


@pytest.mark.parametrize("case_id", ALL_CASE_IDS)
def test_every_aws_eval_case_accepts_complete_contract_evidence(case_id: str) -> None:
    prompt = build_h_eval_task(case_id)
    result = evaluate_aws_eval_submission(case_id, _passing_submission(case_id))
    assert case_id in prompt
    assert result.passed is True
    assert result.score == 100


@pytest.mark.parametrize("case_id", ALL_CASE_IDS)
def test_every_aws_eval_case_fails_closed_on_an_unknown_required_fact(case_id: str) -> None:
    _service, case = get_aws_eval_case(case_id)
    submission = _passing_submission(case_id)
    facts = dict(submission["facts"])  # type: ignore[arg-type]
    facts[case.required_fact_keys[0]] = "unknown"
    submission["facts"] = facts
    result = evaluate_aws_eval_submission(case_id, submission)
    assert result.passed is False
    assert case.required_fact_keys[0] in result.missing_facts


def test_materialized_registry_covers_all_fifty_services_with_fifty_three_total_skills() -> None:
    skills = load_skills()
    by_name = {skill.name: skill for skill in skills}
    assert len(skills) == 53
    for service in CATALOG.services:
        assert by_name[service.skill_name].target == service.skill_target
    assert RULES_MARKER in get_skill("cloud-cua/aws-amplify").body


def test_skill_materialization_is_idempotent_and_preserves_existing_amplify(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "cloud_cua" / "skills" / "aws_amplify.yaml"
    shutil.copy2(source, tmp_path / source.name)
    first = materialize_aws_eval_skills(tmp_path)
    second = materialize_aws_eval_skills(tmp_path)
    assert len(first.created) == 49
    assert first.unchanged == ("cloud-cua/aws-amplify",)
    assert len(second.unchanged) == 50
    assert len(load_skills(tmp_path)) == 50
