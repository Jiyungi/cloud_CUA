from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .approvals import approved as approval_is_approved
from .approvals import create_approval, decide_approval, load_approvals
from .browser_profile import launch_dedicated_browser
from .credentials import inspect_credentials
from .deployments.amplify import build_amplify_plan
from .h_runner import run_h_task
from .mode_policy import normalize_mode
from .models import Cloud, Mode
from .repo_analyzer import analyze_repo
from .reports import write_report
from .run_store import RunStore
from .verifier.aws import verify_amplify_apps, verify_aws_identity
from .verifier.gcp import verify_gcp_identity, verify_gcp_project
from .verifier.http import verify_http_url
from .verifier.playwright_check import verify_playwright_url
from .verifier.repo import verify_git_diff
from .voice_gradium import synthesize_tts
from .voice_router import classify_voice_command


class Orchestrator:
    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()
        self.store = RunStore(self.repo_path)

    def start_deployment(self, cloud: str = "aws", mode: str = "vibe") -> dict:
        mode_v = normalize_mode(mode)
        cloud_v: Cloud = "gcp" if cloud.lower() == "gcp" else "aws"
        run = self.store.create_run(cloud_v, mode_v)
        ctx = analyze_repo(self.repo_path)
        run.target = ctx.recommendation
        run.current_step = "repo_analyzed"
        run.status = "waiting_for_login"
        self.store.save_run(run)
        self.store.append_event(run.run_id, "system", "result", "Analyzed repo.", {"repo_context": asdict(ctx)})
        if ctx.recommendation == "aws_amplify":
            plan = build_amplify_plan(self.repo_path.name, ctx)
            self.store.append_event(run.run_id, "system", "plan", "Prepared AWS Amplify deployment plan.", {"amplify_plan": plan.to_dict()})
        creds = inspect_credentials(self.repo_path)
        self.store.append_event(
            run.run_id,
            "system",
            "result",
            "Checked local credential presence.",
            {"hai_api_key_present": creds.hai_api_key_present, "gradium_api_key_present": creds.gradium_api_key_present, "source": creds.source},
        )
        return asdict(run)

    def get_amplify_plan(self, run_id: str) -> dict:
        ctx = analyze_repo(self.repo_path)
        plan = build_amplify_plan(self.repo_path.name, ctx)
        self.store.append_event(run_id, "system", "plan", "Generated AWS Amplify plan.", {"amplify_plan": plan.to_dict()})
        return plan.to_dict()

    def get_status(self, run_id: str) -> dict:
        return asdict(self.store.load_run(run_id))

    def get_events(self, run_id: str, limit: int = 100) -> list[dict]:
        return self.store.read_events(run_id, limit)

    def set_mode(self, run_id: str, mode: str) -> dict:
        run = self.store.load_run(run_id)
        old = run.mode
        run.mode = normalize_mode(mode)
        self.store.save_run(run)
        self.store.append_event(run_id, "user", "mode_changed", f"User switched from {old} mode to {run.mode} mode.", {"from": old, "to": run.mode})
        return asdict(run)

    def open_browser_for_login(self, run_id: str) -> dict:
        run = self.store.load_run(run_id)
        result = launch_dedicated_browser(run.cloud)
        self.store.append_event(run_id, "system", "command", "Opened dedicated browser for manual cloud login.", result)
        return result

    def continue_after_login(self, run_id: str) -> dict:
        run = self.store.load_run(run_id)
        run.status = "running"
        run.current_step = "login_confirmed"
        self.store.save_run(run)
        self.store.append_event(run_id, "user", "approval", "User confirmed manual cloud login is complete.")
        identity = verify_aws_identity() if run.cloud == "aws" else verify_gcp_identity()
        saved = identity.save(self.store.verifier_dir(run_id))
        self.store.append_event(run_id, "verifier", "result", "Verified cloud identity after manual login.", {"result": asdict(saved)})
        if saved.status != "passed":
            run.status = "blocked"
            run.current_step = "identity_verifier_failed"
            self.store.save_run(run)
            self.store.append_event(run_id, "system", "result", "Cloud identity verifier failed. H CUA modification tasks are blocked.")
        return asdict(run)

    def pause(self, run_id: str) -> dict:
        run = self.store.load_run(run_id)
        run.status = "paused"
        self.store.save_run(run)
        self.store.append_event(run_id, "user", "command", "Paused deployment.")
        return asdict(run)

    def resume(self, run_id: str) -> dict:
        run = self.store.load_run(run_id)
        run.status = "running"
        self.store.save_run(run)
        self.store.append_event(run_id, "user", "command", "Resumed deployment.")
        return asdict(run)

    def run_h_inspect(self, run_id: str, task: str | None = None) -> dict:
        run = self.store.load_run(run_id)
        if run.status == "paused":
            return {"status": "skipped", "summary": "Run is paused."}
        if run.status == "waiting_for_login":
            return {"status": "blocked", "summary": "Manual cloud login is required before H CUA can run."}
        task_text = task or "Inspect the visible cloud console page and report what page is visible. Do not create, edit, or delete anything."
        self.store.append_event(run_id, "h_cua", "command", task_text, {"mode": run.mode})
        result = run_h_task(task_text, run.mode)
        self.store.append_event(run_id, "h_cua", "observation", result.summary, {"status": result.status})
        if result.status in {"blocked", "failed", "timed_out"}:
            run.status = "blocked" if result.status == "blocked" else "failed"
            run.current_step = "h_cua_blocked"
            self.store.save_run(run)
        return asdict(result)

    def run_amplify_deployment(self, run_id: str) -> dict:
        run = self.store.load_run(run_id)
        if run.status == "waiting_for_login":
            return {"status": "blocked", "summary": "Manual AWS login is required first."}
        if run.cloud != "aws" or run.target != "aws_amplify":
            return {"status": "blocked", "summary": f"Amplify deployment is not supported for target {run.target} on {run.cloud}."}

        action = "Create or update AWS Amplify app"
        if not approval_is_approved(self.store.run_dir(run_id), action):
            approval = create_approval(
                self.store.run_dir(run_id),
                action,
                "This can create cloud resources, connect GitHub, expose a public URL, and may incur AWS costs.",
                "high",
            )
            self.store.append_event(run_id, "system", "approval", "Approval required before AWS Amplify modification.", asdict(approval))
            run.status = "blocked"
            run.current_step = "approval_required"
            self.store.save_run(run)
            return {"status": "blocked", "summary": "Approval required before creating or changing AWS Amplify resources.", "approval": asdict(approval)}

        plan = self.get_amplify_plan(run_id)
        if not plan.get("supported"):
            return {"status": "blocked", "summary": "Repo is not supported by the AWS Amplify adapter.", "plan": plan}
        task_text = (
            f"Approval was granted for this action: {action}.\n"
            f"Use the currently open AWS Console to create or configure an AWS Amplify app named {plan['app_name']} "
            f"for branch {plan['branch']}. Build command: {plan.get('build_command')}. Output directory: {plan.get('output_directory')}. "
            "Stop and report before GitHub OAuth, billing, broad IAM permissions, deletion, replacement, or any unclear prompt. "
            "When complete, report the app name, branch, and any visible live/deployment URL."
        )
        run.status = "running"
        run.current_step = "h_cua_amplify_modify"
        self.store.save_run(run)
        self.store.append_event(run_id, "h_cua", "command", task_text, {"mode": run.mode, "approval": action})
        result = run_h_task(task_text, run.mode, max_steps=35, max_time_s=420)
        self.store.append_event(run_id, "h_cua", "observation", result.summary, {"status": result.status, "session_id": result.session_id, "outcome": result.outcome})
        if result.status == "completed":
            run.current_step = "h_cua_completed_run_verifier_next"
            run.status = "verifying"
            self.store.save_run(run)
            self.run_verifier(run_id, "default")
        else:
            run.status = "blocked" if result.status in {"blocked", "timed_out"} else "failed"
            run.current_step = "h_cua_amplify_blocked"
            self.store.save_run(run)
        return asdict(result)

    def submit_codex_plan(self, run_id: str, plan: str) -> dict:
        event = self.store.append_event(run_id, "codex", "plan", plan)
        return asdict(event)

    def submit_objection(self, run_id: str, objection: str, evidence: dict | None = None) -> dict:
        event = self.store.append_event(run_id, "codex", "objection", objection, evidence or {})
        return asdict(event)

    def request_approval(self, run_id: str, action: str, reason: str, risk_level: str = "medium") -> dict:
        approval = create_approval(self.store.run_dir(run_id), action, reason, risk_level)
        self.store.append_event(run_id, "system", "approval", f"Approval requested: {action}", asdict(approval))
        return asdict(approval)

    def decide_approval(self, run_id: str, approval_id: str, approved: bool) -> dict:
        approval = decide_approval(self.store.run_dir(run_id), approval_id, approved)
        self.store.append_event(run_id, "user", "approval", f"Approval {approval.status}: {approval.action}", asdict(approval))
        return asdict(approval)

    def list_approvals(self, run_id: str) -> list[dict]:
        return [asdict(item) for item in load_approvals(self.store.run_dir(run_id))]

    def voice_command(self, run_id: str, text: str) -> dict:
        route = classify_voice_command(text)
        self.store.append_event(run_id, "user", "voice_command", route.transcript, asdict(route))
        if route.classification == "direct_control":
            if route.action == "pause":
                self.pause(run_id)
            elif route.action == "resume":
                self.resume(run_id)
            elif route.action == "set_mode" and route.mode:
                self.set_mode(run_id, route.mode)
            elif route.action == "run_verifier":
                self.run_verifier(run_id, "default")
        return asdict(route)

    def speak(self, run_id: str, text: str) -> dict:
        self.store.append_event(run_id, "system", "command", "Requested Gradium TTS for a dashboard explanation.", {"text": text[:300]})
        result = synthesize_tts(text, str(self.repo_path))
        self.store.append_event(run_id, "system", "result", "Gradium TTS completed.", {"status": result.status, "summary": result.summary, "audio_bytes_base64_length": len(result.audio_base64)})
        return asdict(result)

    def run_verifier(self, run_id: str, verifier_name: str = "default", url: str | None = None) -> list[dict]:
        run = self.store.load_run(run_id)
        run.current_step = "verifier_running"
        self.store.save_run(run)
        out_dir = self.store.verifier_dir(run_id)
        results = []
        for result in [verify_git_diff(self.repo_path)]:
            results.append(asdict(result.save(out_dir)))
        if run.cloud == "aws":
            for result in [verify_aws_identity(), verify_amplify_apps()]:
                results.append(asdict(result.save(out_dir)))
        else:
            for result in [verify_gcp_identity(), verify_gcp_project()]:
                results.append(asdict(result.save(out_dir)))
        if url:
            for result in [verify_http_url(url), verify_playwright_url(url)]:
                results.append(asdict(result.save(out_dir)))
        self.store.append_event(run_id, "verifier", "result", "Ran verifier stack.", {"results": results})
        run = self.store.load_run(run_id)
        run.current_step = "verifier_complete"
        if all(item["status"] in {"passed", "skipped"} for item in results):
            run.status = "completed" if any(item["status"] == "passed" for item in results) else run.status
        else:
            run.status = "blocked"
        self.store.save_run(run)
        return results

    def write_report(self, run_id: str) -> dict:
        path = write_report(self.repo_path, run_id)
        return {"path": str(path)}

    def list_runs(self) -> list[dict]:
        return [asdict(run) for run in self.store.list_runs()]
