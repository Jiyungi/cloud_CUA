from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4


@dataclass
class Approval:
    approval_id: str
    action: str
    reason: str
    risk_level: str
    status: str = "pending"
    triggers: list[str] | None = None


def approvals_path(run_dir: Path) -> Path:
    return run_dir / "approvals.json"


def load_approvals(run_dir: Path) -> list[Approval]:
    path = approvals_path(run_dir)
    if not path.exists():
        return []
    approvals: list[Approval] = []
    for item in json.loads(path.read_text(encoding="utf-8")):
        item.setdefault("triggers", None)
        approvals.append(Approval(**item))
    return approvals


def save_approvals(run_dir: Path, approvals: list[Approval]) -> None:
    path = approvals_path(run_dir)
    path.write_text(json.dumps([asdict(item) for item in approvals], indent=2), encoding="utf-8")


def create_approval(run_dir: Path, action: str, reason: str, risk_level: str = "medium", triggers: list[str] | None = None) -> Approval:
    approvals = load_approvals(run_dir)
    for existing in approvals:
        if existing.action == action and existing.status == "pending":
            return existing
    approval = Approval(uuid4().hex[:12], action, reason, risk_level, "pending", triggers)
    approvals.append(approval)
    save_approvals(run_dir, approvals)
    return approval


def decide_approval(run_dir: Path, approval_id: str, approved: bool) -> Approval:
    approvals = load_approvals(run_dir)
    for approval in approvals:
        if approval.approval_id == approval_id:
            approval.status = "approved" if approved else "denied"
            save_approvals(run_dir, approvals)
            return approval
    raise KeyError(f"approval not found: {approval_id}")


def approved(run_dir: Path, action: str) -> bool:
    return any(item.action == action and item.status == "approved" for item in load_approvals(run_dir))


def voice_action_name(action: str) -> str:
    for prefix in ("Run AWS deployment task:", "Approval required:", "Approve:"):
        if action.lower().startswith(prefix.lower()):
            action = action[len(prefix) :].strip()
            break
    return " ".join(action.rstrip(".:").split())


def voice_approval_phrase(approval: Approval) -> str:
    return f"Approve {voice_action_name(approval.action)}"
