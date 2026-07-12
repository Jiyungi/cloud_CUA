from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from .run_store import now_iso, sanitize_obj, sanitize_text

SECRET_ENV_PREFIXES = ("AWS_", "GOOGLE_", "GCP_", "HAI_", "GRADIUM_")


@dataclass
class CodexVoiceJob:
    job_id: str
    turn_id: str
    status: str
    question: str
    answer: str = ""
    clarification_question: str = ""
    recommended_action: str = ""
    needs_repo_change: bool = False
    error: str = ""
    created_at: str = ""
    updated_at: str = ""


class CodexVoiceStore:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.path = run_dir / "codex-voice-jobs.json"

    def create(self, turn_id: str, question: str) -> CodexVoiceJob:
        now = now_iso()
        job = CodexVoiceJob(uuid4().hex, turn_id, "queued", sanitize_text(question), created_at=now, updated_at=now)
        jobs = self.list()
        jobs.append(job)
        self._save(jobs[-20:])
        return job

    def update(self, job_id: str, **changes) -> CodexVoiceJob:
        jobs = self.list()
        for job in jobs:
            if job.job_id != job_id:
                continue
            for key, value in changes.items():
                if hasattr(job, key):
                    setattr(job, key, sanitize_text(value) if isinstance(value, str) else value)
            job.updated_at = now_iso()
            self._save(jobs)
            return job
        raise KeyError(f"Codex voice job not found: {job_id}")

    def list(self) -> list[CodexVoiceJob]:
        if not self.path.exists():
            return []
        try:
            return [CodexVoiceJob(**item) for item in json.loads(self.path.read_text(encoding="utf-8"))]
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return []

    def current(self) -> CodexVoiceJob | None:
        jobs = self.list()
        return jobs[-1] if jobs else None

    def _save(self, jobs: list[CodexVoiceJob]) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps([asdict(item) for item in jobs], indent=2), encoding="utf-8")
        temporary.replace(self.path)


def build_codex_voice_prompt(question: str, mode: str, context: dict, conversation: list[dict]) -> str:
    detail_requested = any(marker in question.lower() for marker in ("more detail", "explain more", "in depth", "compare", "what does that mean"))
    limit = 180 if detail_requested else (35 if mode == "teach" else 60)
    safe_context = sanitize_obj(context)
    safe_conversation = sanitize_obj(conversation[-6:])
    return f"""You are the read-only Cloud CUA deployment teacher and planner.
Answer the user's question using only repository facts, the deployment run, H observations, verifier evidence, and cost data supplied below.
Use plain language. In Teach mode, explain only the major decision and do not narrate clicks.
Keep the answer within {limit} words. If a missing fact prevents a correct answer, put one concise question in clarification_question.
Never claim that a deployment succeeded unless verifier evidence proves it.
Never output or request secret values. Never instruct H directly and never execute cloud actions.
Return only the required JSON object.

Mode: {mode}
Question: {sanitize_text(question)}
Recent conversation: {json.dumps(safe_conversation, ensure_ascii=True)}
Run context: {json.dumps(safe_context, ensure_ascii=True)}
"""


def codex_output_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "clarification_question": {"type": "string"},
            "recommended_action": {"type": "string"},
            "needs_repo_change": {"type": "boolean"},
        },
        "required": ["answer", "clarification_question", "recommended_action", "needs_repo_change"],
        "additionalProperties": False,
    }


def enforce_answer_limit(answer: str, question: str, mode: str) -> str:
    expanded = any(marker in question.lower() for marker in ("more detail", "explain more", "in depth", "compare", "what does that mean"))
    limit = 180 if expanded else (35 if mode == "teach" else 60)
    words = answer.split()
    if len(words) <= limit:
        return answer.strip()
    return " ".join(words[:limit]).rstrip(" ,;:") + "..."


class CodexVoiceManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen] = {}

    def run(self, repo_path: Path, run_dir: Path, turn_id: str, question: str, mode: str, context: dict, conversation: list[dict], timeout_s: int = 90) -> CodexVoiceJob:
        store = CodexVoiceStore(run_dir)
        current = store.current()
        if current and current.status in {"queued", "running"}:
            return current
        job = store.create(turn_id, question)
        codex = shutil.which("codex")
        if not codex:
            return store.update(job.job_id, status="failed", error="Codex CLI is not installed or not available in PATH.")

        schema_path = run_dir / "codex-voice-output.schema.json"
        output_path = run_dir / f"codex-voice-{job.job_id}.json"
        schema_path.write_text(json.dumps(codex_output_schema(), indent=2), encoding="utf-8")
        prompt = build_codex_voice_prompt(question, mode, context, conversation)
        command = [
            codex,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "-C",
            str(repo_path),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-",
        ]
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith(SECRET_ENV_PREFIXES)
            and key.upper() not in {"AWS_PROFILE", "AWS_REGION", "CLOUD_CUA_SERVICE_TOKEN"}
        }
        store.update(job.job_id, status="running")
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                command,
                cwd=str(repo_path),
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            with self._lock:
                self._processes[job.job_id] = process
            _, stderr = process.communicate(prompt, timeout=timeout_s)
            if process.returncode != 0:
                message = (stderr or "Codex voice worker failed.").strip()[-600:]
                return store.update(job.job_id, status="failed", error=message)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            answer = enforce_answer_limit(str(payload.get("answer", "")).strip(), question, mode)
            clarification = str(payload.get("clarification_question", "")).strip()
            if not answer and not clarification:
                raise ValueError("Codex returned neither an answer nor a clarification question.")
            return store.update(
                job.job_id,
                status="completed",
                answer=answer,
                clarification_question=clarification,
                recommended_action=str(payload.get("recommended_action", "")).strip(),
                needs_repo_change=bool(payload.get("needs_repo_change", False)),
            )
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return store.update(job.job_id, status="timed_out", error=f"Codex did not answer within {timeout_s} seconds.")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return store.update(job.job_id, status="failed", error=f"Codex voice worker failed: {exc}")
        finally:
            with self._lock:
                self._processes.pop(job.job_id, None)
            try:
                output_path.unlink()
            except (FileNotFoundError, PermissionError):
                pass
            elapsed_ms = int((time.monotonic() - started) * 1000)
            try:
                current_job = store.current()
                if current_job and current_job.job_id == job.job_id:
                    store.update(job.job_id, updated_at=now_iso())
            except Exception:
                pass

    def cancel(self, run_dir: Path) -> CodexVoiceJob | None:
        store = CodexVoiceStore(run_dir)
        job = store.current()
        if not job or job.status not in {"queued", "running"}:
            return job
        with self._lock:
            process = self._processes.get(job.job_id)
        if process and process.poll() is None:
            process.kill()
        return store.update(job.job_id, status="cancelled", error="Codex voice job cancelled by user.")


_MANAGER = CodexVoiceManager()


def get_codex_voice_manager() -> CodexVoiceManager:
    return _MANAGER
