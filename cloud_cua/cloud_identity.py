from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .deployment_milestones import extract_json_object
from .h_runner import HTaskResult
from .run_store import now_iso


@dataclass(frozen=True)
class BrowserIdentityProof:
    status: str
    expected_account_id: str
    browser_account_id: str = ""
    account_alias: str = ""
    console_url: str = ""
    checked_at: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def build_aws_browser_identity_task(expected_account_id: str) -> str:
    return f"""Milestone: verify_aws_browser_identity

This is an inspect-only identity check. Do not create, edit, delete, deploy, authorize, or enter credentials.

In the already logged-in AWS Console, inspect the current account menu or another normal console identity surface and read the 12-digit AWS account ID. The independently authenticated AWS CLI expects account {expected_account_id}.

Return the structured answer with the visible account ID, optional account alias, current console URL, and any blocker. Do not claim a match yourself; Cloud CUA compares the values independently.
"""


def review_aws_browser_identity(result: HTaskResult, expected_account_id: str) -> BrowserIdentityProof:
    if result.status != "completed":
        return BrowserIdentityProof("blocked", expected_account_id, message=f"H browser identity inspection ended with {result.status}: {result.summary}", checked_at=now_iso())
    observation = extract_json_object(result.summary)
    if not observation:
        return BrowserIdentityProof("blocked", expected_account_id, message="H did not return structured browser identity evidence.", checked_at=now_iso())
    visible = re.sub(r"\D", "", str(observation.get("account_id") or ""))
    if len(visible) != 12:
        return BrowserIdentityProof(
            "blocked",
            expected_account_id,
            visible,
            str(observation.get("account_alias") or ""),
            str(observation.get("console_url") or ""),
            now_iso(),
            "The browser account ID was not a readable 12-digit AWS account ID.",
        )
    matched = visible == expected_account_id
    return BrowserIdentityProof(
        "matched" if matched else "mismatched",
        expected_account_id,
        visible,
        str(observation.get("account_alias") or ""),
        str(observation.get("console_url") or ""),
        now_iso(),
        "Browser and AWS CLI account IDs match." if matched else "Browser and AWS CLI account IDs do not match.",
    )


def save_browser_identity(path: Path, proof: BrowserIdentityProof) -> Path:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(proof.to_dict(), indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def load_browser_identity(path: Path) -> BrowserIdentityProof | None:
    if not path.exists():
        return None
    try:
        return BrowserIdentityProof(**json.loads(path.read_text(encoding="utf-8")))
    except (OSError, TypeError, json.JSONDecodeError):
        return None
