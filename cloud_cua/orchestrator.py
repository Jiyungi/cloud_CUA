from __future__ import annotations

import json
import base64
import os
from dataclasses import asdict
from pathlib import Path

from .approvals import approved as approval_is_approved
from .approvals import create_approval, decide_approval, load_approvals
from .aws_cleanup import cleanup_cloud_cua_aws_resources
from .browser_profile import launch_dedicated_browser
from .container_image import prepare_ecr_image_with_progress
from .credentials import inspect_credentials
from .deployment_contract import build_deployment_contract
from .deployments.aws_general import DEFAULT_MAX_SPEND_USD, build_aws_deployment_plan, build_general_aws_h_task
from .deployments.amplify import build_amplify_plan
from .deployments.gcp_cloud_run import build_gcp_cloud_run_h_task, build_gcp_cloud_run_plan
from .h_admin import cleanup_h_sessions
from .h_runner import run_h_task
from .mode_policy import normalize_mode
from .models import Cloud, Mode
from .paths import resolve_repo_path
from .repo_analyzer import analyze_repo
from .reports import write_report
from .resource_tracking import extract_resource_record, load_resource_records, save_resource_record
from .run_store import RunStore
from .safety import approval_reason, detect_approval_triggers, risk_level
from .supervisor import review_h_result
from .verifier.aws import (
    verify_amplify_apps,
    verify_app_runner_services,
    verify_aws_identity,
    verify_cloudformation_stacks,
    verify_ecs_clusters,
    verify_ecs_run_services,
    verify_ecr_repositories,
    verify_lambda_functions,
    verify_s3_buckets,
    verify_tagged_resources,
)
from .verifier.base import VerifierResult
from .verifier.gcp import verify_gcp_cloud_run_services, verify_gcp_identity, verify_gcp_project
from .verifier.http import verify_http_url
from .verifier.playwright_check import verify_playwright_url
from .verifier.repo import verify_git_diff
from .voice_gradium import synthesize_tts, transcribe_stt
from .voice_router import classify_voice_command


class Orchestrator:
    def __init__(self, repo_path: str | Path):
        self.repo_path = resolve_repo_path(repo_path)
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
        if cloud_v == "aws":
            aws_plan = build_aws_deployment_plan(self.repo_path.name, ctx)
            self.store.append_event(run.run_id, "system", "plan", "Prepared generalized AWS deployment plan.", {"aws_plan": aws_plan.to_dict()})
        if cloud_v == "gcp":
            gcp_plan = build_gcp_cloud_run_plan(self.repo_path.name, ctx)
            run.target = gcp_plan.target if gcp_plan.supported else "gcp_cloud_run_blocked"
            self.store.save_run(run)
            self.store.append_event(run.run_id, "system", "plan", "Prepared GCP Cloud Run deployment plan.", {"gcp_plan": gcp_plan.to_dict()})
        if cloud_v == "aws" and ctx.recommendation == "aws_amplify":
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

    def get_aws_plan(self, run_id: str) -> dict:
        ctx = analyze_repo(self.repo_path)
        plan = build_aws_deployment_plan(self.repo_path.name, ctx)
        self.store.append_event(run_id, "system", "plan", "Generated generalized AWS deployment plan.", {"aws_plan": plan.to_dict()})
        return plan.to_dict()

    def get_gcp_plan(self, run_id: str) -> dict:
        ctx = analyze_repo(self.repo_path)
        plan = build_gcp_cloud_run_plan(self.repo_path.name, ctx)
        self.store.append_event(run_id, "system", "plan", "Generated GCP Cloud Run plan.", {"gcp_plan": plan.to_dict()})
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

    def run_aws_deployment_task(
        self,
        run_id: str,
        task: str | None = None,
        target: str | None = None,
        max_spend_usd: float = DEFAULT_MAX_SPEND_USD,
    ) -> dict:
        run = self.store.load_run(run_id)
        active_steps = ("h_cua_", "container_image_")
        if run.status == "running" and run.current_step.startswith(active_steps):
            return {"status": "running", "summary": "Deployment work is already running for this run.", "current_step": run.current_step}
        if run.status == "waiting_for_login":
            return {"status": "blocked", "summary": "Manual AWS login is required first."}
        if run.cloud != "aws":
            return {"status": "blocked", "summary": "General AWS deployment tasks require an AWS run."}
        if max_spend_usd > DEFAULT_MAX_SPEND_USD:
            return {"status": "blocked", "summary": f"Requested max spend ${max_spend_usd:.2f} exceeds the configured ${DEFAULT_MAX_SPEND_USD:.2f} limit."}

        ctx = analyze_repo(self.repo_path)
        plan = build_aws_deployment_plan(self.repo_path.name, ctx, max_spend_usd=max_spend_usd)
        option = plan.option(target)
        contract = build_deployment_contract(self.repo_path, ctx, option.target)
        self.store.append_event(run_id, "codex", "contract", "Prepared deployment contract from repo facts.", {"contract": contract.to_dict()})
        if contract.missing_facts:
            run.status = "blocked"
            run.current_step = "deployment_contract_incomplete"
            run.target = option.target
            self.store.save_run(run)
            self.store.append_event(run_id, "codex", "objection", "Deployment contract is incomplete; stopping before cloud changes.", {"missing_facts": contract.missing_facts})
            return {"status": "blocked", "summary": "Deployment contract is incomplete; Cloud CUA needs clarification before creating resources.", "contract": contract.to_dict(), "aws_plan": plan.to_dict()}
        action = f"Run AWS deployment task: {option.label}"
        triggers = detect_approval_triggers(action, option.label, option.h_task_goal, " ".join(option.risks), task or "")
        if not approval_is_approved(self.store.run_dir(run_id), action):
            approval = create_approval(
                self.store.run_dir(run_id),
                action,
                approval_reason(
                    f"This lets H CUA operate AWS Console for {option.label}. "
                    f"The task can create cloud resources, public URLs, IAM/service roles, or service connections. "
                    "Cloud CUA will stop at new unapproved prompts and will verify with AWS CLI after H finishes.",
                    triggers,
                    budget_usd=max_spend_usd,
                ),
                risk_level(triggers),
                [trigger.code for trigger in triggers],
            )
            self.store.append_event(run_id, "system", "approval", "Approval required before generalized AWS deployment task.", asdict(approval))
            run.status = "blocked"
            run.current_step = "approval_required"
            self.store.save_run(run)
            return {"status": "blocked", "summary": "Approval required before H CUA can run the AWS deployment task.", "approval": asdict(approval), "aws_plan": plan.to_dict()}

        if not self.store.acquire_lock(run_id, "deployment"):
            run = self.store.load_run(run_id)
            return {"status": "running", "summary": "Deployment work is already running for this run.", "current_step": run.current_step}

        prepared_inputs: dict[str, str] = {}
        try:
            if option.target == "aws_ecs_express":
                def progress(step: str, message: str, evidence: dict) -> None:
                    current = self.store.load_run(run_id)
                    current.status = "running"
                    current.current_step = step
                    current.target = option.target
                    self.store.save_run(current)
                    self.store.append_event(run_id, "system", "command", message, evidence)

                progress("container_image_preparing", "Preparing local Docker image and ECR repository for ECS Express Mode.", {})
                image_prep = prepare_ecr_image_with_progress(self.repo_path, self.repo_path.name, run_id, plan.region, progress)
                self.store.append_event(run_id, "system", "result", image_prep.summary, image_prep.to_dict())
                if image_prep.status != "passed":
                    run = self.store.load_run(run_id)
                    run.status = "blocked"
                    run.current_step = "container_image_prep_failed"
                    run.target = option.target
                    self.store.save_run(run)
                    return {"status": "blocked", "summary": image_prep.summary, "image_prep": image_prep.to_dict(), "aws_target": option.target, "aws_plan": plan.to_dict()}
                prepared_inputs = {
                    "container_image_uri": image_prep.image_uri,
                    "ecr_repository": image_prep.repository_name,
                    "aws_region": plan.region,
                    "instruction": "Use this exact image URI in ECS Express Mode. Do not ask for GitHub source or App Runner.",
                }
                if contract.selected_container_port is not None:
                    prepared_inputs["container_port"] = str(contract.selected_container_port)
                    prepared_inputs["health_check_path"] = contract.health_check_path

            task_text = build_general_aws_h_task(
                self.repo_path.name,
                ctx,
                plan,
                target=option.target,
                user_task=task,
                run_id=run_id,
                prepared_inputs=prepared_inputs,
                contract=contract,
            )
            run = self.store.load_run(run_id)
            run.status = "running"
            run.current_step = f"h_cua_{option.target}"
            run.target = option.target
            self.store.save_run(run)
            self.store.append_event(run_id, "h_cua", "command", task_text, {"mode": run.mode, "aws_target": option.target, "max_spend_usd": max_spend_usd})
            result = run_h_task(task_text, run.mode, max_steps=60, max_time_s=900)
            self.store.append_event(run_id, "h_cua", "observation", result.summary, {"status": result.status, "session_id": result.session_id, "outcome": result.outcome})
            review = review_h_result(result, contract)
            self.store.append_event(run_id, "codex", "observation_review", f"Reviewed H CUA result: {review.status}.", review.to_dict())
            if result.status == "completed":
                self._record_resource_summary(run_id, run.cloud, option.target, result.summary)
                run.status = "verifying"
                run.current_step = "h_cua_completed_run_verifier_next"
                self.store.save_run(run)
                self.run_verifier(run_id, "default")
                self.write_report(run_id)
            else:
                run.status = "blocked" if result.status in {"blocked", "timed_out"} else "failed"
                run.current_step = "h_cua_aws_task_blocked"
                self.store.save_run(run)
            return {**asdict(result), "aws_target": option.target, "aws_plan": plan.to_dict()}
        finally:
            self.store.release_lock(run_id, "deployment")

    def run_gcp_deployment_task(
        self,
        run_id: str,
        task: str | None = None,
    ) -> dict:
        run = self.store.load_run(run_id)
        if run.status == "running" and run.current_step.startswith("h_cua_"):
            return {"status": "running", "summary": "H CUA is already running for this deployment.", "current_step": run.current_step}
        if run.status == "waiting_for_login":
            return {"status": "blocked", "summary": "Manual GCP login is required first."}
        if run.cloud != "gcp":
            return {"status": "blocked", "summary": "GCP deployment tasks require a GCP run."}

        ctx = analyze_repo(self.repo_path)
        plan = build_gcp_cloud_run_plan(self.repo_path.name, ctx)
        if not plan.supported:
            return {"status": "blocked", "summary": plan.reason, "gcp_plan": plan.to_dict()}

        action = "Run GCP Cloud Run deployment task"
        triggers = detect_approval_triggers(action, plan.reason, " ".join(plan.risks), task or "")
        if not approval_is_approved(self.store.run_dir(run_id), action):
            approval = create_approval(
                self.store.run_dir(run_id),
                action,
                approval_reason(
                    "This lets H CUA operate GCP Console for Cloud Run. It may create billable services, public URLs, Artifact Registry, Cloud Build, or IAM changes.",
                    triggers,
                    budget_usd=DEFAULT_MAX_SPEND_USD,
                ),
                risk_level(triggers),
                [trigger.code for trigger in triggers],
            )
            self.store.append_event(run_id, "system", "approval", "Approval required before GCP Cloud Run task.", asdict(approval))
            run.status = "blocked"
            run.current_step = "approval_required"
            self.store.save_run(run)
            return {"status": "blocked", "summary": "Approval required before H CUA can run the GCP deployment task.", "approval": asdict(approval), "gcp_plan": plan.to_dict()}

        task_text = build_gcp_cloud_run_h_task(self.repo_path.name, ctx, plan, task)
        run.status = "running"
        run.current_step = "h_cua_gcp_cloud_run"
        run.target = plan.target
        self.store.save_run(run)
        self.store.append_event(run_id, "h_cua", "command", task_text, {"mode": run.mode, "gcp_target": plan.target})
        result = run_h_task(task_text, run.mode, max_steps=60, max_time_s=900)
        self.store.append_event(run_id, "h_cua", "observation", result.summary, {"status": result.status, "session_id": result.session_id, "outcome": result.outcome})
        if result.status == "completed":
            self._record_resource_summary(run_id, run.cloud, plan.target, result.summary)
            run.status = "verifying"
            run.current_step = "h_cua_completed_run_verifier_next"
            self.store.save_run(run)
            self.run_verifier(run_id, "default")
        else:
            run.status = "blocked" if result.status in {"blocked", "timed_out"} else "failed"
            run.current_step = "h_cua_gcp_task_blocked"
            self.store.save_run(run)
        return {**asdict(result), "gcp_plan": plan.to_dict()}

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
        if approved:
            run = self.store.load_run(run_id)
            if run.status == "blocked" and run.current_step == "approval_required":
                run.status = "running"
                run.current_step = "approval_approved"
                self.store.save_run(run)
        return asdict(approval)

    def resume_approved_deployment(self, run_id: str) -> dict:
        approvals = load_approvals(self.store.run_dir(run_id))
        approval = next(
            (
                item
                for item in approvals
                if item.status == "approved"
                and (
                    item.action.startswith("Run AWS deployment task:")
                    or item.action == "Run GCP Cloud Run deployment task"
                )
            ),
            None,
        )
        if approval is None:
            return {"status": "skipped", "summary": "No approved deployment gate is ready to resume."}

        run = self.store.load_run(run_id)
        if run.status == "running" and run.current_step.startswith(("h_cua_", "container_image_")):
            return {"status": "running", "summary": "Deployment work is already running for this run.", "current_step": run.current_step}

        if run.status == "blocked" and run.current_step == "approval_required":
            run.status = "running"
            run.current_step = "approval_approved"
            self.store.save_run(run)
        elif run.current_step not in {"approval_required", "approval_approved"}:
            return {"status": "skipped", "summary": f"Approved deployment gate is not resumable from step {run.current_step}.", "current_step": run.current_step}

        self.store.append_event(run_id, "system", "command", "Continuing approved deployment gate.", {"approval_id": approval.approval_id, "action": approval.action})
        if approval.action.startswith("Run AWS deployment task:"):
            target = run.target if run.cloud == "aws" and run.target else None
            return self.run_aws_deployment_task(run_id, target=target)
        if approval.action == "Run GCP Cloud Run deployment task":
            return self.run_gcp_deployment_task(run_id)
        return {"status": "skipped", "summary": f"Approved action is not resumable: {approval.action}"}

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

    def transcribe_voice(self, run_id: str, audio_base64: str, input_format: str = "webm") -> dict:
        try:
            audio = base64.b64decode(audio_base64.split(",", 1)[-1])
        except Exception as exc:
            return {"status": "failed", "summary": f"Invalid audio payload: {exc}", "transcript": ""}
        stt = transcribe_stt(audio, str(self.repo_path), input_format)
        transcript = stt.transcript.strip()
        message = "Gradium STT completed."
        if stt.status == "passed":
            message = f"Gradium STT heard: {transcript or '[no speech detected]'}"
        self.store.append_event(
            run_id,
            "system",
            "result",
            message,
            {"status": stt.status, "summary": stt.summary, "transcript": transcript, "input_format": input_format},
        )
        route = None
        if stt.status == "passed" and transcript:
            route = self.voice_command(run_id, transcript)
            self.store.append_event(
                run_id,
                "system",
                "result",
                f"STT routed to {route['route']} as {route['classification']}.",
                {"route": route},
            )
        return {"stt": asdict(stt), "route": route}

    def run_verifier(self, run_id: str, verifier_name: str = "default", url: str | None = None) -> list[dict]:
        run = self.store.load_run(run_id)
        run.current_step = "verifier_running"
        self.store.save_run(run)
        out_dir = self.store.verifier_dir(run_id)
        results = []
        for result in [verify_git_diff(self.repo_path)]:
            results.append(asdict(result.save(out_dir)))
        if run.cloud == "aws":
            aws_results = [
                verify_aws_identity(),
                verify_tagged_resources(run_id),
                verify_amplify_apps(),
                verify_app_runner_services(),
                verify_ecs_clusters(),
                verify_ecr_repositories(),
                verify_lambda_functions(),
                verify_s3_buckets(),
                verify_cloudformation_stacks(),
            ]
            if run.target in {"aws_ecs_express", "aws_ecs_fargate"}:
                aws_results.append(verify_ecs_run_services(run_id))
            for result in aws_results:
                results.append(asdict(result.save(out_dir)))
        else:
            for result in [verify_gcp_identity(), verify_gcp_project(), verify_gcp_cloud_run_services()]:
                results.append(asdict(result.save(out_dir)))
        urls = [url] if url else []
        for record in load_resource_records(self.store.run_dir(run_id) / "resources.json"):
            urls.extend(record.app_urls)
        if run.cloud == "aws" and run.target in {"aws_ecs_express", "aws_ecs_fargate", "aws_amplify", "aws_s3_static_site"} and not urls:
            result = VerifierResult(
                "public_app_url",
                "failed",
                "resource_records.app_urls",
                "No public application URL was found. Console URLs do not count as live app proof.",
            )
            results.append(asdict(result.save(out_dir)))
        for item_url in sorted(set(item for item in urls if item)):
            for result in [verify_http_url(item_url), verify_playwright_url(item_url)]:
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

    def cleanup_h_sessions(self) -> dict:
        result = cleanup_h_sessions(str(self.repo_path))
        return result.to_dict()

    def cleanup_aws_resources(self, run_id: str | None = None, dry_run: bool = True) -> dict:
        result = cleanup_cloud_cua_aws_resources(run_id=run_id, dry_run=dry_run)
        if run_id:
            self.store.append_event(run_id, "system", "command", "Ran AWS cleanup workflow.", result.to_dict())
        return result.to_dict()

    def write_report(self, run_id: str) -> dict:
        path = write_report(self.repo_path, run_id)
        return {"path": str(path)}

    def list_runs(self) -> list[dict]:
        return [asdict(run) for run in self.store.list_runs()]

    def capabilities(self) -> dict:
        creds = inspect_credentials(self.repo_path)
        return {
            "hai_api_key_present": creds.hai_api_key_present,
            "gradium_api_key_present": creds.gradium_api_key_present,
            "credentials_source": creds.source,
            "container_mode": os.environ.get("CLOUD_CUA_CONTAINER") == "1",
        }

    def _record_resource_summary(self, run_id: str, cloud: str, target: str, summary: str) -> None:
        record = extract_resource_record(run_id, cloud, target, summary)
        path = save_resource_record(self.store.run_dir(run_id) / "resources.json", record)
        self.store.append_event(run_id, "system", "result", "Recorded resource hints from H CUA final answer.", {"path": str(path), "record": asdict(record)})
