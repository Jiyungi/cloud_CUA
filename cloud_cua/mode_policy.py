from __future__ import annotations

from .models import Mode


POLICIES: dict[Mode, str] = {
    "vibe": "Use safe defaults. Ask only for login, cost, secrets, broad permissions, public exposure, or destructive changes. Keep explanations short.",
    "teach": "Explain only major decisions in plain language. Default to one sentence of at most 35 words. Use at most three short bullets for a decision or blocker, and expand only when asked.",
    "expert": "Ask concrete tradeoff questions. Show cost, security, reliability, and operational implications. Avoid beginner explanations unless asked.",
}


def normalize_mode(mode: str) -> Mode:
    value = mode.lower().strip()
    if value not in POLICIES:
        raise ValueError(f"unsupported mode: {mode}")
    return value  # type: ignore[return-value]


def policy_for(mode: Mode) -> str:
    return POLICIES[mode]


def response_word_limit(mode: Mode, *, expanded: bool = False) -> int:
    if expanded:
        return 180
    return 35 if mode == "teach" else 60
