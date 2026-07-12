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
    can_apply = observation.get("can_apply_contract") is True
    if not can_apply:
        objections.append("H reported that the contract cannot be applied to the visible form.")
    blockers = observation.get("blockers") or []
    if blockers and not can_apply:
        objections.append("H reported blockers: " + "; ".join(str(item) for item in blockers))
    elif blockers:
        corrections.extend(f"Inspection note: {item}" for item in blockers)

    visible = observation.get("visible_defaults") if isinstance(observation.get("visible_defaults"), dict) else {}
    _compare_if_present(objections, "region", observation.get("region"), contract.cloud_region)
    _correction_if_different(corrections, "image URI", visible.get("image_uri"), contract.container_image_uri)
    _correction_if_different(corrections, "container port", visible.get("container_port"), contract.selected_container_port)
    _correction_if_different(corrections, "health check path", visible.get("health_check_path"), contract.health_check_path)
    return MilestoneReview("blocked" if objections else "clear", observation=observation, objections=objections, corrections=corrections)


def build_ecs_prepare_form_task(contract: DeploymentContract, corrections: list[str] | None = None) -> str:
    correction_text = "\n".join(f"- {item}" for item in (corrections or [])) or "- No editable defaults require correction."
    return f"""Milestone: prepare_ecs_express_form

User approval is granted to prepare this ECS Express form, but not to submit it in this milestone. Use the loaded cloud-cua/aws-ecs-express skill.

Use write actions with enter=false for every text field. Never press Enter. Never click Create or submit the form. Fill only these contract values:
{json.dumps(contract.to_dict(), indent=2)}

Apply these supervisor corrections:
{correction_text}

Set the exact image URI, container port, health check path, and all required tags. Leave the optional task role empty and leave default networking unchanged because the contract does not specify either. Do not create IAM roles.

Return the selected values through the structured answer schema. Set ready_to_submit=true only when every reported value exactly matches the contract and the form is still unsubmitted.
"""


def review_ecs_prepared_form(result: HTaskResult, contract: DeploymentContract) -> MilestoneReview:
    if result.status != "completed":
        return MilestoneReview("blocked", objections=[f"H form preparation ended with status {result.status}: {result.summary}"])
    observation = extract_json_object(result.summary)
    if observation is None:
        return MilestoneReview("blocked", objections=["H form preparation did not return the required structured answer."])
    objections: list[str] = []
    if observation.get("milestone") != "prepare_ecs_express_form":
        objections.append("H returned the wrong form-preparation milestone.")
    if observation.get("ready_to_submit") is not True:
        objections.append("H did not confirm that the form is ready to submit.")
    if observation.get("blockers"):
        objections.append("H reported form blockers: " + "; ".join(str(item) for item in observation["blockers"]))
    _compare_required(objections, "image URI", observation.get("image_uri"), contract.container_image_uri)
    _compare_required(objections, "container port", observation.get("container_port"), contract.selected_container_port)
    _compare_required(objections, "health check path", observation.get("health_check_path"), contract.health_check_path)
    actual_tags = observation.get("tags") if isinstance(observation.get("tags"), dict) else {}
    for key, value in contract.required_tags.items():
        if str(actual_tags.get(key, "")) != str(value):
            objections.append(f"Prepared form tag {key!r} does not match contract value {value!r}.")
    return MilestoneReview("blocked" if objections else "clear", observation=observation, objections=objections)


def build_ecs_submit_task(contract: DeploymentContract) -> str:
    return f"""Milestone: create_ecs_express_service

The ECS Express form was prepared in a previous milestone and the supervisor verified its reported values. Do not type into fields and do not press Enter.

Before submitting, visually confirm the image URI, container port, health path, and required tags still match this contract:
{json.dumps(contract.to_dict(), indent=2)}

If any value is missing or different, do not submit and return status=blocked. Otherwise click the visible Create button exactly once. Observe the resulting service until AWS shows a stable success, failure, or user-action blocker, then return the required structured answer.
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


def _compare_required(objections: list[str], label: str, actual: Any, expected: Any) -> None:
    if str(actual).strip() != str(expected).strip():
        objections.append(f"Prepared {label} {actual!r} does not match contract value {expected!r}.")
