from __future__ import annotations

import json
import subprocess
from pathlib import Path

from cloud_cua.h_runner import run_h_task
from cloud_cua.reports import write_report
from cloud_cua.repo_analyzer import analyze_repo
from cloud_cua.run_store import RunStore
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
    assert ctx.recommendation == "aws_ecs_express_planned"


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
