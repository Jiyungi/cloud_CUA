from __future__ import annotations

import re
import json
from dataclasses import asdict, dataclass, field

from .deployment_contract import DeploymentContract
from .h_runner import HTaskResult


@dataclass(frozen=True)
class SupervisorFinding:
    severity: str
    message: str


@dataclass(frozen=True)
class SupervisorReview:
    status: str
    findings: list[SupervisorFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["findings"] = [asdict(item) for item in self.findings]
        return data


def review_h_result(result: HTaskResult, contract: DeploymentContract) -> SupervisorReview:
    text = f"{result.summary}\n{result.raw or ''}".lower()
    findings: list[SupervisorFinding] = []

    try:
        structured = json.loads(result.summary)
    except (json.JSONDecodeError, TypeError):
        structured = None
    if isinstance(structured, dict):
        reported_status = str(structured.get("status") or "").strip().lower()
        if reported_status in {"blocked", "failed", "infeasible", "timed_out", "timeout"}:
            findings.append(SupervisorFinding("blocked", f"H's structured answer reported status {reported_status}."))
        target_health = str(structured.get("target_health") or "").strip().lower()
        if target_health and target_health not in {"healthy", "passed"}:
            findings.append(SupervisorFinding("needs_verification", f"H reported target health {target_health}."))

    patterns = [
        ("blocked", r"\baccessdenied\b|access denied|permission denied", "H observed an access/permission problem."),
        ("blocked", r"\b0\s+running\b|0 tasks running|no running tasks", "H observed that no tasks were running."),
        ("blocked", r"unhealthy|health checks? failed|503 service unavailable", "H observed failed health or unavailable service."),
        ("blocked", r"deployment (is )?still in progress|deployment in progress|provisioning", "H observed deployment still in progress."),
        ("needs_verification", r"no tags|tags were not applied", "H observed missing tags before correction."),
        ("needs_verification", r"truncated|not accepting|disabled", "H observed input/control uncertainty."),
    ]
    for severity, pattern, message in patterns:
        if re.search(pattern, text):
            findings.append(SupervisorFinding(severity, message))

    if contract.required_public_app_url and "console.aws.amazon.com" in text and ".on.aws" not in text:
        findings.append(SupervisorFinding("blocked", "H reported a console URL but no public application URL."))
    if contract.selected_container_port is not None and str(contract.selected_container_port) not in text:
        findings.append(
            SupervisorFinding(
                "needs_verification",
                f"H final answer did not mention the selected container port {contract.selected_container_port}.",
            )
        )

    if any(item.severity == "blocked" for item in findings):
        status = "blocked"
    elif findings:
        status = "needs_verification"
    else:
        status = "clear"
    return SupervisorReview(status=status, findings=findings)
