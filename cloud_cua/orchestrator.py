from __future__ import annotations

import json
import base64
import os
import time
from uuid import uuid4
from dataclasses import asdict
from pathlib import Path

from .approvals import approved as approval_is_approved
from .approvals import create_approval, decide_approval, load_approvals
from .aws_cleanup import cleanup_cloud_cua_aws_resources
from .aws_costs import ensure_cost_policy, load_cost_policy, save_cost_policy, start_cost_clock, start_run_cost_clock
from .aws_runtime_config import load_runtime_configuration, provision_aws_runtime_configuration
from .amplify_artifact import stage_amplify_artifact
from .browser_profile import launch_dedicated_browser
from .cloud_identity import build_aws_browser_identity_task, load_browser_identity, review_aws_browser_identity, save_browser_identity
from .container_image import ContainerImagePrepResult, ecr_image_exists, prepare_ecr_image_with_progress
from .cost_monitor import get_cost_monitor
from .credentials import inspect_credentials
from .deployment_contract import build_deployment_contract, load_contract, save_contract
from .deployment_checkpoints import load_milestone_checkpoint, save_milestone_checkpoint
from .deployment_milestones import (
    MilestoneReview,
    build_ecs_inspection_task,
    build_ecs_prepare_form_task,
    build_ecs_submit_task,
    review_ecs_inspection,
    review_ecs_prepared_form,
)
from .deployments.aws_general import DEFAULT_MAX_SPEND_USD, build_aws_deployment_plan, build_general_aws_h_task
from .deployments.amplify import (
    AmplifyMilestoneReview,
    build_amplify_inspection_task,
    build_amplify_plan,
    build_amplify_prepare_task,
    build_amplify_submit_task,
    review_amplify_creation,
    review_amplify_inspection,
    review_amplify_prepared,
)
from .deployments.s3_static import apply_s3_public_read_policy, build_s3_creation_task, build_s3_website_task, review_s3_bucket, review_s3_website, s3_bucket_name
from .deployments.gcp_cloud_run import build_gcp_cloud_run_h_task, build_gcp_cloud_run_plan
from .h_admin import cleanup_h_sessions
from .explanations import explain_run_question
from .h_runner import HTaskResult, run_h_task, summarize_h_event
from .h_skills import get_h_skill_status, sync_h_skills
from .h_session_manager import get_h_session_manager
from .lessons import load_lesson_candidate, resolve_lesson_candidate, write_lesson_candidate
from .mode_policy import normalize_mode
from .models import Cloud, Mode
from .paths import resolve_repo_path
from .repo_analyzer import analyze_repo
from .reports import write_report
from .resource_tracking import extract_resource_record, load_resource_records, save_resource_record
from .skill_registry import get_skill, load_skills, skill_for_target
from .static_artifact import prepare_static_artifact, upload_static_artifact
from .run_store import RunStore, now_iso
from .safety import approval_reason, detect_approval_triggers, risk_level
from .supervisor import review_h_result
from .verifier.aws import (
    verify_amplify_apps,
    verify_amplify_run,
    verify_app_runner_services,
    verify_aws_identity,
    verify_cloudformation_stacks,
    verify_ecs_clusters,
    verify_ecs_contract,
    verify_ecs_run_services,
    verify_ecr_repositories,
    verify_lambda_functions,
    verify_s3_buckets,
    verify_s3_static_run,
    verify_runtime_secret_references,
    verify_cloudtrail_run,
    verify_tagged_resources,
)
from .verifier.base import VerifierResult
from .verifier.gcp import verify_gcp_cloud_run_services, verify_gcp_identity, verify_gcp_project
from .verifier.http import verify_http_url
from .verifier.playwright_check import verify_playwright_url
from .verifier.repo import verify_repository
from .voice_gradium import synthesize_tts, transcribe_stt
from .voice_router import classify_voice_command


class Orchestrator:
    def __init__(self, repo_path: str | Path):
        self.repo_path = resolve_repo_path(repo_path)
        self.store = RunStore(self.repo_path)
        self.h_sessions = get_h_session_manager()
        self.h_sessions.recover_repo(self.repo_path)
        self.cost_monitor = get_cost_monitor()

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
        if (self.store.run_dir(run_id) / "cost-policy.json").exists():
            self.cost_monitor.evaluate(self.repo_path, run_id)
        urls = sorted(
            {
                url
                for record in load_resource_records(self.store.run_dir(run_id) / "resources.json")
                for url in record.app_urls
            }
        )
        report = self.repo_path / "DEPLOYMENT_REPORT.md"
        cleanup_events = [event for event in self.store.read_events(run_id, 1000) if event.get("message") == "Ran AWS cleanup workflow."]
        cleanup_state = cleanup_events[-1].get("evidence", {}) if cleanup_events else {"status": "not_run"}
        return {
            **asdict(self.store.load_run(run_id)),
            "h_job": self.h_sessions.get(self.repo_path, run_id),
            "live_urls": urls,
            "report_path": str(report) if report.exists() else None,
            "cleanup_state": cleanup_state,
        }

    def set_dashboard_url(self, run_id: str, dashboard_url: str) -> dict:
        run = self.store.load_run(run_id)
        run.dashboard_url = dashboard_url
        self.store.save_run(run)
        return asdict(run)

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
        if saved.status == "passed" and run.cloud == "aws":
            try:
                account_id = str(json.loads(saved.summary).get("Account") or "")
            except (TypeError, json.JSONDecodeError):
                account_id = ""
            if len(account_id) != 12 or not account_id.isdigit():
                run.status = "blocked"
                run.current_step = "identity_verifier_failed"
                self.store.save_run(run)
            else:
                run.status = "running"
                run.current_step = "browser_identity_verifying"
                self.store.save_run(run)
                (self.store.run_dir(run_id) / "expected-account.json").write_text(json.dumps({"account_id": account_id}), encoding="utf-8")
        return asdict(run)

    def inspect_browser_identity(self, run_id: str) -> dict:
        run = self.store.load_run(run_id)
        expected_path = self.store.run_dir(run_id) / "expected-account.json"
        try:
            expected = str(json.loads(expected_path.read_text(encoding="utf-8"))["account_id"])
        except Exception:
            run.status = "blocked"
            run.current_step = "browser_identity_missing_cli_proof"
            self.store.save_run(run)
            return {"status": "blocked", "message": "Expected AWS CLI account proof is missing."}
        task = build_aws_browser_identity_task(expected)
        self.store.append_event(run_id, "h_cua", "command", "Inspecting the logged-in AWS browser account ID without making changes.", {"expected_account_id": expected})
        result = run_h_task(
            task,
            run.mode,
            max_steps=15,
            max_time_s=240,
            event_callback=self._h_event_callback(run_id, "verify_aws_browser_identity"),
            answer_schema_name="aws_browser_identity",
        )
        proof = review_aws_browser_identity(result, expected)
        save_browser_identity(self.store.run_dir(run_id) / "browser-identity.json", proof)
        self.store.append_event(run_id, "verifier", "result", proof.message, {"browser_identity": proof.to_dict(), "session_id": result.session_id})
        if proof.status == "matched":
            run.status = "running"
            run.current_step = "login_verified"
        else:
            run.status = "blocked"
            run.current_step = "browser_identity_mismatch" if proof.status == "mismatched" else "browser_identity_unverified"
        self.store.save_run(run)
        return proof.to_dict()

    def pause(self, run_id: str) -> dict:
        control = self.h_sessions.pause(self.repo_path, run_id)
        run = self.store.load_run(run_id)
        if control["status"] in {"paused", "skipped"}:
            run.status = "paused"
            message = "Paused deployment and confirmed the H session is paused."
        else:
            message = "Could not confirm that the H session paused; the deployment state was not changed."
        self.store.save_run(run)
        self.store.append_event(run_id, "user", "command", message, {"h_control": control})
        return {**asdict(run), "h_job": control.get("h_job")}

    def resume(self, run_id: str) -> dict:
        control = self.h_sessions.resume(self.repo_path, run_id)
        run = self.store.load_run(run_id)
        if control["status"] in {"running", "skipped"}:
            run.status = "running"
            message = "Resumed deployment and confirmed the H session is running."
        else:
            message = "Could not confirm that the H session resumed; the deployment state was not changed."
        self.store.save_run(run)
        self.store.append_event(run_id, "user", "command", message, {"h_control": control})
        return {**asdict(run), "h_job": control.get("h_job")}

    def cancel(self, run_id: str) -> dict:
        control = self.h_sessions.cancel(self.repo_path, run_id)
        run = self.store.load_run(run_id)
        if control["status"] == "cancelled":
            run.status = "cancelled"
            run.current_step = "cancelled"
            message = "Cancelled deployment. Existing cloud resources were not deleted."
        else:
            run.status = "blocked"
            run.current_step = "h_cancel_unconfirmed"
            message = "H cancellation was not confirmed. Cloud CUA blocked the run for manual review."
        self.store.save_run(run)
        self.store.append_event(run_id, "user", "command", message, {"h_control": control})
        return {**asdict(run), "h_job": control.get("h_job")}

    def run_h_inspect(self, run_id: str, task: str | None = None) -> dict:
        run = self.store.load_run(run_id)
        if run.status == "paused":
            return {"status": "skipped", "summary": "Run is paused."}
        if run.status == "waiting_for_login":
            return {"status": "blocked", "summary": "Manual cloud login is required before H CUA can run."}
        task_text = task or "Inspect the visible cloud console page and report what page is visible. Do not create, edit, or delete anything."
        self.store.append_event(run_id, "h_cua", "command", task_text, {"mode": run.mode})
        result = run_h_task(task_text, run.mode, event_callback=self._h_event_callback(run_id, "inspect"))
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
        browser_identity = load_browser_identity(self.store.run_dir(run_id) / "browser-identity.json")
        if not browser_identity or browser_identity.status != "matched":
            return {"status": "blocked", "summary": "The AWS account visible in the browser has not been proven to match the AWS CLI account."}

        ctx = analyze_repo(self.repo_path)
        plan = build_aws_deployment_plan(self.repo_path.name, ctx, max_spend_usd=max_spend_usd)
        option = plan.option(target)
        if run.target != option.target:
            run.target = option.target
            self.store.save_run(run)
        amplify_plan = build_amplify_plan(self.repo_path.name, ctx) if option.target == "aws_amplify" else None
        resource_name = (
            s3_bucket_name(self.repo_path.name, run_id)
            if option.target == "aws_s3_static_site"
            else amplify_plan.app_name if amplify_plan else ""
        )
        branch_name = amplify_plan.branch if amplify_plan else ""
        cost_policy = ensure_cost_policy(self.store.run_dir(run_id), option.target, plan.region, max_spend_usd)
        self.cost_monitor.register(self.repo_path, run_id)
        if cost_policy.status != "ready":
            run.status = "blocked"
            run.current_step = "cost_estimate_unavailable"
            run.target = option.target
            self.store.save_run(run)
            self.store.append_event(run_id, "codex", "objection", cost_policy.message, {"cost_policy": cost_policy.to_dict()})
            return {"status": "blocked", "summary": cost_policy.message, "cost_policy": cost_policy.to_dict()}
        contract = build_deployment_contract(self.repo_path, ctx, option.target)
        previous_contract = None
        if self.store.contract_path(run_id).exists():
            try:
                previous_contract = load_contract(self.store.contract_path(run_id))
            except Exception:
                previous_contract = None
        skill = skill_for_target(option.target)
        if skill is not None:
            contract = contract.with_runtime_inputs(
                run_id=run_id,
                skill_name=skill.name,
                skill_hash=skill.content_hash,
                autonomy_level=skill.autonomy_level,
                cloud_region=plan.region,
                container_image_uri=previous_contract.container_image_uri if previous_contract and previous_contract.target == option.target else "",
                ecr_repository=previous_contract.ecr_repository if previous_contract and previous_contract.target == option.target else "",
                repo_name=self.repo_path.name,
                resource_name=resource_name,
                branch_name=branch_name,
                build_command=ctx.build_command or "",
                output_directory=ctx.output_directory or "",
                expected_account_id=browser_identity.expected_account_id,
                cost_limit_usd=cost_policy.max_spend_usd,
                estimated_hourly_usd=cost_policy.fixed_hourly_usd,
                cost_deadline_at=cost_policy.deadline_at,
            )
        contract_path = save_contract(self.store.contract_path(run_id), contract)
        self.store.append_event(run_id, "codex", "contract", "Prepared and saved deployment contract from repo facts.", {"contract": contract.to_dict(), "path": str(contract_path)})
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

        runtime_config = load_runtime_configuration(self.store.run_dir(run_id), ctx.env_vars)
        if runtime_config.status != "ready":
            run.status = "waiting_for_configuration"
            run.current_step = "runtime_configuration_required"
            run.target = option.target
            self.store.save_run(run)
            self.store.append_event(
                run_id,
                "system",
                "approval",
                "Secure runtime configuration is required before cloud deployment can continue.",
                {"required_names": runtime_config.required_names, "missing_names": runtime_config.missing_names, "public_build_names": runtime_config.public_build_names},
            )
            return runtime_config.to_dict()

        if not self.store.acquire_lock(run_id, "deployment"):
            run = self.store.load_run(run_id)
            return {"status": "running", "summary": "Deployment work is already running for this run.", "current_step": run.current_step}

        prepared_inputs: dict[str, str] = {}
        static_artifact = None
        amplify_artifact = None
        cost_clock_started = False
        try:
            if option.target == "aws_ecs_express":
                def progress(step: str, message: str, evidence: dict) -> None:
                    current = self.store.load_run(run_id)
                    current.status = "running"
                    current.current_step = step
                    current.target = option.target
                    self.store.save_run(current)
                    self.store.append_event(run_id, "system", "command", message, evidence)

                if contract.container_image_uri and contract.ecr_repository and ecr_image_exists(contract.container_image_uri, contract.ecr_repository, plan.region):
                    progress(
                        "container_image_reused",
                        "Reusing the run's existing ECR image for ECS Express Mode.",
                        {"image_uri": contract.container_image_uri, "repository": contract.ecr_repository},
                    )
                    image_prep = ContainerImagePrepResult(
                        "passed",
                        f"Reused existing ECR image: {contract.container_image_uri}",
                        image_uri=contract.container_image_uri,
                        repository_name=contract.ecr_repository,
                        registry=contract.container_image_uri.split("/", 1)[0],
                    )
                else:
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
            elif option.target == "aws_s3_static_site":
                static_artifact = prepare_static_artifact(
                    self.repo_path,
                    ctx,
                    self.store.run_dir(run_id) / "static-artifact",
                )
                self.store.append_event(run_id, "system", "result", static_artifact.summary, static_artifact.to_dict())
                if static_artifact.status != "passed":
                    run = self.store.load_run(run_id)
                    run.status = "blocked"
                    run.current_step = "static_artifact_failed"
                    self.store.save_run(run)
                    return {"status": "blocked", "summary": static_artifact.summary, "artifact": static_artifact.to_dict()}
                prepared_inputs = {"output_directory": static_artifact.output_directory, "bucket_name": resource_name}
            elif option.target == "aws_amplify":
                if ctx.category != "frontend_static":
                    run = self.store.load_run(run_id)
                    run.status = "blocked"
                    run.current_step = "amplify_manual_deploy_unsupported"
                    self.store.save_run(run)
                    return {"status": "blocked", "summary": "Deploy without Git supports static build output only. SSR/full-stack Amplify requires a separately approved GitHub App workflow."}
                static_artifact = prepare_static_artifact(
                    self.repo_path,
                    ctx,
                    self.store.run_dir(run_id) / "static-artifact",
                )
                self.store.append_event(run_id, "system", "result", static_artifact.summary, static_artifact.to_dict())
                if static_artifact.status != "passed":
                    run = self.store.load_run(run_id)
                    run.status = "blocked"
                    run.current_step = "amplify_static_artifact_failed"
                    self.store.save_run(run)
                    return {"status": "blocked", "summary": static_artifact.summary, "artifact": static_artifact.to_dict()}
                amplify_artifact = stage_amplify_artifact(
                    self.store.run_dir(run_id),
                    static_artifact.output_directory,
                    self.repo_path.name,
                    run_id,
                    plan.region,
                )
                self.store.append_event(run_id, "system", "result", amplify_artifact.summary, amplify_artifact.to_dict())
                if amplify_artifact.status != "passed":
                    run = self.store.load_run(run_id)
                    run.status = "blocked"
                    run.current_step = "amplify_artifact_staging_failed"
                    self.store.save_run(run)
                    return {"status": "blocked", "summary": amplify_artifact.summary, "artifact": amplify_artifact.to_dict()}
                prepared_inputs = {"artifact_reference": amplify_artifact.s3_uri, "branch_name": branch_name}

            skill = skill_for_target(option.target)
            if skill is None:
                run = self.store.load_run(run_id)
                run.status = "blocked"
                run.current_step = "deployment_skill_missing"
                self.store.save_run(run)
                self.store.append_event(run_id, "codex", "objection", f"No approved deployment skill exists for {option.target}.")
                return {"status": "blocked", "summary": f"No approved deployment skill exists for {option.target}."}
            skill_sync = sync_h_skills(self.repo_path, names=[skill.name])
            self.store.append_event(
                run_id,
                "system",
                "skill_sync",
                skill_sync.message,
                {"skill": skill.to_dict(include_body=False), "sync": skill_sync.to_dict()},
            )
            if skill_sync.status != "passed":
                run = self.store.load_run(run_id)
                run.status = "blocked"
                run.current_step = "h_skill_sync_blocked"
                self.store.save_run(run)
                return {"status": "blocked", "summary": skill_sync.message, "skill_sync": skill_sync.to_dict()}

            contract = contract.with_runtime_inputs(
                run_id=run_id,
                skill_name=skill.name,
                skill_hash=skill.content_hash,
                autonomy_level=skill.autonomy_level,
                cloud_region=plan.region,
                container_image_uri=prepared_inputs.get("container_image_uri", ""),
                ecr_repository=prepared_inputs.get("ecr_repository", ""),
                repo_name=self.repo_path.name,
                resource_name=resource_name,
                branch_name=branch_name,
                build_command=ctx.build_command or "",
                output_directory=ctx.output_directory or "",
                artifact_reference=prepared_inputs.get("artifact_reference", ""),
                expected_account_id=browser_identity.expected_account_id,
                runtime_secret_references=runtime_config.reference_map(),
                cost_limit_usd=cost_policy.max_spend_usd,
                estimated_hourly_usd=cost_policy.fixed_hourly_usd,
                cost_deadline_at=cost_policy.deadline_at,
            )
            save_contract(self.store.contract_path(run_id), contract)

            if option.target == "aws_ecs_express":
                checkpoint_path = self.store.milestones_path(run_id)
                inspection_checkpoint = load_milestone_checkpoint(checkpoint_path, "inspect_ecs_express_form", contract)
                if inspection_checkpoint:
                    inspection_review = MilestoneReview(**inspection_checkpoint["review"])
                    self.store.append_event(
                        run_id,
                        "codex",
                        "milestone_reused",
                        "Reused the contract-matching ECS inspection checkpoint.",
                        {"milestone": "inspect_ecs_express_form", "review": inspection_review.to_dict()},
                    )
                else:
                    run = self.store.load_run(run_id)
                    run.status = "running"
                    run.current_step = "h_cua_inspect_ecs_form"
                    run.target = option.target
                    self.store.save_run(run)
                    inspect_task = build_ecs_inspection_task(contract)
                    self.store.append_event(run_id, "h_cua", "milestone", "H CUA is inspecting the ECS Express form without making changes.", {"milestone": "inspect_ecs_express_form", "skill_name": skill.name})
                    inspect_result = run_h_task(
                        inspect_task,
                        run.mode,
                        max_steps=30,
                        max_time_s=420,
                        skill_names=[skill.name],
                        event_callback=self._h_event_callback(run_id, "inspect_ecs_express_form"),
                        answer_schema_name="ecs_inspection",
                    )
                    self.store.append_event(run_id, "h_cua", "observation", inspect_result.summary, {"status": inspect_result.status, "session_id": inspect_result.session_id, "milestone": "inspect_ecs_express_form"})
                    inspection_review = review_ecs_inspection(inspect_result, contract)
                    self.store.append_event(run_id, "codex", "milestone_review", f"Supervisor reviewed ECS form inspection: {inspection_review.status}.", inspection_review.to_dict())
                    if inspection_review.status == "clear":
                        save_milestone_checkpoint(
                            checkpoint_path,
                            "inspect_ecs_express_form",
                            contract,
                            asdict(inspect_result),
                            inspection_review.to_dict(),
                        )
                if inspection_review.status != "clear":
                    run = self.store.load_run(run_id)
                    run.status = "blocked"
                    run.current_step = "ecs_form_contract_mismatch"
                    self.store.save_run(run)
                    self._write_lesson(
                        run_id,
                        skill.name,
                        "H CUA's ECS form inspection conflicted with the deployment contract.",
                        inspection_review.to_dict(),
                        "Require a structured, contract-matching ECS form inspection before any mutation milestone.",
                        "Test that any visible image, port, region, health path, or service-target mismatch blocks creation.",
                    )
                    return {
                        "status": "blocked",
                        "summary": "The ECS form inspection did not match the saved deployment contract.",
                        "review": inspection_review.to_dict(),
                        "contract": contract.to_dict(),
                    }

                prepare_checkpoint = load_milestone_checkpoint(checkpoint_path, "prepare_ecs_express_form", contract)
                if prepare_checkpoint:
                    prepare_review = MilestoneReview(**prepare_checkpoint["review"])
                    self.store.append_event(
                        run_id,
                        "codex",
                        "milestone_reused",
                        "Reused the contract-matching prepared ECS form checkpoint; H must still visually recheck it before submit.",
                        {"milestone": "prepare_ecs_express_form", "review": prepare_review.to_dict()},
                    )
                else:
                    run = self.store.load_run(run_id)
                    run.current_step = "h_cua_prepare_ecs_form"
                    self.store.save_run(run)
                    prepare_task = build_ecs_prepare_form_task(contract, inspection_review.corrections)
                    self.store.append_event(run_id, "h_cua", "milestone", "H CUA is preparing the ECS form without submitting it.", {"milestone": "prepare_ecs_express_form", "skill_name": skill.name})
                    prepare_result = run_h_task(
                        prepare_task,
                        run.mode,
                        max_steps=35,
                        max_time_s=480,
                        skill_names=[skill.name],
                        event_callback=self._h_event_callback(run_id, "prepare_ecs_express_form"),
                        answer_schema_name="ecs_prepared_form",
                    )
                    self.store.append_event(run_id, "h_cua", "observation", prepare_result.summary, {"status": prepare_result.status, "session_id": prepare_result.session_id, "milestone": "prepare_ecs_express_form"})
                    prepare_review = review_ecs_prepared_form(prepare_result, contract)
                    self.store.append_event(run_id, "codex", "milestone_review", f"Supervisor reviewed prepared ECS form: {prepare_review.status}.", prepare_review.to_dict())
                    if prepare_review.status == "clear":
                        save_milestone_checkpoint(
                            checkpoint_path,
                            "prepare_ecs_express_form",
                            contract,
                            asdict(prepare_result),
                            prepare_review.to_dict(),
                        )
                if prepare_review.status != "clear":
                    run = self.store.load_run(run_id)
                    run.status = "blocked"
                    run.current_step = "ecs_prepared_form_mismatch"
                    self.store.save_run(run)
                    self._write_lesson(
                        run_id,
                        skill.name,
                        "H CUA's prepared ECS form did not match the deployment contract.",
                        prepare_review.to_dict(),
                        "Prepare the cloud form without submitting, then compare every selected value to the contract.",
                        "Test that image, port, health path, tag, blocker, or ready-state mismatches prevent submission.",
                    )
                    return {"status": "blocked", "summary": "The prepared ECS form did not match the deployment contract.", "review": prepare_review.to_dict(), "contract": contract.to_dict()}

                task_text = build_ecs_submit_task(contract)
            elif option.target == "aws_amplify":
                checkpoint_path = self.store.milestones_path(run_id)
                inspection_checkpoint = load_milestone_checkpoint(checkpoint_path, "inspect_amplify_manual_deploy", contract)
                if inspection_checkpoint:
                    amplify_inspection = AmplifyMilestoneReview(**inspection_checkpoint["review"])
                else:
                    run = self.store.load_run(run_id)
                    run.status = "running"
                    run.current_step = "h_cua_inspect_amplify"
                    run.target = option.target
                    self.store.save_run(run)
                    inspection_result = run_h_task(
                        build_amplify_inspection_task(contract),
                        run.mode,
                        max_steps=25,
                        max_time_s=360,
                        skill_names=[skill.name],
                        event_callback=self._h_event_callback(run_id, "inspect_amplify_manual_deploy"),
                        answer_schema_name="amplify_inspection",
                    )
                    amplify_inspection = review_amplify_inspection(inspection_result, contract)
                    self.store.append_event(run_id, "codex", "milestone_review", f"Supervisor reviewed Amplify inspection: {amplify_inspection.status}.", amplify_inspection.to_dict())
                    if amplify_inspection.status == "clear":
                        save_milestone_checkpoint(checkpoint_path, "inspect_amplify_manual_deploy", contract, asdict(inspection_result), amplify_inspection.to_dict())
                if amplify_inspection.status != "clear":
                    run = self.store.load_run(run_id)
                    run.status = "blocked"
                    run.current_step = "amplify_inspection_blocked"
                    self.store.save_run(run)
                    return {"status": "blocked", "summary": "Amplify manual deployment inspection failed.", "review": amplify_inspection.to_dict()}

                prepared_checkpoint = load_milestone_checkpoint(checkpoint_path, "prepare_amplify_manual_deploy", contract)
                if prepared_checkpoint:
                    amplify_prepared = AmplifyMilestoneReview(**prepared_checkpoint["review"])
                else:
                    run = self.store.load_run(run_id)
                    run.current_step = "h_cua_prepare_amplify"
                    self.store.save_run(run)
                    prepared_result = run_h_task(
                        build_amplify_prepare_task(contract),
                        run.mode,
                        max_steps=35,
                        max_time_s=480,
                        skill_names=[skill.name],
                        event_callback=self._h_event_callback(run_id, "prepare_amplify_manual_deploy"),
                        answer_schema_name="amplify_prepared",
                    )
                    amplify_prepared = review_amplify_prepared(prepared_result, contract)
                    self.store.append_event(run_id, "codex", "milestone_review", f"Supervisor reviewed prepared Amplify form: {amplify_prepared.status}.", amplify_prepared.to_dict())
                    if amplify_prepared.status == "clear":
                        save_milestone_checkpoint(checkpoint_path, "prepare_amplify_manual_deploy", contract, asdict(prepared_result), amplify_prepared.to_dict())
                if amplify_prepared.status != "clear":
                    run = self.store.load_run(run_id)
                    run.status = "blocked"
                    run.current_step = "amplify_prepared_form_mismatch"
                    self.store.save_run(run)
                    return {"status": "blocked", "summary": "Prepared Amplify form did not match the contract.", "review": amplify_prepared.to_dict()}
                task_text = build_amplify_submit_task(contract)
            elif option.target == "aws_s3_static_site":
                checkpoint_path = self.store.milestones_path(run_id)
                bucket_checkpoint = load_milestone_checkpoint(checkpoint_path, "prepare_s3_static_bucket", contract)
                if not bucket_checkpoint:
                    run = self.store.load_run(run_id)
                    run.status = "running"
                    run.current_step = "h_cua_prepare_s3_bucket"
                    run.target = option.target
                    self.store.save_run(run)
                    active_cost = start_run_cost_clock(self.store.run_dir(run_id))
                    cost_clock_started = active_cost is not None
                    if active_cost:
                        self.cost_monitor.register(self.repo_path, run_id)
                        self.store.append_event(run_id, "system", "cost_started", "Started the deployment cost clock before the S3 bucket-creation milestone.", {"cost_policy": active_cost.to_dict()})
                    bucket_result = run_h_task(
                        build_s3_creation_task(contract),
                        run.mode,
                        max_steps=40,
                        max_time_s=600,
                        skill_names=[skill.name],
                        event_callback=self._h_event_callback(run_id, "prepare_s3_static_bucket"),
                        answer_schema_name="s3_creation",
                    )
                    bucket_review = review_s3_bucket(bucket_result, contract)
                    self.store.append_event(run_id, "codex", "milestone_review", f"Supervisor reviewed S3 bucket preparation: {bucket_review.status}.", bucket_review.to_dict())
                    if bucket_review.status == "clear":
                        save_milestone_checkpoint(checkpoint_path, "prepare_s3_static_bucket", contract, asdict(bucket_result), bucket_review.to_dict())
                    else:
                        run = self.store.load_run(run_id)
                        run.status = "blocked"
                        run.current_step = "s3_bucket_preparation_blocked"
                        self.store.save_run(run)
                        self._write_lesson(
                            run_id,
                            skill.name,
                            "H CUA did not finish the bounded S3 bucket-preparation milestone.",
                            {"result": asdict(bucket_result), "review": bucket_review.to_dict()},
                            "Create or reuse only the exact run-tagged bucket, then checkpoint before website configuration.",
                            "Test that a partial or incorrectly tagged S3 bucket blocks website configuration.",
                        )
                        return {"status": "blocked", "summary": "S3 bucket preparation did not match the contract.", "review": bucket_review.to_dict()}
                else:
                    self.store.append_event(run_id, "codex", "milestone_reused", "Reused the contract-matching S3 bucket checkpoint.", {"milestone": "prepare_s3_static_bucket"})
                task_text = build_s3_website_task(contract)
            else:
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
            run.current_step = "h_cua_create_ecs_service" if option.target == "aws_ecs_express" else f"h_cua_{option.target}"
            run.target = option.target
            self.store.save_run(run)
            self.store.append_event(run_id, "h_cua", "milestone", "H CUA is executing the approved deployment milestone.", {"mode": run.mode, "aws_target": option.target, "max_spend_usd": max_spend_usd, "skill_name": skill.name, "milestone": "create_ecs_express_service" if option.target == "aws_ecs_express" else "deploy"})
            active_cost = None if cost_clock_started else start_run_cost_clock(self.store.run_dir(run_id))
            if active_cost:
                self.cost_monitor.register(self.repo_path, run_id)
                self.store.append_event(run_id, "system", "cost_started", "Started the deployment cost clock before the resource-creation milestone.", {"cost_policy": active_cost.to_dict()})
            result = run_h_task(
                task_text,
                run.mode,
                max_steps=60,
                max_time_s=900,
                skill_names=[skill.name],
                event_callback=self._h_event_callback(run_id, "create_ecs_express_service" if option.target == "aws_ecs_express" else "deploy"),
                answer_schema_name=(
                    "ecs_creation"
                    if option.target == "aws_ecs_express"
                    else "s3_creation"
                    if option.target == "aws_s3_static_site"
                    else "amplify_creation"
                    if option.target == "aws_amplify"
                    else None
                ),
            )
            self.store.append_event(run_id, "h_cua", "observation", result.summary, {"status": result.status, "session_id": result.session_id, "outcome": result.outcome})
            if option.target == "aws_s3_static_site" and result.status == "completed":
                s3_review = review_s3_website(result, contract)
                self.store.append_event(run_id, "codex", "milestone_review", f"Supervisor reviewed S3 website configuration: {s3_review.status}.", s3_review.to_dict())
                if s3_review.status == "clear" and static_artifact:
                    policy = apply_s3_public_read_policy(contract)
                    self.store.append_event(run_id, "system", "result", policy.summary, policy.to_dict())
                    if policy.status == "passed":
                        upload = upload_static_artifact(static_artifact.output_directory, s3_review.bucket_name)
                        self.store.append_event(run_id, "system", "result", upload.summary, upload.to_dict())
                        if upload.status == "passed":
                            result = HTaskResult(
                                "completed",
                                json.dumps(
                                    {
                                        "milestone": "configure_s3_static_website",
                                        "status": "completed",
                                        "bucket_name": s3_review.bucket_name,
                                        "region": contract.cloud_region,
                                        "tags": contract.required_tags,
                                        "website_enabled": True,
                                        "public_app_url": policy.public_url,
                                        "blockers": [],
                                    }
                                ),
                                session_id=result.session_id,
                                outcome=result.outcome,
                            )
                        else:
                            result = HTaskResult("blocked", upload.summary, session_id=result.session_id, outcome=result.outcome)
                    else:
                        result = HTaskResult("blocked", policy.summary, session_id=result.session_id, outcome=result.outcome)
                else:
                    result = HTaskResult("blocked", "S3 console result did not match the deployment contract: " + "; ".join(s3_review.objections), session_id=result.session_id, outcome=result.outcome)
            if option.target == "aws_amplify" and result.status == "completed":
                amplify_creation = review_amplify_creation(result, contract)
                self.store.append_event(run_id, "codex", "milestone_review", f"Supervisor reviewed Amplify creation: {amplify_creation.status}.", amplify_creation.to_dict())
                if amplify_creation.status != "clear":
                    result = HTaskResult("blocked", "Amplify creation did not match the deployment contract: " + "; ".join(amplify_creation.objections), session_id=result.session_id, outcome=result.outcome)
            review = review_h_result(result, contract)
            self.store.append_event(run_id, "codex", "observation_review", f"Reviewed H CUA result: {review.status}.", review.to_dict())
            if result.status == "completed" and review.status != "blocked":
                self._record_resource_summary(run_id, run.cloud, option.target, result.summary)
                run.status = "verifying"
                run.current_step = "h_cua_completed_run_verifier_next"
                self.store.save_run(run)
                self.run_verifier(run_id, "default")
                self.write_report(run_id)
            else:
                run.status = "blocked" if result.status in {"blocked", "timed_out", "completed"} or review.status == "blocked" else "failed"
                run.current_step = "h_cua_aws_task_blocked"
                self.store.save_run(run)
                self._write_lesson(
                    run_id,
                    skill.name,
                    f"H CUA deployment milestone ended with status {result.status} and supervisor review {review.status}.",
                    {"summary": result.summary, "outcome": result.outcome, "error": result.error, "review": review.to_dict()},
                    "Stop the deployment when H cannot complete a skill milestone and preserve its blocker for review.",
                    "Test that blocked, timed-out, and failed H milestones cannot advance to verification.",
                )
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

        skill = skill_for_target(plan.target)
        if skill is None:
            return {"status": "blocked", "summary": f"No approved deployment skill exists for {plan.target}."}
        skill_sync = sync_h_skills(self.repo_path, names=[skill.name])
        self.store.append_event(run_id, "system", "skill_sync", skill_sync.message, {"skill": skill.to_dict(include_body=False), "sync": skill_sync.to_dict()})
        if skill_sync.status != "passed":
            run.status = "blocked"
            run.current_step = "h_skill_sync_blocked"
            self.store.save_run(run)
            return {"status": "blocked", "summary": skill_sync.message, "skill_sync": skill_sync.to_dict()}

        task_text = build_gcp_cloud_run_h_task(self.repo_path.name, ctx, plan, task)
        run.status = "running"
        run.current_step = "h_cua_gcp_cloud_run"
        run.target = plan.target
        self.store.save_run(run)
        self.store.append_event(run_id, "h_cua", "command", task_text, {"mode": run.mode, "gcp_target": plan.target, "skill_name": skill.name})
        result = run_h_task(
            task_text,
            run.mode,
            max_steps=60,
            max_time_s=900,
            skill_names=[skill.name],
            event_callback=self._h_event_callback(run_id, "gcp_cloud_run"),
        )
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
        elif run.current_step == "runtime_configuration_ready":
            run.status = "running"
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

    def get_runtime_configuration(self, run_id: str) -> dict:
        ctx = analyze_repo(self.repo_path)
        return load_runtime_configuration(self.store.run_dir(run_id), ctx.env_vars).to_dict()

    def get_browser_identity(self, run_id: str) -> dict:
        proof = load_browser_identity(self.store.run_dir(run_id) / "browser-identity.json")
        return proof.to_dict() if proof else {"status": "not_checked", "message": "Browser account identity has not been checked."}

    def get_cost_status(self, run_id: str) -> dict:
        self.cost_monitor.register(self.repo_path, run_id)
        return self.cost_monitor.evaluate(self.repo_path, run_id)

    def request_cost_extension(self, run_id: str, new_cap_usd: float) -> dict:
        path = self.store.run_dir(run_id) / "cost-policy.json"
        policy = load_cost_policy(path)
        if not policy:
            return {"status": "blocked", "summary": "No cost policy exists for this run."}
        if new_cap_usd <= policy.max_spend_usd:
            return {"status": "blocked", "summary": "The new cap must be greater than the current cap."}
        action = f"Extend Cloud CUA cost policy to ${new_cap_usd:.2f}"
        if not approval_is_approved(self.store.run_dir(run_id), action):
            return self.request_approval(run_id, action, "This permits tagged resources from this run to continue accruing estimated AWS charges.", "high")
        policy.max_spend_usd = new_cap_usd
        policy.deadline_at = ""
        policy = start_cost_clock(policy)
        save_cost_policy(path, policy)
        run = self.store.load_run(run_id)
        if run.status == "cost_action_required":
            run.status = "running"
            run.current_step = "cost_extension_approved"
            self.store.save_run(run)
        self.store.append_event(run_id, "user", "approval", f"Extended run cost policy to ${new_cap_usd:.2f}.", {"cost_policy": policy.to_dict()})
        return policy.to_dict()

    def configure_runtime(
        self,
        run_id: str,
        values: dict[str, str],
        existing_references: dict[str, str],
        region: str = "us-east-1",
    ) -> dict:
        run = self.store.load_run(run_id)
        if run.cloud != "aws":
            return {"status": "blocked", "message": "AWS SSM runtime configuration requires an AWS run."}
        if run.status == "waiting_for_login":
            return {"status": "blocked", "message": "Verify cloud login before provisioning runtime configuration."}
        identity = verify_aws_identity()
        try:
            account_id = str(json.loads(identity.summary).get("Account") or "")
        except (TypeError, json.JSONDecodeError):
            account_id = ""
        if identity.status != "passed" or not account_id:
            return {"status": "blocked", "message": "AWS CLI identity must be verified before provisioning SSM parameters."}
        ctx = analyze_repo(self.repo_path)
        result = provision_aws_runtime_configuration(
            self.store.run_dir(run_id),
            run_id,
            self.repo_path.name,
            ctx.env_vars,
            values,
            existing_references,
            region=region,
            account_id=account_id,
        )
        run.status = "running"
        run.current_step = "runtime_configuration_ready"
        self.store.save_run(run)
        self.store.append_event(
            run_id,
            "system",
            "result",
            result.message,
            {"references": [asdict(item) for item in result.references], "public_build_names": result.public_build_names},
        )
        return result.to_dict()

    def list_approvals(self, run_id: str) -> list[dict]:
        return [asdict(item) for item in load_approvals(self.store.run_dir(run_id))]

    def voice_command(self, run_id: str, text: str) -> dict:
        route = classify_voice_command(text)
        self.store.append_event(run_id, "user", "voice_command", route.transcript, asdict(route))
        response = ""
        executed = False
        ui_action = None
        if route.classification == "direct_control":
            if route.action == "pause":
                self.pause(run_id)
                response, executed = "Deployment paused.", True
            elif route.action == "resume":
                self.resume(run_id)
                response, executed = "Deployment resumed.", True
            elif route.action == "stop":
                self.cancel(run_id)
                response, executed = "Deployment cancelled. Existing cloud resources were not deleted.", True
            elif route.action == "set_mode" and route.mode:
                self.set_mode(run_id, route.mode)
                response, executed = f"Switched to {route.mode} mode.", True
            elif route.action == "run_verifier":
                self.run_verifier(run_id, "default")
                response, executed = "Independent verification completed.", True
            elif route.action == "open_logs":
                response, executed, ui_action = "Opening the Activity timeline.", True, "open_logs"
            elif route.action == "mute_voice":
                response, executed, ui_action = "Voice playback muted for this dashboard session.", True, "mute_voice"
        elif route.classification == "reasoning_question":
            run = self.store.load_run(run_id)
            context = analyze_repo(self.repo_path)
            cost = self.get_cost_status(run_id) if (self.store.run_dir(run_id) / "cost-policy.json").exists() else None
            response = explain_run_question(route.transcript, run, context, cost)
            executed = True
            self.store.append_event(run_id, "codex", "explanation", response, {"question": route.transcript})
        elif route.classification == "planned_cloud_action":
            pending = self._record_pending_action(run_id, route.transcript)
            response = "Cloud operation request saved for planning and approval. It was not sent directly to H CUA."
            executed = True
            self.store.append_event(run_id, "codex", "plan", response, {"pending_action": pending})
        else:
            response = "Command not recognized. Try pause, resume, cancel, verify, switch mode, or ask why this service was selected."
        return {**asdict(route), "executed": executed, "response": response, "ui_action": ui_action}

    def get_pending_actions(self, run_id: str) -> list[dict]:
        path = self.store.run_dir(run_id) / "pending-actions.json"
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def watch_run(self, run_id: str, cursor: int = 0, timeout_seconds: int = 20) -> dict:
        timeout_seconds = max(0, min(timeout_seconds, 25))
        deadline = time.monotonic() + timeout_seconds
        while True:
            events = self.store.read_events(run_id, 0)
            run = self.store.load_run(run_id)
            if len(events) > cursor or run.status in {"completed", "blocked", "failed", "cancelled", "cost_action_required"} or time.monotonic() >= deadline:
                return {"cursor": len(events), "events": events[cursor:], "run": self.get_status(run_id), "pending_actions": self.get_pending_actions(run_id)}
            time.sleep(0.25)

    def _record_pending_action(self, run_id: str, request: str) -> dict:
        path = self.store.run_dir(run_id) / "pending-actions.json"
        items = self.get_pending_actions(run_id)
        context = analyze_repo(self.repo_path)
        item = {
            "action_id": uuid4().hex,
            "status": "needs_plan_and_approval",
            "request": request,
            "recommended_target": context.recommendation,
            "created_at": now_iso(),
        }
        items.append(item)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(items, indent=2), encoding="utf-8")
        temporary.replace(path)
        return item

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
        report_path = write_report(self.repo_path, run_id)
        out_dir = self.store.verifier_dir(run_id)
        results = []
        verifier_urls: list[str] = []
        report_result = VerifierResult(
            "report_written",
            "passed" if report_path.exists() else "failed",
            "DEPLOYMENT_REPORT.md",
            f"Deployment report exists at {report_path}." if report_path.exists() else "Deployment report was not written.",
        )
        results.append(asdict(report_result.save(out_dir)))
        repo_context = analyze_repo(self.repo_path)
        for result in verify_repository(self.repo_path, repo_context, run_tests=verifier_name in {"repo-full", "full"}):
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
                if self.store.contract_path(run_id).exists():
                    ecs_contract_result = verify_ecs_contract(run_id, load_contract(self.store.contract_path(run_id)))
                    aws_results.append(ecs_contract_result)
                    try:
                        contract_evidence = json.loads(ecs_contract_result.summary)
                        for service in contract_evidence.get("services", []):
                            for endpoint in service.get("endpoints", []):
                                verifier_urls.append(endpoint if str(endpoint).startswith("http") else f"https://{endpoint}")
                    except (json.JSONDecodeError, TypeError):
                        pass
                else:
                    aws_results.append(VerifierResult("aws_ecs_contract", "failed", "contract.json", "Saved deployment contract is missing."))
            if run.target == "aws_amplify":
                amplify_plan = build_amplify_plan(self.repo_path.name, repo_context)
                exact = verify_amplify_run(run_id, amplify_plan.app_name)
                aws_results.append(exact)
                try:
                    exact_data = json.loads(exact.summary)
                    for app in exact_data.get("apps", []):
                        verifier_urls.extend(app.get("urls", []))
                except (json.JSONDecodeError, TypeError):
                    pass
            if run.target == "aws_s3_static_site":
                exact = verify_s3_static_run(run_id)
                aws_results.append(exact)
                try:
                    exact_data = json.loads(exact.summary)
                    verifier_urls.extend(item.get("url") for item in exact_data.get("buckets", []) if item.get("url"))
                except (json.JSONDecodeError, TypeError):
                    pass
            if self.store.contract_path(run_id).exists():
                contract = load_contract(self.store.contract_path(run_id))
                if contract.runtime_secret_references:
                    aws_results.append(verify_runtime_secret_references(contract))
            event_names = {
                "aws_ecs_express": ["CreateService", "CreateTaskSet"],
                "aws_amplify": ["CreateApp", "CreateBranch", "StartDeployment"],
                "aws_s3_static_site": ["CreateBucket", "PutBucketWebsite", "PutObject"],
            }.get(run.target, [])
            if event_names:
                aws_results.append(verify_cloudtrail_run(run_id, event_names, run.created_at))
            if run.target in {"aws_ecs_express", "aws_ecs_fargate", "aws_amplify", "aws_s3_static_site"}:
                cleanup = cleanup_cloud_cua_aws_resources(run_id=run_id, dry_run=True)
                cleanup_status = "passed" if cleanup.status == "passed" and cleanup.actions else "failed"
                aws_results.append(
                    VerifierResult(
                        "cleanup_discovery",
                        cleanup_status,
                        "cloud-cua aws-cleanup --run-id <run-id>",
                        cleanup.summary if cleanup.actions else "Cleanup could not discover any resource belonging to this run.",
                    )
                )
            for result in aws_results:
                results.append(asdict(result.save(out_dir)))
        else:
            for result in [verify_gcp_identity(), verify_gcp_project(), verify_gcp_cloud_run_services()]:
                results.append(asdict(result.save(out_dir)))
        urls = ([url] if url else []) + verifier_urls
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
            resolved = resolve_lesson_candidate(
                self.store.run_dir(run_id),
                "The run later passed every required independent verifier.",
            )
            if resolved:
                self.store.append_event(
                    run_id,
                    "codex",
                    "lesson_resolved",
                    "Resolved the stale lesson candidate after strict verification passed.",
                    {"affected_skill": resolved.get("affected_skill"), "resolved_at": resolved.get("resolved_at")},
                )
        else:
            run.status = "blocked"
        self.store.save_run(run)
        failed_results = [item for item in results if item["status"] == "failed"]
        if failed_results:
            skill_name = ""
            if self.store.contract_path(run_id).exists():
                skill_name = load_contract(self.store.contract_path(run_id)).skill_name
            self._write_lesson(
                run_id,
                skill_name or f"cloud-cua/{run.target.replace('_', '-')}",
                "Independent deployment verification failed.",
                {"failed_verifiers": failed_results},
                "Do not mark a deployment complete until every verifier required by the active skill passes.",
                "Reproduce each failed verifier with a fixture and prove the run remains blocked.",
            )
        write_report(self.repo_path, run_id)
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

    def get_skill_status(self) -> dict:
        remote = get_h_skill_status(self.repo_path).to_dict()
        remote_by_name = {item["name"]: item for item in remote["skills"]}
        return {
            **remote,
            "skills": [
                {
                    **skill.to_dict(include_body=False),
                    "h_status": remote_by_name.get(skill.name, {}).get("status", "unknown"),
                    "h_message": remote_by_name.get(skill.name, {}).get("message", ""),
                    "remote_hash": remote_by_name.get(skill.name, {}).get("remote_hash"),
                }
                for skill in load_skills()
            ],
        }

    def get_lesson_candidate(self, run_id: str) -> dict:
        lesson = load_lesson_candidate(self.store.run_dir(run_id))
        return lesson or {"status": "none", "run_id": run_id}

    def get_run_skill_state(self, run_id: str) -> dict:
        run = self.store.load_run(run_id)
        contract = load_contract(self.store.contract_path(run_id)) if self.store.contract_path(run_id).exists() else None
        skill = None
        if contract and contract.skill_name:
            try:
                skill = get_skill(contract.skill_name)
            except KeyError:
                skill = None
        if skill is None:
            skill = skill_for_target(run.target)
        events = self.store.read_events(run_id, limit=500)
        sync_event = next((event for event in reversed(events) if event["type"] == "skill_sync"), None)
        sync_status = "not_synced"
        if sync_event:
            sync_items = sync_event.get("evidence", {}).get("sync", {}).get("skills", [])
            matching = next((item for item in sync_items if not skill or item.get("name") == skill.name), None)
            sync_status = matching.get("status", "unknown") if matching else sync_event.get("evidence", {}).get("sync", {}).get("status", "unknown")
        contract_data = contract.to_dict() if contract else {}
        present_facts = _present_contract_facts(contract_data)
        required_facts = skill.required_facts if skill else []
        missing_facts = [fact for fact in required_facts if fact not in present_facts]
        if contract:
            missing_facts.extend(item for item in contract.missing_facts if item not in missing_facts)
        return {
            "run_id": run_id,
            "active_skill": skill.to_dict(include_body=False) if skill else None,
            "h_sync_status": sync_status,
            "contract": contract_data or None,
            "present_facts": sorted(present_facts),
            "missing_facts": missing_facts,
            "verifier_gates": skill.required_verifiers if skill else [],
            "lesson_candidate": load_lesson_candidate(self.store.run_dir(run_id)),
        }

    def sync_h_skills(self, names: list[str] | None = None, dry_run: bool = False) -> dict:
        return sync_h_skills(self.repo_path, names=names, dry_run=dry_run).to_dict()

    def _record_resource_summary(self, run_id: str, cloud: str, target: str, summary: str) -> None:
        record = extract_resource_record(run_id, cloud, target, summary)
        path = save_resource_record(self.store.run_dir(run_id) / "resources.json", record)
        self.store.append_event(run_id, "system", "result", "Recorded resource hints from H CUA final answer.", {"path": str(path), "record": asdict(record)})

    def _h_event_callback(self, run_id: str, milestone: str):
        def record(event: dict) -> None:
            self.h_sessions.observe_event(self.repo_path, run_id, milestone, event)
            evidence = {"milestone": milestone, "h_event_type": event.get("type", "trajectory_event")}
            data = event.get("data")
            if isinstance(data, dict):
                for key in ("session_id", "agent_view_url", "status", "outcome"):
                    if data.get(key) not in {None, ""}:
                        evidence[key] = data[key]
            self.store.append_event(
                run_id,
                "h_cua",
                "trajectory",
                summarize_h_event(event),
                evidence,
            )

        return record

    def _write_lesson(
        self,
        run_id: str,
        affected_skill: str,
        failure: str,
        evidence: dict,
        proposed_rule: str,
        required_test: str,
    ) -> None:
        path = write_lesson_candidate(
            self.store.run_dir(run_id),
            run_id=run_id,
            affected_skill=affected_skill,
            failure=failure,
            evidence=evidence,
            proposed_rule=proposed_rule,
            required_test=required_test,
        )
        self.store.append_event(
            run_id,
            "codex",
            "lesson_candidate",
            "Recorded a skill lesson candidate for review; it was not auto-promoted.",
            {"path": str(path), "affected_skill": affected_skill},
        )


def _present_contract_facts(contract: dict) -> set[str]:
    present = {key for key, value in contract.items() if value is not None and value != "" and value != [] and value != {}}
    if contract.get("cloud_region"):
        present.update({"aws_region", "google_cloud_region"})
    if contract.get("required_tags", {}).get("cloud-cua-run"):
        present.update({"cloud_cua_run_tag"})
    return present
