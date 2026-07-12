from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cloud_cua.aws_cli import aws_command
from cloud_cua.h_runner import HTaskResult, run_h_task
from cloud_cua.lessons import load_lesson_candidate, resolve_lesson_candidate, write_lesson_candidate
from cloud_cua.aws_cleanup import cleanup_cloud_cua_aws_resources
from cloud_cua.codex_config import install_cloud_cua_mcp, upsert_mcp_server
from cloud_cua.container_image import prepare_ecr_image, prepare_ecr_image_with_progress
from cloud_cua.credentials import save_credentials
from cloud_cua.deployment_contract import build_deployment_contract, load_contract, save_contract
from cloud_cua.deployment_milestones import build_ecs_submit_task, review_ecs_inspection, review_ecs_prepared_form
from cloud_cua.deployments.aws_general import build_aws_deployment_plan, build_general_aws_h_task
from cloud_cua.deployments.gcp_cloud_run import build_gcp_cloud_run_plan
from cloud_cua.packaging import build_shareable_package
from cloud_cua.paths import resolve_repo_path
from cloud_cua.reports import write_report
from cloud_cua.repo_analyzer import analyze_repo
from cloud_cua.resource_tracking import extract_resource_record
from cloud_cua.run_store import RunStore
from cloud_cua.safety import detect_approval_triggers
from cloud_cua.supervisor import review_h_result
from cloud_cua.verifier.base import VerifierResult
from cloud_cua.verifier.aws import verify_ecs_contract
from cloud_cua.voice_router import classify_voice_command
from cloud_cua.voice_gradium import synthesize_tts
from cloud_cua.voice_state import VoiceTurnStore


def test_voice_router_fast_lane_pause():
    route = classify_voice_command("pause")
    assert route.classification == "direct_control"
    assert route.route == "backend"
    assert route.action == "pause"


def test_voice_router_reasoning_not_h_cua():
    route = classify_voice_command("why this service?")
    assert route.classification == "reasoning_question"
    assert route.route == "codex"


def test_voice_router_cloud_action_needs_planning():
    route = classify_voice_command("click this in AWS")
    assert route.classification == "planned_cloud_action"
    assert route.route == "planner"


def test_voice_router_stop_is_contextual():
    assert classify_voice_command("stop", playback_active=True).action == "stop_speaking"
    assert classify_voice_command("stop", playback_active=False).classification == "unknown"
    assert classify_voice_command("stop deployment").action == "stop"
    assert classify_voice_command("it's cancel run.").action == "stop"
    assert classify_voice_command("please cancel the run").action == "stop"
    assert classify_voice_command("what happens if I cancel run?").action is None


def test_voice_router_supports_status_cleanup_and_exact_approval():
    assert classify_voice_command("resume deployment.").action == "resume"
    assert classify_voice_command("deployment status").action == "status"
    assert classify_voice_command("cleanup preview").action == "cleanup_preview"
    approval = classify_voice_command("Approve Create ECS service")
    assert approval.classification == "approval"
    assert approval.spoken_target == "Create ECS service"


def test_voice_turn_store_persists_bounded_sanitized_history(tmp_path: Path):
    store = VoiceTurnStore(tmp_path)
    first = store.create("run-1")
    store.update(first.turn_id, state="completed", transcript="api_key=secret-value", response="Done")
    for index in range(25):
        turn = store.create("run-1")
        store.update(turn.turn_id, state="completed", transcript=f"question {index}", response=f"answer {index}")

    assert len(store.list()) == 20
    assert "secret-value" not in store.path.read_text(encoding="utf-8")
    assert store.current().state == "completed"
    assert len(store.recent_conversation()) == 6


def test_run_store_redacts_secret(tmp_path: Path):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    store.append_event(run.run_id, "user", "command", "api_key=supersecret", {"token": "abc"})
    events = store.read_events(run.run_id)
    assert "supersecret" not in json.dumps(events)
    assert "abc" not in json.dumps(events)


def test_run_store_writes_run_atomically(tmp_path: Path):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    run.status = "running"
    store.save_run(run)
    assert store.load_run(run.run_id).status == "running"


def test_run_lock_recovers_dead_owner(tmp_path: Path):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    lock = store.run_dir(run.run_id) / "locks" / "voice-stream.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"time": "old", "pid": 99999999}), encoding="utf-8")

    assert store.acquire_lock(run.run_id, "voice-stream", stale_after_seconds=75) is True
    assert json.loads(lock.read_text(encoding="utf-8"))["pid"] == __import__("os").getpid()
    assert not store.run_path(run.run_id).with_suffix(".tmp").exists()


def test_credentials_reject_placeholders_and_write_outside_repo(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("cloud_cua.credentials.user_config_dir", lambda: tmp_path / "user-config")
    monkeypatch.setattr("cloud_cua.credentials.credentials_path", lambda: tmp_path / "user-config" / "credentials.env")
    try:
        save_credentials("placeholder")
        assert False, "placeholder key should be rejected"
    except ValueError:
        pass
    path = save_credentials("hai_live_test_key_123456")
    assert path.parent == tmp_path / "user-config"
    assert "hai_live_test_key_123456" in path.read_text(encoding="utf-8")


def test_repo_analyzer_vite_recommends_amplify(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build"}, "dependencies": {"vite": "^5.0.0", "react": "^18.0.0"}}),
        encoding="utf-8",
    )
    ctx = analyze_repo(tmp_path)
    assert ctx.framework == "vite"
    assert ctx.category == "frontend_static"
    assert ctx.recommendation == "aws_amplify"


def test_repo_analyzer_dockerfile_is_planned_ecs(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    ctx = analyze_repo(tmp_path)
    assert ctx.dockerfile is True
    assert ctx.recommendation == "aws_ecs_express"


def test_repo_analyzer_node_api_recommends_lambda(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"start": "node server.js"}, "dependencies": {"express": "^5.0.0"}}),
        encoding="utf-8",
    )
    ctx = analyze_repo(tmp_path)
    assert ctx.category == "node_api"
    assert ctx.recommendation == "aws_lambda"


def test_general_aws_plan_has_multiple_frontend_options(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"build": "vite build"}, "dependencies": {"vite": "^5.0.0"}}),
        encoding="utf-8",
    )
    ctx = analyze_repo(tmp_path)
    plan = build_aws_deployment_plan("demo", ctx)
    targets = [option.target for option in plan.options]
    assert plan.primary_target == "aws_amplify"
    assert "aws_s3_static_site" in targets
    assert plan.max_spend_usd == 5.0


def test_general_aws_plan_uses_ecs_express_for_docker(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM nginx:alpine\n", encoding="utf-8")
    ctx = analyze_repo(tmp_path)
    plan = build_aws_deployment_plan("demo-api", ctx)
    targets = [option.target for option in plan.options]
    assert plan.primary_target == "aws_ecs_express"
    assert "aws_app_runner_deprecated" in targets
    assert "App Runner is closed" in " ".join(plan.unknowns)


def test_deployment_contract_detects_container_port(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\nEXPOSE 4173/tcp\nCMD python -m app\n", encoding="utf-8")
    ctx = analyze_repo(tmp_path)
    contract = build_deployment_contract(tmp_path, ctx, "aws_ecs_express")
    assert contract.selected_container_port == 4173
    assert not contract.missing_facts


def test_deployment_contract_blocks_unknown_container_port(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\nCMD python -m app\n", encoding="utf-8")
    ctx = analyze_repo(tmp_path)
    contract = build_deployment_contract(tmp_path, ctx, "aws_ecs_express")
    assert contract.selected_container_port is None
    assert contract.missing_facts


def test_deployment_contract_round_trips_runtime_inputs(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM nginx\nEXPOSE 8080\n", encoding="utf-8")
    ctx = analyze_repo(tmp_path)
    contract = build_deployment_contract(tmp_path, ctx, "aws_ecs_express").with_runtime_inputs(
        run_id="run-1",
        skill_name="cloud-cua/aws-ecs-express",
        skill_hash="abc",
        autonomy_level=2,
        cloud_region="us-east-1",
        container_image_uri="123.dkr.ecr.us-east-1.amazonaws.com/app:run-1",
        ecr_repository="app",
        repo_name="demo",
    )
    path = save_contract(tmp_path / "contract.json", contract)
    loaded = load_contract(path)
    assert loaded.selected_container_port == 8080
    assert loaded.container_image_uri == contract.container_image_uri
    assert loaded.required_tags["cloud-cua-run"] == "run-1"


def test_milestone_checkpoint_requires_exact_contract(tmp_path: Path):
    from cloud_cua.deployment_checkpoints import load_milestone_checkpoint, save_milestone_checkpoint

    contract = _ecs_contract_fixture(tmp_path)
    path = tmp_path / "milestones.json"
    save_milestone_checkpoint(path, "inspect_ecs_express_form", contract, {"status": "completed"}, {"status": "clear"})

    assert load_milestone_checkpoint(path, "inspect_ecs_express_form", contract) is not None
    changed = contract.with_runtime_inputs(
        run_id="run-2",
        skill_name=contract.skill_name,
        skill_hash=contract.skill_hash,
        autonomy_level=contract.autonomy_level,
        cloud_region=contract.cloud_region,
        container_image_uri=contract.container_image_uri,
        ecr_repository=contract.ecr_repository,
        repo_name="demo",
    )
    assert load_milestone_checkpoint(path, "inspect_ecs_express_form", changed) is None


def test_milestone_checkpoint_ignores_moving_cost_clock_fields(tmp_path: Path):
    from dataclasses import replace
    from cloud_cua.deployment_checkpoints import load_milestone_checkpoint, save_milestone_checkpoint

    contract = _ecs_contract_fixture(tmp_path)
    path = tmp_path / "milestones.json"
    save_milestone_checkpoint(path, "prepare", contract, {"status": "completed"}, {"status": "clear"})
    refreshed = replace(contract, cost_limit_usd=10.0, estimated_hourly_usd=0.25, cost_deadline_at="later")

    assert load_milestone_checkpoint(path, "prepare", refreshed) is not None


def test_ecs_inspection_editable_default_becomes_correction(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM nginx\nEXPOSE 8080\n", encoding="utf-8")
    contract = build_deployment_contract(tmp_path, analyze_repo(tmp_path), "aws_ecs_express").with_runtime_inputs(
        run_id="run-1",
        skill_name="cloud-cua/aws-ecs-express",
        skill_hash="abc",
        autonomy_level=2,
        cloud_region="us-east-1",
        container_image_uri="example/image:tag",
        repo_name="demo",
    )
    result = HTaskResult(
        "completed",
        json.dumps(
            {
                "milestone": "inspect_ecs_express_form",
                "status": "observed",
                "service_target": "aws_ecs_express",
                "region": "us-east-1",
                "visible_defaults": {"container_port": 80},
                "can_apply_contract": True,
                "required_corrections": [],
                "blockers": [],
            }
        ),
    )
    review = review_ecs_inspection(result, contract)
    assert review.status == "clear"
    assert "container port" in review.corrections[0]


def test_ecs_inspection_blocks_when_form_cannot_apply_contract(tmp_path: Path):
    contract = _ecs_contract_fixture(tmp_path)
    result = HTaskResult(
        "completed",
        json.dumps(
            {
                "milestone": "inspect_ecs_express_form",
                "status": "blocked",
                "service_target": "aws_ecs_express",
                "region": "us-east-1",
                "visible_defaults": {"container_port": 80},
                "can_apply_contract": False,
                "required_corrections": [],
                "blockers": ["Container port control is disabled."],
            }
        ),
    )
    review = review_ecs_inspection(result, contract)
    assert review.status == "blocked"
    assert any("cannot be applied" in item for item in review.objections)


def test_ecs_inspection_keeps_nonblocking_notes_when_contract_is_applicable(tmp_path: Path):
    contract = _ecs_contract_fixture(tmp_path)
    result = HTaskResult(
        "completed",
        json.dumps(
            {
                "milestone": "inspect_ecs_express_form",
                "status": "observed",
                "service_target": "aws_ecs_express",
                "region": "us-east-1",
                "visible_defaults": {"container_port": 80, "health_check_path": "/"},
                "can_apply_contract": True,
                "required_corrections": [],
                "blockers": ["No cost estimate is visible."],
            }
        ),
    )
    review = review_ecs_inspection(result, contract)
    assert review.status == "clear"
    assert "Inspection note" in review.corrections[0]


def _ecs_contract_fixture(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM nginx\nEXPOSE 8080\n", encoding="utf-8")
    return build_deployment_contract(tmp_path, analyze_repo(tmp_path), "aws_ecs_express").with_runtime_inputs(
        run_id="run-1",
        skill_name="cloud-cua/aws-ecs-express",
        skill_hash="abc",
        autonomy_level=2,
        cloud_region="us-east-1",
        container_image_uri="123.dkr.ecr.us-east-1.amazonaws.com/app:run-1",
        repo_name="demo",
    )


def _fake_ecs_aws_json(
    command,
    timeout=30,
    *,
    image=None,
    port=8080,
    health="healthy",
    tagged=True,
    express_events=False,
    health_path="/",
    repo_tag="demo",
    secrets=None,
):
    joined = " ".join(command)
    if "resourcegroupstaggingapi" in joined:
        resources = [
            {
                "ResourceARN": "arn:aws:ecs:us-east-1:123456789012:service/default/cloud-cua-demo",
                "Tags": [
                    {"Key": "cloud-cua", "Value": "true"},
                    {"Key": "cloud-cua-run", "Value": "run-1"},
                    {"Key": "cloud-cua-repo", "Value": repo_tag},
                ],
            }
        ] if tagged else []
        return {"ResourceTagMappingList": resources}
    if "describe-services" in joined:
        return {
            "services": [
                {
                    "status": "ACTIVE",
                    "desiredCount": 1,
                    "runningCount": 1,
                    "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/demo:1",
                    "deployments": [{"status": "PRIMARY", "rolloutState": "COMPLETED"}],
                    "loadBalancers": [] if express_events else [{"targetGroupArn": "arn:aws:elasticloadbalancing:us-east-1:123:targetgroup/demo/abc"}],
                    "events": ([{"message": "registered 1 targets in (target-group arn:aws:elasticloadbalancing:us-east-1:123:targetgroup/demo/abc)"}] if express_events else []),
                }
            ]
        }
    if "describe-express-gateway-service" in joined:
        return {
            "service": {
                "status": {"statusCode": "ACTIVE"},
                "activeConfigurations": [
                    {
                        "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/demo:1",
                        "healthCheckPath": health_path,
                        "primaryContainer": {
                            "image": image or "123.dkr.ecr.us-east-1.amazonaws.com/app:run-1",
                            "containerPort": port,
                        },
                        "ingressPaths": [{"accessType": "PUBLIC", "endpoint": "demo.ecs.us-east-1.on.aws"}],
                    }
                ],
            }
        }
    if "describe-task-definition" in joined:
        return {
            "taskDefinition": {
                "containerDefinitions": [
                    {
                        "image": image or "123.dkr.ecr.us-east-1.amazonaws.com/app:run-1",
                        "portMappings": [{"containerPort": port}],
                        "secrets": [{"name": name, "valueFrom": value} for name, value in (secrets or {}).items()],
                    }
                ]
            }
        }
    if "describe-target-health" in joined:
        return {"TargetHealthDescriptions": [{"Target": {"Id": "task-1", "Port": port}, "TargetHealth": {"State": health}}]}
    return {}


def test_ecs_contract_verifier_rejects_image_mismatch(tmp_path: Path, monkeypatch):
    contract = _ecs_contract_fixture(tmp_path)
    monkeypatch.setattr("cloud_cua.verifier.aws._aws_json", lambda command, timeout=30: _fake_ecs_aws_json(command, timeout, image="wrong/image:tag"))
    result = verify_ecs_contract("run-1", contract)
    assert result.status == "failed"
    assert "image mismatch" in result.summary


def test_ecs_contract_verifier_rejects_port_mismatch(tmp_path: Path, monkeypatch):
    contract = _ecs_contract_fixture(tmp_path)
    monkeypatch.setattr("cloud_cua.verifier.aws._aws_json", lambda command, timeout=30: _fake_ecs_aws_json(command, timeout, port=80))
    result = verify_ecs_contract("run-1", contract)
    assert result.status == "failed"
    assert "port mismatch" in result.summary


def test_ecs_contract_verifier_rejects_unhealthy_target(tmp_path: Path, monkeypatch):
    contract = _ecs_contract_fixture(tmp_path)
    monkeypatch.setattr("cloud_cua.verifier.aws._aws_json", lambda command, timeout=30: _fake_ecs_aws_json(command, timeout, health="unhealthy"))
    result = verify_ecs_contract("run-1", contract)
    assert result.status == "failed"
    assert "not healthy" in result.summary


def test_ecs_contract_verifier_requires_exact_run_tag(tmp_path: Path, monkeypatch):
    contract = _ecs_contract_fixture(tmp_path)
    monkeypatch.setattr("cloud_cua.verifier.aws._aws_json", lambda command, timeout=30: _fake_ecs_aws_json(command, timeout, tagged=False))
    result = verify_ecs_contract("run-1", contract)
    assert result.status == "failed"
    assert "cloud-cua-run=run-1" in result.summary


def test_ecs_contract_verifier_finds_express_target_group_in_events(tmp_path: Path, monkeypatch):
    contract = _ecs_contract_fixture(tmp_path)
    monkeypatch.setattr(
        "cloud_cua.verifier.aws._aws_json",
        lambda command, timeout=30: _fake_ecs_aws_json(command, timeout, express_events=True),
    )

    result = verify_ecs_contract("run-1", contract)
    assert result.status == "passed"
    assert '"state": "healthy"' in result.summary


def test_ecs_contract_verifier_rejects_health_path_mismatch(tmp_path: Path, monkeypatch):
    contract = _ecs_contract_fixture(tmp_path)
    monkeypatch.setattr(
        "cloud_cua.verifier.aws._aws_json",
        lambda command, timeout=30: _fake_ecs_aws_json(command, timeout, health_path="/healthz"),
    )
    result = verify_ecs_contract("run-1", contract)
    assert result.status == "failed"
    assert "health path mismatch" in result.summary


def test_ecs_contract_verifier_rejects_required_tag_mismatch(tmp_path: Path, monkeypatch):
    contract = _ecs_contract_fixture(tmp_path)
    monkeypatch.setattr(
        "cloud_cua.verifier.aws._aws_json",
        lambda command, timeout=30: _fake_ecs_aws_json(command, timeout, repo_tag="other-repo"),
    )
    result = verify_ecs_contract("run-1", contract)
    assert result.status == "failed"
    assert "cloud-cua-repo" in result.summary


def test_ecs_contract_verifier_requires_exact_runtime_secret_binding(tmp_path: Path, monkeypatch):
    from dataclasses import replace

    reference = "arn:aws:ssm:us-east-1:123456789012:parameter/cloud-cua/run-1/DATABASE_URL"
    contract = replace(_ecs_contract_fixture(tmp_path), runtime_secret_references={"DATABASE_URL": reference})
    monkeypatch.setattr("cloud_cua.verifier.aws._aws_json", lambda command, timeout=30: _fake_ecs_aws_json(command, timeout))

    missing = verify_ecs_contract("run-1", contract)
    assert missing.status == "failed"
    assert "secret binding mismatch" in missing.summary

    monkeypatch.setattr(
        "cloud_cua.verifier.aws._aws_json",
        lambda command, timeout=30: _fake_ecs_aws_json(command, timeout, secrets={"DATABASE_URL": reference}),
    )
    matched = verify_ecs_contract("run-1", contract)
    assert matched.status == "passed"


def test_lesson_candidate_is_review_only_and_redacted(tmp_path: Path):
    path = write_lesson_candidate(
        tmp_path,
        run_id="run-1",
        affected_skill="cloud-cua/aws-ecs-express",
        failure="port mismatch token=secret-value",
        evidence={"api_key": "secret", "expected": 8080, "actual": 80},
        proposed_rule="Verify the contract port before creation.",
        required_test="Reject a mismatched task definition port.",
    )
    lesson = load_lesson_candidate(tmp_path)
    assert path.exists()
    assert lesson["status"] == "pending_review"
    assert lesson["evidence"]["api_key"] == "[REDACTED]"
    assert "secret-value" not in path.read_text(encoding="utf-8")


def test_lesson_candidate_can_be_resolved_without_deleting_evidence(tmp_path: Path):
    write_lesson_candidate(
        tmp_path,
        run_id="run-1",
        affected_skill="cloud-cua/aws-ecs-express",
        failure="Transient verifier mismatch.",
        evidence={"check": "failed"},
        proposed_rule="Use the native ECS Express response.",
        required_test="Verify managed target discovery.",
    )
    resolved = resolve_lesson_candidate(tmp_path, "Strict verification later passed.")

    assert resolved is not None
    assert resolved["status"] == "resolved"
    assert resolved["evidence"] == {"check": "failed"}


def test_resource_record_separates_console_and_app_urls():
    record = extract_resource_record(
        "run-123",
        "aws",
        "aws_ecs_express",
        "Console https://console.aws.amazon.com/ecs/v2/clusters/default and app https://abc.ecs.us-east-1.on.aws",
    )
    assert "https://console.aws.amazon.com/ecs/v2/clusters/default" in record.urls
    assert record.app_urls == ["https://abc.ecs.us-east-1.on.aws"]


def test_resource_record_normalizes_structured_app_host_without_scheme():
    record = extract_resource_record(
        "run-123",
        "aws",
        "aws_ecs_express",
        json.dumps({"public_app_url": "abc.ecs.us-east-1.on.aws", "console_url": "https://console.aws.amazon.com/ecs"}),
    )
    assert record.app_urls == ["https://abc.ecs.us-east-1.on.aws"]


def test_ecs_h_task_includes_contract_port_and_prepared_image_uri(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM nginx:alpine\nEXPOSE 8080\n", encoding="utf-8")
    ctx = analyze_repo(tmp_path)
    plan = build_aws_deployment_plan("demo-api", ctx)
    contract = build_deployment_contract(tmp_path, ctx, "aws_ecs_express")
    task = build_general_aws_h_task(
        "demo-api",
        ctx,
        plan,
        target="aws_ecs_express",
        run_id="run-123",
        prepared_inputs={"container_image_uri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/cloud-cua-demo:run-123", "container_port": "8080"},
        contract=contract,
    )
    assert "Prepared inputs from Codex/local repo tools" in task
    assert "123456789012.dkr.ecr.us-east-1.amazonaws.com/cloud-cua-demo:run-123" in task
    assert "selected_container_port: 8080" in task
    assert "Do not choose AWS App Runner" in task


def test_prepare_ecr_image_skips_without_dockerfile(tmp_path: Path):
    result = prepare_ecr_image(tmp_path, "demo", "run-123")
    assert result.status == "skipped"


def test_prepare_ecr_image_reports_progress_on_skip(tmp_path: Path):
    steps = []
    result = prepare_ecr_image_with_progress(tmp_path, "demo", "run-123", progress=lambda step, message, evidence: steps.append((step, message)))
    assert result.status == "skipped"
    assert steps[0][0] == "container_image_skipped"


def test_gcp_cloud_run_plan_supports_docker_repo(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    ctx = analyze_repo(tmp_path)
    plan = build_gcp_cloud_run_plan("demo-api", ctx)
    assert plan.supported is True
    assert plan.target == "gcp_cloud_run"
    assert plan.service_name.startswith("cloud-cua-demo-api")


def test_approval_trigger_detection_is_specific():
    triggers = detect_approval_triggers("Deploy public ECS service with IAM role and GitHub OAuth")
    codes = {trigger.code for trigger in triggers}
    assert {"paid_resources", "public_exposure", "broad_iam", "oauth"} <= codes


def test_codex_config_upsert_replaces_cloud_cua_only():
    text = '[mcp_servers.other]\ncommand = "x"\n'
    updated = upsert_mcp_server(text, "cloud-cua", "python.exe", ["-m", "cloud_cua.cli", "mcp"])
    assert "[mcp_servers.other]" in updated
    assert "[mcp_servers.cloud-cua]" in updated
    assert 'args = ["-m", "cloud_cua.cli", "mcp"]' in updated


def test_install_mcp_writes_config(tmp_path: Path):
    config = tmp_path / "config.toml"
    result = install_cloud_cua_mcp(config, python_executable="python", dry_run=False)
    text = config.read_text(encoding="utf-8")
    assert result.status == "passed"
    assert "[mcp_servers.cloud-cua]" in text
    assert 'command = "python"' in text
    assert 'args = ["-I", "-m", "cloud_cua.cli", "mcp"]' in text


def test_aws_cleanup_dry_run_uses_discovery(monkeypatch):
    monkeypatch.setattr(
        "cloud_cua.aws_cleanup.discover_cleanup_actions",
        lambda run_id=None: [],
    )
    result = cleanup_cloud_cua_aws_resources(dry_run=True)
    assert result.status == "passed"
    assert result.dry_run is True


def test_aws_cleanup_skips_inactive_express_service(monkeypatch):
    from cloud_cua.aws_cleanup import _action_from_arn

    monkeypatch.setattr(
        "cloud_cua.aws_cleanup._aws_json",
        lambda command: {"service": {"status": {"statusCode": "INACTIVE"}}}
        if "describe-express-gateway-service" in command
        else {},
    )
    arn = "arn:aws:ecs:us-east-1:123456789012:service/default/cloud-cua-demo"
    assert _action_from_arn(arn) is None


def test_aws_cleanup_skips_already_stopping_task(monkeypatch):
    from cloud_cua.aws_cleanup import _action_from_arn

    def fake_aws(command):
        if "describe-tasks" in command:
            return {"tasks": [{"lastStatus": "DEPROVISIONING", "desiredStatus": "STOPPED"}]}
        return {}

    monkeypatch.setattr("cloud_cua.aws_cleanup._aws_json", fake_aws)
    arn = "arn:aws:ecs:us-east-1:123456789012:task/default/task-1"
    assert _action_from_arn(arn) is None


def test_aws_cleanup_deletes_tagged_ssm_parameter():
    from cloud_cua.aws_cleanup import _action_from_arn

    action = _action_from_arn("arn:aws:ssm:us-east-1:123456789012:parameter/cloud-cua/run-1/DATABASE_URL")
    assert action is not None
    assert action.service == "ssm"
    assert action.resource == "/cloud-cua/run-1/DATABASE_URL"
    assert action.command[-2:] == ["--name", "/cloud-cua/run-1/DATABASE_URL"]


def test_aws_cleanup_handles_tagged_task_definitions_and_log_groups():
    from cloud_cua.aws_cleanup import _actions_from_arn

    task_actions = _actions_from_arn("arn:aws:ecs:us-east-1:123456789012:task-definition/cloud-cua-demo:1")
    log_actions = _actions_from_arn("arn:aws:logs:us-east-1:123456789012:log-group:/aws/ecs/cloud-cua-demo")

    assert [item.service for item in task_actions] == ["ecs-task-definition", "ecs-untag"]
    assert log_actions[0].service == "cloudwatch-logs"
    assert "delete-log-group" in log_actions[0].command


def test_aws_command_uses_cloud_cua_profile_when_available(monkeypatch):
    class FakeProc:
        returncode = 0
        stdout = "default\ncloud-cua-dev\n"
        stderr = ""

    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.setattr("cloud_cua.aws_cli.shutil.which", lambda name: "aws.exe")
    monkeypatch.setattr("cloud_cua.aws_cli.subprocess.run", lambda *args, **kwargs: FakeProc())

    assert aws_command(["sts", "get-caller-identity"]) == ["aws", "--profile", "cloud-cua-dev", "sts", "get-caller-identity"]


def test_repo_analyzer_unknown_blocks(tmp_path: Path):
    ctx = analyze_repo(tmp_path)
    assert ctx.recommendation == "blocked_unknown_repo"


def test_container_windows_path_maps_to_workspace(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("CLOUD_CUA_CONTAINER", "1")
    monkeypatch.setenv("CLOUD_CUA_WORKSPACE", str(workspace))

    assert resolve_repo_path(r"C:\Users\Person\project") == workspace


def test_gradium_tts_skips_without_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GRADIUM_API_KEY", raising=False)
    monkeypatch.setattr("cloud_cua.voice_gradium.load_secret_values", lambda *_args, **_kwargs: {})
    result = synthesize_tts("hello", str(tmp_path))
    assert result.status == "skipped"


def test_h_runner_outer_timeout(monkeypatch):
    class FakeProc:
        pid = 123
        returncode = None

        def communicate(self, *_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd="h", timeout=1)

        def kill(self):
            return None

    monkeypatch.setattr("cloud_cua.h_runner.subprocess.Popen", lambda *_args, **_kwargs: FakeProc())
    monkeypatch.setattr("cloud_cua.h_runner.subprocess.run", lambda *_args, **_kwargs: None)
    result = run_h_task("safe inspect", "vibe", max_steps=1, max_time_s=1)
    assert result.status == "timed_out"


def test_h_runner_rate_limit_message(monkeypatch):
    class FakeProc:
        pid = 123
        returncode = 0

        def communicate(self, *_args, **_kwargs):
            return (
                json.dumps(
                    {
                        "status": "blocked",
                        "summary": "H API rate limited this run while creating the local browser session.",
                        "raw": "HTTPStatusError 429",
                        "session_id": None,
                        "agent_view_url": None,
                        "outcome": None,
                        "error": "local web bridge failed",
                    }
                ),
                "",
            )

    monkeypatch.setattr("cloud_cua.h_runner.subprocess.Popen", lambda *_args, **_kwargs: FakeProc())
    result = run_h_task("safe inspect", "vibe", max_steps=1, max_time_s=1)
    assert result.status == "blocked"
    assert "rate limited" in result.summary


def test_h_runner_blocks_browser_takeover_in_docker(monkeypatch):
    monkeypatch.setenv("CLOUD_CUA_CONTAINER", "1")
    from cloud_cua.h_runner import _run_h_task_sdk

    result = _run_h_task_sdk("inspect only")
    assert result.status == "blocked"
    assert "host-local" in result.summary


def test_h_agent_includes_active_skill_name():
    from cloud_cua.h_runner import _inline_browser_agent

    agent = _inline_browser_agent("vibe", ["cloud-cua/aws-ecs-express"])
    assert agent["skills"] == ["cloud-cua/aws-ecs-express"]


def test_h_event_summary_keeps_action_without_large_payload():
    from cloud_cua.h_runner import summarize_h_event

    summary = summarize_h_event({"type": "agent_event", "data": {"action": "click Create service", "screenshot": "x" * 10000}})
    assert "click Create service" in summary
    assert len(summary) < 500


def test_h_supervisor_detects_agent_observation_errors():
    from cloud_cua.h_runner import _is_agent_error_event, _is_repeat_submit_intent, _is_submit_click_event, _supervisor_event

    event = {"type": "AgentEvent", "data": {"kind": "error_event", "error": "observation timed out"}}
    assert _is_agent_error_event(event) is True
    assert _is_agent_error_event({"type": "AgentEvent", "data": {"kind": "policy_event"}}) is False
    intervention = _supervisor_event("session-1", "stalled", "forcing_answer")
    assert intervention["data"]["session_id"] == "session-1"
    assert intervention["data"]["status"] == "forcing_answer"
    click = {
        "type": "AgentEvent",
        "data": {"kind": "tool_result", "tool_req": {"tool_name": "click_web", "args": {"element": "Create button"}}},
    }
    retry = {
        "type": "AgentEvent",
        "data": {"kind": "policy_event", "reasoning_content": "The previous click may not have registered. Click Create again."},
    }
    assert _is_submit_click_event(click) is True
    assert _is_repeat_submit_intent(retry) is True


def test_h_session_identity_is_saved_in_timeline(tmp_path: Path):
    from cloud_cua.orchestrator import Orchestrator

    orchestrator = Orchestrator(tmp_path)
    run = orchestrator.store.create_run("aws", "vibe")
    callback = orchestrator._h_event_callback(run.run_id, "inspect_ecs_express_form")
    callback(
        {
            "type": "HSessionStarted",
            "data": {"status": "running", "session_id": "session-1", "agent_view_url": "https://example.test/session-1"},
        }
    )

    event = orchestrator.store.read_events(run.run_id, limit=1)[0]
    assert event["evidence"]["session_id"] == "session-1"
    assert event["evidence"]["agent_view_url"].endswith("session-1")


def test_orphaned_chromedriver_cleanup_parses_stopped_ids(monkeypatch):
    from cloud_cua.h_runner import cleanup_orphaned_chromedrivers

    monkeypatch.setattr("cloud_cua.h_runner.os.name", "nt")
    monkeypatch.setattr(
        "cloud_cua.h_runner.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "123,456\n", ""),
    )
    assert cleanup_orphaned_chromedrivers() == [123, 456]


def test_h_runner_resolves_structured_ecs_schemas():
    from cloud_cua.h_runner import ECSCreationAnswer, ECSInspectionAnswer, ECSPreparedFormAnswer, _answer_schema_for

    assert _answer_schema_for("ecs_inspection") is ECSInspectionAnswer
    assert _answer_schema_for("ecs_prepared_form") is ECSPreparedFormAnswer
    assert _answer_schema_for("ecs_creation") is ECSCreationAnswer
    assert _answer_schema_for(None) is None


def test_prepared_ecs_form_must_match_contract(tmp_path: Path):
    contract = _ecs_contract_fixture(tmp_path)
    result = HTaskResult(
        "completed",
        json.dumps(
            {
                "milestone": "prepare_ecs_express_form",
                "status": "prepared",
                "image_uri": contract.container_image_uri,
                "container_port": 80,
                "health_check_path": "/",
                "tags": contract.required_tags,
                "ready_to_submit": True,
                "blockers": [],
            }
        ),
    )
    review = review_ecs_prepared_form(result, contract)
    assert review.status == "blocked"
    assert any("container port" in item for item in review.objections)


def test_ecs_submit_uses_checkpoint_and_forbids_second_click(tmp_path: Path):
    task = build_ecs_submit_task(_ecs_contract_fixture(tmp_path))
    assert "Trust the checkpoint" in task
    assert "never click Create a second time" in task


def test_supervisor_blocks_structured_h_failure(tmp_path: Path):
    contract = _ecs_contract_fixture(tmp_path)
    result = HTaskResult(
        "completed",
        json.dumps(
            {
                "milestone": "create_ecs_express_service",
                "status": "failed",
                "container_port": contract.selected_container_port,
                "public_app_url": None,
                "blockers": ["AWS rejected the service"],
            }
        ),
    )

    review = review_h_result(result, contract)
    assert review.status == "blocked"
    assert any("structured answer" in finding.message for finding in review.findings)


def test_verifier_result_redacts_saved_artifact(tmp_path: Path):
    result = VerifierResult(
        "secret_check",
        "failed",
        "fake --api-key=abc123",
        "token=abc123 AKIAABCDEFGHIJKLMNOP",
    ).save(tmp_path)
    text = Path(result.raw_path).read_text(encoding="utf-8")
    assert "abc123" not in text
    assert "AKIAABCDEFGHIJKLMNOP" not in text
    assert "[REDACTED]" in text


def test_shareable_package_excludes_local_state(tmp_path: Path):
    (tmp_path / "cloud_cua").mkdir()
    (tmp_path / "cloud_cua" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text("HAI_API_KEY=secret", encoding="utf-8")
    (tmp_path / ".kiro").mkdir()
    (tmp_path / ".kiro" / "local.md").write_text("local", encoding="utf-8")
    (tmp_path / "readme files").mkdir()
    (tmp_path / "readme files" / "notes.md").write_text("notes", encoding="utf-8")
    (tmp_path / "Conversation.md").write_text("local transcript", encoding="utf-8")
    (tmp_path / "DEPLOYMENT_REPORT.md").write_text("local run report", encoding="utf-8")
    result = build_shareable_package(tmp_path, tmp_path / "out.zip")
    import zipfile

    with zipfile.ZipFile(result.path) as archive:
        names = set(archive.namelist())
    assert "cloud_cua/__init__.py" in names
    assert ".env" not in names
    assert ".kiro/local.md" not in names
    assert "readme files/notes.md" not in names
    assert "Conversation.md" not in names
    assert "DEPLOYMENT_REPORT.md" not in names


def test_report_includes_approvals_and_verifiers(tmp_path: Path):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    store.append_event(run.run_id, "system", "approval", "Approval requested: Create app")
    from cloud_cua.approvals import create_approval

    create_approval(store.run_dir(run.run_id), "Create app", "Creates a cloud resource.", "high")
    VerifierResult("aws_identity", "passed", "aws sts get-caller-identity", "Account ok").save(store.verifier_dir(run.run_id))

    path = write_report(tmp_path, run.run_id)
    text = path.read_text(encoding="utf-8")
    assert "## Approvals" in text
    assert "Create app" in text
    assert "aws_identity" in text
