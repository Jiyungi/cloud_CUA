from __future__ import annotations

from .models import Mode


POLICIES: dict[Mode, str] = {
    "vibe": "Use safe defaults. Ask only for login, cost, secrets, broad permissions, public exposure, or destructive changes. Keep explanations short.",
    "teach": "Explain each major cloud step in simple language. Pause before IAM, region, env vars, domain, SSL, cost, and logs. Answer questions clearly.",
    "expert": "Ask concrete tradeoff questions. Show cost, security, reliability, and operational implications. Avoid beginner explanations unless asked.",
}


def normalize_mode(mode: str) -> Mode:
    value = mode.lower().strip()
    if value not in POLICIES:
        raise ValueError(f"unsupported mode: {mode}")
    return value  # type: ignore[return-value]


def policy_for(mode: Mode) -> str:
    return POLICIES[mode]

