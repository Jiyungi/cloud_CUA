from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from .aws_evals import AWSServiceEval, load_aws_eval_catalog
from .skill_registry import SKILLS_DIR


SOURCE_URL = "https://github.com/Jiyungi/cloud_CUA/blob/main/docs/aws-h-evaluation-catalog.md"
RULES_MARKER = "## Evaluation-derived service rules"


@dataclass(frozen=True)
class SkillMaterializationResult:
    status: str
    output_directory: str
    created: tuple[str, ...]
    updated: tuple[str, ...]
    unchanged: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def materialize_aws_eval_skills(output_directory: str | Path | None = None) -> SkillMaterializationResult:
    root = Path(output_directory) if output_directory else SKILLS_DIR
    root.mkdir(parents=True, exist_ok=True)
    existing = _existing_skills(root)
    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []

    for service in load_aws_eval_catalog().services:
        current = existing.get(service.skill_name)
        path = current[0] if current else root / f"aws_eval_{service.id.replace('-', '_')}.yaml"
        payload = _merge_skill(current[1], service) if current else _new_skill(service)
        rendered = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, width=120)
        before = path.read_text(encoding="utf-8") if path.exists() else None
        if before == rendered:
            unchanged.append(service.skill_name)
            continue
        path.write_text(rendered, encoding="utf-8", newline="\n")
        (updated if current else created).append(service.skill_name)

    return SkillMaterializationResult(
        status="passed",
        output_directory=str(root.resolve()),
        created=tuple(created),
        updated=tuple(updated),
        unchanged=tuple(unchanged),
    )


def _existing_skills(root: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    found: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in sorted(root.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("name"), str):
            found[raw["name"]] = (path, raw)
    return found


def _new_skill(service: AWSServiceEval) -> dict[str, Any]:
    facts = _facts(service)
    return {
        "name": service.skill_name,
        "description": f"Operate {service.name} through its AWS console with reviewed facts, safety stops, proof, and cleanup gates.",
        "target": service.skill_target,
        "autonomy_level": 1,
        "source": SOURCE_URL,
        "url_pattern": service.console_url,
        "required_facts": facts,
        "unknowns_that_block": [f"Required fact is missing or unverified: {fact}" for fact in facts],
        "h_cua_allowed_actions": _allowed_actions(service),
        "h_cua_stop_conditions": list(service.common_warnings),
        "required_verifiers": _evidence(service),
        "success_conditions": [case.objective for case in service.cases],
        "cleanup_strategy": _cleanup_strategy(service),
        "body": _body(service),
    }


def _merge_skill(current: dict[str, Any], service: AWSServiceEval) -> dict[str, Any]:
    if current.get("source") == SOURCE_URL:
        return _new_skill(service)
    merged = dict(current)
    merged["required_facts"] = _union(current.get("required_facts"), _facts(service))
    merged["unknowns_that_block"] = _union(
        current.get("unknowns_that_block"),
        [f"Required fact is missing or unverified: {fact}" for fact in _facts(service)],
    )
    merged["h_cua_allowed_actions"] = _union(current.get("h_cua_allowed_actions"), _allowed_actions(service))
    merged["h_cua_stop_conditions"] = _union(current.get("h_cua_stop_conditions"), service.common_warnings)
    merged["required_verifiers"] = _union(current.get("required_verifiers"), _evidence(service))
    merged["success_conditions"] = _union(current.get("success_conditions"), [case.objective for case in service.cases])
    body = str(current.get("body") or "").rstrip()
    if RULES_MARKER not in body:
        body = f"{body}\n\n{_body(service, heading=RULES_MARKER)}"
    merged["body"] = body + "\n"
    return merged


def _facts(service: AWSServiceEval) -> list[str]:
    return sorted({fact for case in service.cases for fact in case.required_fact_keys})


def _evidence(service: AWSServiceEval) -> list[str]:
    return sorted(
        {
            evidence
            for case in service.cases
            for evidence in (*case.required_evidence_keys, *case.cleanup_evidence_keys)
        }
    )


def _allowed_actions(service: AWSServiceEval) -> list[str]:
    return [
        f"Inspect {service.name} console state without mutation.",
        "Compare every visible selection with the approved run contract.",
        "Perform only the bounded, approved service action after required facts are verified.",
        "Return structured resource, verifier, blocker, and cleanup evidence.",
    ]


def _cleanup_strategy(service: AWSServiceEval) -> str:
    cleanup = sorted({item for case in service.cases for item in case.cleanup_evidence_keys})
    return "Delete only exact run-owned resources and prove: " + ", ".join(cleanup) + "."


def _body(service: AWSServiceEval, *, heading: str | None = None) -> str:
    rules = list(dict.fromkeys(rule for case in service.cases for rule in case.skill_rules))
    lines = [heading or f"# Operate {service.name}", ""]
    lines.extend(
        [
            "Use the run contract as the source of truth. Inspect before mutation and stop when a required fact is unknown.",
            "A console success label is not proof; independent service, workload, and cleanup evidence decide success.",
            "",
            "Required sequence:",
            "1. Confirm account, region, ownership tags, cost boundary, and service-specific facts.",
            "2. Inspect defaults and report mismatches before editing anything.",
            "3. Mutate only after approval and only within the exact run-owned resource boundary.",
            "4. Stop on new IAM, public exposure, destructive, cross-account, secret, or billing decisions.",
            "5. Return structured evidence and verify cleanup dependencies before declaring completion.",
            "",
            "Service rules:",
        ]
    )
    lines.extend(f"- {rule}" for rule in rules)
    lines.extend(["", "Evaluation scenarios:"])
    lines.extend(f"- {case.id}: {case.objective}" for case in service.cases)
    return "\n".join(lines)


def _union(current: Any, additions: list[str]) -> list[str]:
    values = [str(item) for item in current] if isinstance(current, list) else []
    return list(dict.fromkeys([*values, *additions]))
