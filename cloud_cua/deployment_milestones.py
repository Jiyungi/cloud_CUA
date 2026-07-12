from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .deployment_contract import DeploymentContract
from .h_runner import HTaskResult


@dataclass(frozen=True)
class MilestoneReview:
    status: str
    observation: dict[str, Any] = field(default_factory=dict)
    objections: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_ecs_inspection_task(contract: DeploymentContract) -> str:
    return f"""Milestone: inspect_ecs_express_form

Navigate to the Amazon ECS Express Mode create-service form in {contract.cloud_region}. Do not type into fields, submit forms, create resources, change IAM, or modify AWS.

Inspect the visible service type, region, image field/default, container port default, health-check path default, tag controls, IAM choices, networking/public exposure choices, estimated cost, and any blockers. Compare nothing silently and do not guess hidden values.

A visible default that differs from the contract is not itself a blocker when the field can be edited. Put the needed change in required_corrections and set can_apply_contract=true. Set can_apply_contract=false only when the form cannot accept a required contract value.

Cloud CUA contract:
{json.dumps(contract.to_dict(), indent=2)}

Return one JSON object and no Markdown:
{{
  "milestone": "inspect_ecs_express_form",
  "status": "observed|blocked",
  "service_target": "aws_ecs_express",
  "region": "visible region or null",
  "visible_defaults": {{
    "image_uri": null,
    "container_port": null,
    "health_check_path": null,
    "public_exposure": null,
    "iam_scope": null,
    "estimated_cost": null
  }},
  "required_inputs_visible": [],
  "can_apply_contract": true,
  "required_corrections": [],
  "blockers": [],
  "console_url": "current AWS Console URL"
}}
"""


def review_ecs_inspection(result: HTaskResult, contract: DeploymentContract) -> MilestoneReview:
    if result.status != "completed":
        return MilestoneReview("blocked", objections=[f"H inspection ended with status {result.status}: {result.summary}"])
    observation = extract_json_object(result.summary)
    if observation is None:
        return MilestoneReview("blocked", objections=["H inspection did not return the required structured JSON object."])

    objections: list[str] = []
    corrections = [str(item) for item in observation.get("required_corrections", [])]
    if observation.get("milestone") != "inspect_ecs_express_form":
        objections.append("H returned the wrong milestone result.")
    if observation.get("service_target") != contract.target:
        objections.append(f"H inspected {observation.get('service_target')!r}, expected {contract.target!r}.")
    if observation.get("can_apply_contract") is not True:
        objections.append("H reported that the contract cannot be applied to the visible form.")
    blockers = observation.get("blockers") or []
    if blockers:
        objections.append("H reported blockers: " + "; ".join(str(item) for item in blockers))

    visible = observation.get("visible_defaults") if isinstance(observation.get("visible_defaults"), dict) else {}
    _compare_if_present(objections, "region", observation.get("region"), contract.cloud_region)
    _correction_if_different(corrections, "image URI", visible.get("image_uri"), contract.container_image_uri)
    _correction_if_different(corrections, "container port", visible.get("container_port"), contract.selected_container_port)
    _correction_if_different(corrections, "health check path", visible.get("health_check_path"), contract.health_check_path)
    return MilestoneReview("blocked" if objections else "clear", observation=observation, objections=objections, corrections=corrections)


def build_ecs_creation_task(contract: DeploymentContract, corrections: list[str] | None = None) -> str:
    correction_text = "\n".join(f"- {item}" for item in (corrections or [])) or "- No editable defaults require correction."
    return f"""Milestone: create_ecs_express_service

User approval is granted for this exact Cloud CUA deployment contract. Use the loaded cloud-cua/aws-ecs-express skill and only the values below. Do not substitute defaults that conflict with the contract. Stop before any new OAuth, secret entry, broad IAM, billing change, destructive action, or cost above $5.

Cloud CUA contract:
{json.dumps(contract.to_dict(), indent=2)}

Supervisor corrections from the inspection milestone:
{correction_text}

Create the ECS Express Mode service, then observe AWS until it reports a stable success, failure, or user-action blocker. Return one JSON object and no Markdown:
{{
  "milestone": "create_ecs_express_service",
  "status": "submitted|completed|blocked|failed",
  "region": "...",
  "service_name": "...",
  "service_arn": "...",
  "task_definition_arn": "...",
  "image_uri": "...",
  "container_port": 0,
  "target_health": "healthy|unhealthy|pending|unknown",
  "public_app_url": null,
  "console_url": "...",
  "created_resources": [],
  "blockers": [],
  "assumptions": []
}}
"""


def extract_json_object(text: str) -> dict[str, Any] | None:
    candidates = [text.strip()]
    candidates.extend(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.I | re.S))
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        candidates.append(text[first : last + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    return None


def _compare_if_present(objections: list[str], label: str, visible: Any, expected: Any) -> None:
    if visible in {None, "", "unknown", "not set"}:
        return
    if str(visible).strip() != str(expected).strip():
        objections.append(f"Visible {label} {visible!r} conflicts with contract value {expected!r}.")


def _correction_if_different(corrections: list[str], label: str, visible: Any, expected: Any) -> None:
    if visible in {None, "", "unknown", "not set"}:
        return
    if str(visible).strip() != str(expected).strip():
        message = f"Set {label} from visible default {visible!r} to contract value {expected!r}."
        if message not in corrections:
            corrections.append(message)
