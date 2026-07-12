from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .deployment_contract import DeploymentContract


def contract_fingerprint(contract: DeploymentContract) -> str:
    payload = json.dumps(contract.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_milestone_checkpoint(
    path: Path,
    milestone: str,
    contract: DeploymentContract,
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    record = data.get(milestone)
    if not isinstance(record, dict):
        return None
    if record.get("contract_fingerprint") != contract_fingerprint(contract):
        return None
    review = record.get("review")
    if not isinstance(review, dict) or review.get("status") != "clear":
        return None
    return record


def save_milestone_checkpoint(
    path: Path,
    milestone: str,
    contract: DeploymentContract,
    result: dict[str, Any],
    review: dict[str, Any],
) -> Path:
    data: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError):
            pass
    data[milestone] = {
        "contract_fingerprint": contract_fingerprint(contract),
        "result": result,
        "review": review,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path
