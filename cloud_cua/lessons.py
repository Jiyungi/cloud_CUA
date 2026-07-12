from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .run_store import now_iso, sanitize_obj, sanitize_text


@dataclass(frozen=True)
class LessonCandidate:
    run_id: str
    affected_skill: str
    failure: str
    evidence: dict[str, Any]
    proposed_rule: str
    required_test: str
    status: str = "pending_review"
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_lesson_candidate(
    run_dir: Path,
    *,
    run_id: str,
    affected_skill: str,
    failure: str,
    evidence: dict[str, Any],
    proposed_rule: str,
    required_test: str,
) -> Path:
    lesson = LessonCandidate(
        run_id=run_id,
        affected_skill=affected_skill,
        failure=sanitize_text(failure),
        evidence=sanitize_obj(evidence),
        proposed_rule=sanitize_text(proposed_rule),
        required_test=sanitize_text(required_test),
    )
    path = run_dir / "lesson_candidate.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(lesson.to_dict(), indent=2), encoding="utf-8")
    return path


def load_lesson_candidate(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "lesson_candidate.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
