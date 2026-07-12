from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


SKILLS_DIR = Path(__file__).with_name("skills")


@dataclass(frozen=True)
class DeploymentSkill:
    name: str
    description: str
    target: str
    autonomy_level: int
    body: str
    source: str | None = None
    url_pattern: str | None = None
    required_facts: list[str] = field(default_factory=list)
    unknowns_that_block: list[str] = field(default_factory=list)
    h_cua_allowed_actions: list[str] = field(default_factory=list)
    h_cua_stop_conditions: list[str] = field(default_factory=list)
    required_verifiers: list[str] = field(default_factory=list)
    success_conditions: list[str] = field(default_factory=list)
    cleanup_strategy: str = ""

    def to_dict(self, include_body: bool = True) -> dict[str, Any]:
        data = asdict(self)
        if not include_body:
            data.pop("body", None)
        data["content_hash"] = self.content_hash
        return data

    @property
    def content_hash(self) -> str:
        payload = {
            "name": self.name,
            "description": self.description,
            "body": self.body,
            "source": self.source,
            "url_pattern": self.url_pattern,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def load_skills(skills_dir: str | Path | None = None) -> list[DeploymentSkill]:
    root = Path(skills_dir) if skills_dir else SKILLS_DIR
    skills = [_load_skill(path) for path in sorted(root.glob("*.yaml"))]
    names = [skill.name for skill in skills]
    targets = [skill.target for skill in skills]
    if len(names) != len(set(names)):
        raise ValueError("Deployment skill names must be unique.")
    if len(targets) != len(set(targets)):
        raise ValueError("Deployment skill targets must be unique.")
    return skills


def get_skill(name: str, skills_dir: str | Path | None = None) -> DeploymentSkill:
    for skill in load_skills(skills_dir):
        if skill.name == name:
            return skill
    raise KeyError(f"Unknown deployment skill: {name}")


def skill_for_target(target: str, skills_dir: str | Path | None = None) -> DeploymentSkill | None:
    return next((skill for skill in load_skills(skills_dir) if skill.target == target), None)


def _load_skill(path: Path) -> DeploymentSkill:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Skill file must contain a YAML object: {path}")
    required = ["name", "description", "target", "autonomy_level", "body"]
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError(f"Skill {path.name} is missing required fields: {', '.join(missing)}")
    allowed = set(DeploymentSkill.__dataclass_fields__)
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ValueError(f"Skill {path.name} has unknown fields: {', '.join(unknown)}")
    skill = DeploymentSkill(**raw)
    _validate_skill(skill, path)
    return skill


def _validate_skill(skill: DeploymentSkill, path: Path) -> None:
    segments = skill.name.split("/")
    if len(segments) > 2 or any(not segment or not _is_kebab_case(segment) for segment in segments):
        raise ValueError(f"Skill {path.name} name must be kebab-case with at most one namespace.")
    if not 1 <= skill.autonomy_level <= 5:
        raise ValueError(f"Skill {path.name} autonomy_level must be between 1 and 5.")
    for field_name in (
        "required_facts",
        "unknowns_that_block",
        "h_cua_allowed_actions",
        "h_cua_stop_conditions",
        "required_verifiers",
        "success_conditions",
    ):
        values = getattr(skill, field_name)
        if not isinstance(values, list) or any(not isinstance(item, str) or not item.strip() for item in values):
            raise ValueError(f"Skill {path.name} field {field_name} must be a list of non-empty strings.")


def _is_kebab_case(value: str) -> bool:
    return value.replace("-", "").isalnum() and value == value.lower() and "_" not in value
