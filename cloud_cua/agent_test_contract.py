from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .aws_evals import load_aws_eval_catalog


CONTRACT_FILENAME = "agent-test.json"
SERVICE_ALIASES = {
    "amplify-hosting": "amplify",
    "eventbridge-scheduler": "eventbridge",
}


@dataclass(frozen=True)
class AgentTestContract:
    fixture_id: str
    product_name: str
    cloud: str
    region: str
    git_branch: str
    app_root: str
    backend_initial_state: str
    required_aws_services: tuple[str, ...]
    public_environment_variables: tuple[str, ...]
    local_success_checks: tuple[str, ...]
    aws_success_checks: tuple[str, ...]
    required_tags: dict[str, str]
    matched_skill_names: tuple[str, ...]
    unmatched_services: tuple[str, ...]

    @property
    def requires_backend_implementation(self) -> bool:
        return self.backend_initial_state.lower() == "absent" and bool(self.required_aws_services)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_agent_test_contract(repo_path: str | Path) -> AgentTestContract | None:
    path = Path(repo_path).resolve() / CONTRACT_FILENAME
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{CONTRACT_FILENAME} must contain a JSON object.")
    required = ("fixture_id", "product_name", "cloud", "region", "backend_initial_state", "required_aws_services")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"{CONTRACT_FILENAME} is missing: {', '.join(missing)}")
    services = tuple(str(item) for item in raw["required_aws_services"])
    matched, unmatched = match_service_skills(services)
    return AgentTestContract(
        fixture_id=str(raw["fixture_id"]),
        product_name=str(raw["product_name"]),
        cloud=str(raw["cloud"]),
        region=str(raw["region"]),
        git_branch=str(raw.get("git_branch") or ""),
        app_root=str(raw.get("app_root") or ""),
        backend_initial_state=str(raw["backend_initial_state"]),
        required_aws_services=services,
        public_environment_variables=tuple(str(item) for item in raw.get("public_environment_variables") or []),
        local_success_checks=tuple(str(item) for item in raw.get("local_success_checks") or []),
        aws_success_checks=tuple(str(item) for item in raw.get("aws_success_checks") or []),
        required_tags={str(key): str(value) for key, value in (raw.get("required_tags") or {}).items()},
        matched_skill_names=matched,
        unmatched_services=unmatched,
    )


def match_service_skills(service_names: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    catalog = load_aws_eval_catalog()
    by_id = {service.id: service.skill_name for service in catalog.services}
    by_normalized_name = {_normalize(service.name): service.skill_name for service in catalog.services}
    matched: list[str] = []
    unmatched: list[str] = []
    for display_name in service_names:
        normalized = _normalize(display_name)
        service_id = SERVICE_ALIASES.get(normalized, normalized)
        skill_name = by_id.get(service_id) or by_normalized_name.get(normalized)
        if skill_name:
            matched.append(skill_name)
        else:
            unmatched.append(display_name)
    return tuple(dict.fromkeys(matched)), tuple(unmatched)


def _normalize(value: str) -> str:
    normalized = re.sub(r"^(amazon|aws)\s+", "", value.strip().lower())
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
