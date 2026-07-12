from __future__ import annotations

import json
from pathlib import Path

from cloud_cua.codex_voice import CodexVoiceManager, CodexVoiceStore, build_codex_voice_prompt


def test_codex_voice_prompt_is_concise_and_redacts_secrets() -> None:
    prompt = build_codex_voice_prompt(
        "Why ECS?",
        "teach",
        {"target": "ecs", "api_key": "secret-value"},
        [{"question": "Earlier", "answer": "Because it is a container."}],
    )

    assert "within 35 words" in prompt
    assert "secret-value" not in prompt
    assert "[REDACTED]" in prompt


def test_codex_voice_prompt_allows_bounded_expansion() -> None:
    prompt = build_codex_voice_prompt("Explain more in depth", "teach", {}, [])
    assert "within 180 words" in prompt


def test_codex_voice_worker_is_read_only_ephemeral_and_scrubs_cloud_secrets(tmp_path: Path, monkeypatch) -> None:
    captured = {}

    class Process:
        returncode = 0

        def __init__(self, command, **kwargs):
            captured["command"] = command
            captured["env"] = kwargs["env"]
            self.command = command

        def communicate(self, prompt=None, timeout=None):
            captured["prompt"] = prompt
            captured["timeout"] = timeout
            output_path = Path(self.command[self.command.index("--output-last-message") + 1])
            output_path.write_text(
                json.dumps(
                    {
                        "answer": "ECS fits because the repository contains a container image.",
                        "clarification_question": "",
                        "recommended_action": "Continue with the ECS plan.",
                        "needs_repo_change": False,
                    }
                ),
                encoding="utf-8",
            )
            return "", ""

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "should-not-leak")
    monkeypatch.setenv("GRADIUM_API_KEY", "should-not-leak")
    monkeypatch.setattr("cloud_cua.codex_voice.shutil.which", lambda _name: "codex")
    monkeypatch.setattr("cloud_cua.codex_voice.subprocess.Popen", Process)

    manager = CodexVoiceManager()
    job = manager.run(tmp_path, tmp_path / "run", "turn-1", "Why ECS?", "teach", {"target": "ecs"}, [])

    assert job.status == "completed"
    assert job.answer.startswith("ECS fits")
    assert "--ephemeral" in captured["command"]
    assert "--ignore-user-config" in captured["command"]
    assert captured["command"][captured["command"].index("--sandbox") + 1] == "read-only"
    assert "AWS_ACCESS_KEY_ID" not in captured["env"]
    assert "GRADIUM_API_KEY" not in captured["env"]


def test_codex_voice_store_cancelled_job_is_persisted(tmp_path: Path) -> None:
    store = CodexVoiceStore(tmp_path)
    job = store.create("turn-1", "What happened?")
    updated = store.update(job.job_id, status="cancelled", error="Cancelled")
    assert updated.status == "cancelled"
    assert store.current().error == "Cancelled"
