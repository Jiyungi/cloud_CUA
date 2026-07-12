from __future__ import annotations

from pathlib import Path

from cloud_cua.agent_test_contract import load_agent_test_contract
from cloud_cua.orchestrator import Orchestrator
from cloud_cua.dashboard import render_dashboard


ROOT = Path(__file__).parents[1]


def test_receipt_split_contract_maps_fourteen_skills_and_keeps_two_explicit_gaps() -> None:
    contract = load_agent_test_contract(ROOT / "agent-test-projects" / "receipt-split")
    assert contract is not None
    assert contract.requires_backend_implementation is True
    assert len(contract.matched_skill_names) == 14
    assert contract.unmatched_services == ("Textract", "X-Ray")
    assert "cloud-cua/aws-amplify" in contract.matched_skill_names
    assert "cloud-cua/aws-eventbridge" in contract.matched_skill_names


def test_invoiceops_contract_maps_fifteen_skills_and_keeps_textract_explicit() -> None:
    contract = load_agent_test_contract(ROOT / "agent-test-projects" / "invoiceops")
    assert contract is not None
    assert len(contract.matched_skill_names) == 15
    assert contract.unmatched_services == ("Textract",)
    assert "cloud-cua/aws-step-functions" in contract.matched_skill_names


def test_fixture_run_defaults_to_honest_frontend_preview() -> None:
    repo = ROOT / "agent-test-projects" / "receipt-split"
    orchestrator = Orchestrator(repo)
    run = orchestrator.start_deployment()
    assert run["status"] == "waiting_for_login"
    assert run["target"] == "aws_amplify"
    assert run["deployment_scope"] == "frontend_preview"
    assert run["current_step"] == "frontend_preview_ready"
    result = orchestrator.run_aws_deployment_task(run["run_id"], target="aws_amplify")
    assert result["status"] == "blocked"
    assert "login" in result["summary"].lower()


def test_fixture_full_scope_blocks_before_login() -> None:
    repo = ROOT / "agent-test-projects" / "receipt-split"
    orchestrator = Orchestrator(repo)
    run = orchestrator.start_deployment(deployment_scope="full")
    assert run["status"] == "blocked"
    assert run["target"] == "aws_multi_service_application"
    assert run["current_step"] == "backend_implementation_required"
    result = orchestrator.run_aws_deployment_task(run["run_id"], target="aws_amplify")
    assert result["status"] == "blocked"
    assert "false success" in result["summary"]
    state = orchestrator.get_run_skill_state(run["run_id"])
    assert len(state["required_skills"]) == 14
    assert state["unmatched_services"] == ["Textract", "X-Ray"]


def test_dashboard_exposes_multi_service_skill_coverage() -> None:
    dashboard = render_dashboard()
    assert 'id="multiSkillPanel"' in dashboard
    assert 'id="requiredSkills"' in dashboard
    assert 'id="skillGaps"' in dashboard
