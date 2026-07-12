from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field

from .deployments.aws_general import RESOURCE_PREFIX


@dataclass
class CleanupAction:
    service: str
    resource: str
    command: list[str]
    status: str = "planned"
    summary: str = ""


@dataclass
class CleanupResult:
    status: str
    dry_run: bool
    actions: list[CleanupAction] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "dry_run": self.dry_run,
            "summary": self.summary,
            "actions": [asdict(action) for action in self.actions],
        }


def cleanup_cloud_cua_aws_resources(*, run_id: str | None = None, dry_run: bool = True) -> CleanupResult:
    actions = discover_cleanup_actions(run_id=run_id)
    if dry_run:
        return CleanupResult("passed", True, actions, f"Dry run found {len(actions)} Cloud CUA cleanup action(s).")
    completed: list[CleanupAction] = []
    for action in actions:
        completed.append(_execute_action(action))
    failed = [action for action in completed if action.status == "failed"]
    status = "failed" if failed else "passed"
    return CleanupResult(status, False, completed, f"Executed {len(completed)} cleanup action(s); {len(failed)} failed.")


def discover_cleanup_actions(*, run_id: str | None = None) -> list[CleanupAction]:
    actions: list[CleanupAction] = []
    actions.extend(_amplify_actions())
    actions.extend(_app_runner_actions())
    actions.extend(_lambda_actions())
    actions.extend(_cloudformation_actions())
    actions.extend(_s3_actions())
    actions.extend(_ecr_actions())
    actions.extend(_tagged_resource_actions(run_id))
    return _dedupe_actions(actions)


def _amplify_actions() -> list[CleanupAction]:
    data = _aws_json(["aws", "amplify", "list-apps"])
    actions: list[CleanupAction] = []
    for app in data.get("apps", []) if isinstance(data, dict) else []:
        name = str(app.get("name", ""))
        app_id = str(app.get("appId", ""))
        if _cloud_cua_named(name) and app_id:
            actions.append(CleanupAction("amplify", name, ["aws", "amplify", "delete-app", "--app-id", app_id]))
    return actions


def _app_runner_actions() -> list[CleanupAction]:
    data = _aws_json(["aws", "apprunner", "list-services"])
    actions: list[CleanupAction] = []
    for service in data.get("ServiceSummaryList", []) if isinstance(data, dict) else []:
        name = str(service.get("ServiceName", ""))
        arn = str(service.get("ServiceArn", ""))
        if _cloud_cua_named(name) and arn:
            actions.append(CleanupAction("apprunner", name, ["aws", "apprunner", "delete-service", "--service-arn", arn]))
    return actions


def _lambda_actions() -> list[CleanupAction]:
    data = _aws_json(["aws", "lambda", "list-functions", "--max-items", "100"])
    actions: list[CleanupAction] = []
    for fn in data.get("Functions", []) if isinstance(data, dict) else []:
        name = str(fn.get("FunctionName", ""))
        if _cloud_cua_named(name):
            actions.append(CleanupAction("lambda", name, ["aws", "lambda", "delete-function", "--function-name", name]))
    return actions


def _cloudformation_actions() -> list[CleanupAction]:
    data = _aws_json(["aws", "cloudformation", "list-stacks", "--stack-status-filter", "CREATE_COMPLETE", "UPDATE_COMPLETE", "ROLLBACK_COMPLETE"])
    actions: list[CleanupAction] = []
    for stack in data.get("StackSummaries", []) if isinstance(data, dict) else []:
        name = str(stack.get("StackName", ""))
        if _cloud_cua_named(name):
            actions.append(CleanupAction("cloudformation", name, ["aws", "cloudformation", "delete-stack", "--stack-name", name]))
    return actions


def _s3_actions() -> list[CleanupAction]:
    data = _aws_json(["aws", "s3api", "list-buckets"])
    actions: list[CleanupAction] = []
    for bucket in data.get("Buckets", []) if isinstance(data, dict) else []:
        name = str(bucket.get("Name", ""))
        if _cloud_cua_named(name):
            actions.append(CleanupAction("s3", name, ["aws", "s3", "rb", f"s3://{name}", "--force"]))
    return actions


def _ecr_actions() -> list[CleanupAction]:
    data = _aws_json(["aws", "ecr", "describe-repositories"])
    actions: list[CleanupAction] = []
    for repo in data.get("repositories", []) if isinstance(data, dict) else []:
        name = str(repo.get("repositoryName", ""))
        if _cloud_cua_named(name):
            actions.append(CleanupAction("ecr", name, ["aws", "ecr", "delete-repository", "--repository-name", name, "--force"]))
    return actions


def _tagged_resource_actions(run_id: str | None) -> list[CleanupAction]:
    filters = ["Key=cloud-cua,Values=true"]
    if run_id:
        filters.append(f"Key=cloud-cua-run,Values={run_id}")
    command = ["aws", "resourcegroupstaggingapi", "get-resources", "--tag-filters", *filters]
    data = _aws_json(command)
    actions: list[CleanupAction] = []
    for item in data.get("ResourceTagMappingList", []) if isinstance(data, dict) else []:
        arn = str(item.get("ResourceARN", ""))
        action = _action_from_arn(arn)
        if action:
            actions.append(action)
    return actions


def _action_from_arn(arn: str) -> CleanupAction | None:
    if ":lambda:" in arn and ":function:" in arn:
        name = arn.rsplit(":function:", 1)[-1]
        return CleanupAction("lambda", name, ["aws", "lambda", "delete-function", "--function-name", name])
    if ":apprunner:" in arn and ":service/" in arn:
        name = arn.split(":service/", 1)[-1].split("/", 1)[0]
        return CleanupAction("apprunner", name, ["aws", "apprunner", "delete-service", "--service-arn", arn])
    if ":amplify:" in arn and ":apps/" in arn:
        app_id = arn.rsplit("/apps/", 1)[-1].split("/", 1)[0]
        return CleanupAction("amplify", app_id, ["aws", "amplify", "delete-app", "--app-id", app_id])
    if ":cloudformation:" in arn and ":stack/" in arn:
        stack_name = arn.split(":stack/", 1)[-1].split("/", 1)[0]
        return CleanupAction("cloudformation", stack_name, ["aws", "cloudformation", "delete-stack", "--stack-name", stack_name])
    if arn.startswith("arn:aws:s3:::"):
        bucket = arn.rsplit(":::", 1)[-1]
        return CleanupAction("s3", bucket, ["aws", "s3", "rb", f"s3://{bucket}", "--force"])
    if ":ecr:" in arn and ":repository/" in arn:
        name = arn.split(":repository/", 1)[-1]
        return CleanupAction("ecr", name, ["aws", "ecr", "delete-repository", "--repository-name", name, "--force"])
    return None


def _execute_action(action: CleanupAction) -> CleanupAction:
    try:
        proc = subprocess.run(action.command, text=True, capture_output=True, timeout=180)
    except Exception as exc:
        action.status = "failed"
        action.summary = f"{type(exc).__name__}: {exc}"
        return action
    action.status = "passed" if proc.returncode == 0 else "failed"
    action.summary = (proc.stdout or proc.stderr or f"exit {proc.returncode}").strip()[:800]
    return action


def _aws_json(command: list[str]) -> dict:
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=45)
    except Exception:
        return {}
    if proc.returncode != 0 or not proc.stdout.strip():
        return {}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {}


def _cloud_cua_named(name: str) -> bool:
    return name.startswith(f"{RESOURCE_PREFIX}-") or name.startswith("cloud-cua-")


def _dedupe_actions(actions: list[CleanupAction]) -> list[CleanupAction]:
    seen: set[tuple[str, str]] = set()
    deduped: list[CleanupAction] = []
    for action in actions:
        key = (action.service, action.resource)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped
