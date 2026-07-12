from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cloud_cua.h_runner import run_h_task
from cloud_cua.aws_cleanup import cleanup_cloud_cua_aws_resources
from cloud_cua.codex_config import install_cloud_cua_mcp, upsert_mcp_server
from cloud_cua.deployments.aws_general import build_aws_deployment_plan
from cloud_cua.deployments.gcp_cloud_run import build_gcp_cloud_run_plan
from cloud_cua.packaging import build_shareable_package
from cloud_cua.reports import write_report
from cloud_cua.repo_analyzer import analyze_repo
from cloud_cua.run_store import RunStore
from cloud_cua.safety import detect_approval_triggers
from cloud_cua.verifier.base import VerifierResult
from cloud_cua.voice_router import classify_voice_command
from cloud_cua.voice_gradium import synthesize_tts


def test_voice_router_fast_lane_pause():
    route = classify_voice_command("pause")
    assert route.classification == "direct_control"
    assert route.route == "backend"
    assert route.action == "pause"


def test_voice_router_reasoning_not_h_cua():
    route = classify_voice_command("why Amplify?")
    assert route.classification == "reasoning_question"
    assert route.route == "codex"


def test_voice_router_cloud_action_needs_planning():
    route = classify_voice_command("click this in AWS")
    assert route.classification == "planned_cloud_action"
    assert route.route == "planner"


def test_run_store_redacts_secret(tmp_path: Path):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    store.append_event(run.run_id, "user", "command", "api_key=supersecret", {"token": "abc"})
    events = store.read_events(run.run_id)
    assert "supersecret" not in json.dumps(events)
    assert "abc" not in json.dumps(events)


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


def test_repo_analyzer_node_api_recommends_app_runner(tmp_path: Path):
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


def test_gcp_cloud_run_plan_supports_docker_repo(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    ctx = analyze_repo(tmp_path)
    plan = build_gcp_cloud_run_plan("demo-api", ctx)
    assert plan.supported is True
    assert plan.target == "gcp_cloud_run"
    assert plan.service_name.startswith("cloud-cua-demo-api")


def test_approval_trigger_detection_is_specific():
    triggers = detect_approval_triggers("Deploy public App Runner service with IAM role and GitHub OAuth")
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


def test_aws_cleanup_dry_run_uses_discovery(monkeypatch):
    monkeypatch.setattr(
        "cloud_cua.aws_cleanup.discover_cleanup_actions",
        lambda run_id=None: [],
    )
    result = cleanup_cloud_cua_aws_resources(dry_run=True)
    assert result.status == "passed"
    assert result.dry_run is True


def test_repo_analyzer_unknown_blocks(tmp_path: Path):
    ctx = analyze_repo(tmp_path)
    assert ctx.recommendation == "blocked_unknown_repo"


def test_gradium_tts_skips_without_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GRADIUM_API_KEY", raising=False)
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
    result = build_shareable_package(tmp_path, tmp_path / "out.zip")
    import zipfile

    with zipfile.ZipFile(result.path) as archive:
        names = set(archive.namelist())
    assert "cloud_cua/__init__.py" in names
    assert ".env" not in names
    assert ".kiro/local.md" not in names
    assert "readme files/notes.md" not in names


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
