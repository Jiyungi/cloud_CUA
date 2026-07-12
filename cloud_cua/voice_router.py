from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceRoute:
    transcript: str
    classification: str
    route: str
    action: str | None = None
    mode: str | None = None
    reason: str | None = None


def classify_voice_command(text: str) -> VoiceRoute:
    raw = text.strip()
    lower = raw.lower().strip(" .!?")

    if lower in {"pause", "pause agent", "pause deployment", "stop for now"}:
        return VoiceRoute(raw, "direct_control", "backend", action="pause")
    if lower in {"continue", "resume", "resume agent", "continue deployment"}:
        return VoiceRoute(raw, "direct_control", "backend", action="resume")
    if lower in {"stop", "cancel", "cancel run", "stop deployment"}:
        return VoiceRoute(raw, "direct_control", "backend", action="stop")
    if "switch" in lower and "vibe" in lower:
        return VoiceRoute(raw, "direct_control", "backend", action="set_mode", mode="vibe")
    if "switch" in lower and "teach" in lower:
        return VoiceRoute(raw, "direct_control", "backend", action="set_mode", mode="teach")
    if "switch" in lower and "expert" in lower:
        return VoiceRoute(raw, "direct_control", "backend", action="set_mode", mode="expert")
    if lower in {"run verifier", "verify", "run verification", "check deployment"}:
        return VoiceRoute(raw, "direct_control", "backend", action="run_verifier")
    if lower in {"open logs", "show logs"}:
        return VoiceRoute(raw, "direct_control", "backend", action="open_logs")
    if lower in {"mute", "mute voice", "stop speaking"}:
        return VoiceRoute(raw, "direct_control", "backend", action="mute_voice")

    reasoning_markers = ["why", "what is", "explain", "is this", "should", "cheaper", "cost", "iam", "amplify", "error"]
    if any(marker in lower for marker in reasoning_markers):
        return VoiceRoute(raw, "reasoning_question", "codex", reason="requires explanation or repo/cloud reasoning")

    operation_markers = ["click", "create", "delete", "deploy", "change", "set up", "use "]
    if any(marker in lower for marker in operation_markers):
        return VoiceRoute(raw, "planned_cloud_action", "planner", reason="cloud operation request needs planning and approvals")

    return VoiceRoute(raw, "unknown", "clarify", reason="command not recognized")

