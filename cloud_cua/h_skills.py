from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .credentials import load_secret_values
from .skill_registry import DeploymentSkill, get_skill, load_skills


@dataclass(frozen=True)
class HSkillStatus:
    name: str
    target: str
    status: str
    local_hash: str
    remote_hash: str | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HSkillSyncReport:
    status: str
    dry_run: bool
    skills: list[HSkillStatus] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "dry_run": self.dry_run,
            "skills": [item.to_dict() for item in self.skills],
            "message": self.message,
        }


def get_h_skill_status(
    repo_path: str | Path | None = None,
    names: list[str] | None = None,
    client: Any | None = None,
) -> HSkillSyncReport:
    return _sync_or_status(repo_path, names, dry_run=True, mutate=False, client=client)


def sync_h_skills(
    repo_path: str | Path | None = None,
    names: list[str] | None = None,
    dry_run: bool = False,
    client: Any | None = None,
) -> HSkillSyncReport:
    return _sync_or_status(repo_path, names, dry_run=dry_run, mutate=not dry_run, client=client)


def _sync_or_status(
    repo_path: str | Path | None,
    names: list[str] | None,
    *,
    dry_run: bool,
    mutate: bool,
    client: Any | None,
) -> HSkillSyncReport:
    local_skills = _select_local_skills(names)
    try:
        h_client = client or _make_client(repo_path)
    except RuntimeError as exc:
        return HSkillSyncReport(
            status="blocked",
            dry_run=dry_run,
            skills=[
                HSkillStatus(skill.name, skill.target, "not_configured", skill.content_hash, message=str(exc))
                for skill in local_skills
            ],
            message=str(exc),
        )

    try:
        remote_by_name = _remote_skills(h_client)
    except Exception as exc:
        return HSkillSyncReport(
            status="failed",
            dry_run=dry_run,
            skills=[
                HSkillStatus(skill.name, skill.target, "unknown", skill.content_hash, message=f"H skill listing failed: {exc}")
                for skill in local_skills
            ],
            message=f"H skill listing failed: {type(exc).__name__}: {exc}",
        )

    statuses: list[HSkillStatus] = []
    for skill in local_skills:
        remote = remote_by_name.get(skill.name)
        remote_hash = _remote_hash(remote) if remote else None
        if remote is None:
            action = "would_create" if dry_run else "created"
            if mutate:
                try:
                    _create_skill(h_client, skill)
                except Exception as exc:
                    statuses.append(HSkillStatus(skill.name, skill.target, "failed", skill.content_hash, None, f"Create failed: {type(exc).__name__}: {exc}"))
                    continue
            statuses.append(HSkillStatus(skill.name, skill.target, action, skill.content_hash, None))
            continue
        if remote_hash == skill.content_hash:
            statuses.append(HSkillStatus(skill.name, skill.target, "synced", skill.content_hash, remote_hash))
            continue
        action = "would_update" if dry_run else "updated"
        if mutate:
            try:
                _update_skill(h_client, skill)
            except Exception as exc:
                statuses.append(HSkillStatus(skill.name, skill.target, "failed", skill.content_hash, remote_hash, f"Update failed: {type(exc).__name__}: {exc}"))
                continue
        statuses.append(HSkillStatus(skill.name, skill.target, action, skill.content_hash, remote_hash))

    report_status = "passed" if all(item.status not in {"failed", "unknown", "not_configured"} for item in statuses) else "blocked"
    return HSkillSyncReport(
        status=report_status,
        dry_run=dry_run,
        skills=statuses,
        message=_summary(statuses, dry_run),
    )


def _select_local_skills(names: list[str] | None) -> list[DeploymentSkill]:
    if not names:
        return load_skills()
    return [get_skill(name) for name in names]


def _make_client(repo_path: str | Path | None) -> Any:
    api_key = load_secret_values(repo_path).get("HAI_API_KEY")
    if not api_key:
        raise RuntimeError("HAI_API_KEY is not configured; H-hosted skills cannot be listed or synced.")
    from hai_agents import Client

    return Client(api_key=api_key)


def _remote_skills(client: Any) -> dict[str, Any]:
    page = client.skills.list_skills(search="cloud-cua/", page=1, size=100)
    return {_value(item, "name"): item for item in page.items if _value(item, "name").startswith("cloud-cua/")}


def _remote_hash(remote: Any) -> str:
    comparable = DeploymentSkill(
        name=_value(remote, "name"),
        description=_value(remote, "description"),
        target="remote",
        autonomy_level=1,
        body=_value(remote, "body"),
        source=_value(remote, "source"),
        url_pattern=_value(remote, "url_pattern"),
    )
    return comparable.content_hash


def _create_skill(client: Any, skill: DeploymentSkill) -> None:
    client.skills.create_skill(
        name=skill.name,
        description=skill.description,
        body=skill.body,
        source=skill.source,
        url_pattern=skill.url_pattern,
    )


def _update_skill(client: Any, skill: DeploymentSkill) -> None:
    client.skills.update_skill(
        skill.name,
        name=skill.name,
        description=skill.description,
        body=skill.body,
        source=skill.source,
        url_pattern=skill.url_pattern,
    )


def _value(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _summary(statuses: list[HSkillStatus], dry_run: bool) -> str:
    counts: dict[str, int] = {}
    for item in statuses:
        counts[item.status] = counts.get(item.status, 0) + 1
    detail = ", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "no skills"
    prefix = "H skill dry run" if dry_run else "H skill sync"
    return f"{prefix}: {detail}."
