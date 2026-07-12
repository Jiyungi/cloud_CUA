from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from uuid import uuid4

from .run_store import now_iso, sanitize_obj, sanitize_text

VOICE_STATES = {
    "idle",
    "listening",
    "transcribing",
    "routing",
    "answering",
    "executing",
    "speaking",
    "completed",
    "failed",
    "cancelled",
}


@dataclass
class VoiceTurn:
    turn_id: str
    run_id: str
    state: str
    transcript: str = ""
    partial_transcript: str = ""
    classification: str = ""
    action: str = ""
    response: str = ""
    error: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict = field(default_factory=dict)


class VoiceTurnStore:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.path = run_dir / "voice-turns.json"

    def create(self, run_id: str, state: str = "listening") -> VoiceTurn:
        now = now_iso()
        turn = VoiceTurn(uuid4().hex, run_id, state, created_at=now, updated_at=now)
        turns = self.list()
        turns.append(turn)
        self._save(turns[-20:])
        return turn

    def update(self, turn_id: str, **changes) -> VoiceTurn:
        turns = self.list()
        for turn in turns:
            if turn.turn_id != turn_id:
                continue
            state = changes.get("state", turn.state)
            if state not in VOICE_STATES:
                raise ValueError(f"unsupported voice state: {state}")
            for key, value in changes.items():
                if hasattr(turn, key):
                    setattr(turn, key, value)
            turn.transcript = sanitize_text(turn.transcript)
            turn.partial_transcript = sanitize_text(turn.partial_transcript)
            turn.response = sanitize_text(turn.response)
            turn.error = sanitize_text(turn.error)
            turn.metadata = sanitize_obj(turn.metadata)
            turn.updated_at = now_iso()
            self._save(turns)
            return turn
        raise KeyError(f"voice turn not found: {turn_id}")

    def list(self) -> list[VoiceTurn]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [VoiceTurn(**item) for item in data]
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return []

    def current(self) -> VoiceTurn | None:
        turns = self.list()
        return turns[-1] if turns else None

    def recent_conversation(self, limit: int = 6) -> list[dict[str, str]]:
        return [
            {"question": turn.transcript, "answer": turn.response}
            for turn in self.list()[-limit:]
            if turn.transcript and turn.response
        ]

    def _save(self, turns: list[VoiceTurn]) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps([asdict(item) for item in turns], indent=2), encoding="utf-8")
        temporary.replace(self.path)
