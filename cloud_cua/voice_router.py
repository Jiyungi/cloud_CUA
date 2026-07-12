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
    spoken_target: str | None = None


def classify_voice_command(text: str, *, playback_active: bool = False) -> VoiceRoute:
    raw = text.strip()
    lower = raw.lower().strip(" .!?")

    if lower in {"pause", "pause agent", "pause deployment", "stop for now"}:
        return VoiceRoute(raw, "direct_control", "backend", action="pause")
    if lower in {"continue", "resume", "resume agent", "continue deployment"}:
        return VoiceRoute(raw, "direct_control", "backend", action="resume")
    if lower == "stop" and playback_active:
        return VoiceRoute(raw, "direct_control", "backend", action="stop_speaking")
    if lower in {"cancel", "cancel run", "stop deployment"}:
        return VoiceRoute(raw, "direct_control", "backend", action="stop")
    if "switch" in lower and "vibe" in lower:
        return VoiceRoute(raw, "direct_control", "backend", action="set_mode", mode="vibe")
    if "switch" in lower and "teach" in lower:
        return VoiceRoute(raw, "direct_control", "backend", action="set_mode", mode="teach")
    if "switch" in lower and "expert" in lower:
        return VoiceRoute(raw, "direct_control", "backend", action="set_mode", mode="expert")
    if lower in {"run verifier", "verify", "run verification", "check deployment"}:
        return VoiceRoute(raw, "direct_control", "backend", action="run_verifier")
    if lower in {"status", "deployment status", "what is happening", "what's happening"}:
        return VoiceRoute(raw, "direct_control", "backend", action="status")
    if lower in {"cleanup preview", "show cleanup", "preview cleanup"}:
        return VoiceRoute(raw, "direct_control", "backend", action="cleanup_preview")
    if lower in {"open logs", "show logs"}:
        return VoiceRoute(raw, "direct_control", "backend", action="open_logs")
    if lower in {"mute", "mute voice"}:
        return VoiceRoute(raw, "direct_control", "backend", action="mute_voice")
    if lower in {"stop speaking", "be quiet"}:
        return VoiceRoute(raw, "direct_control", "backend", action="stop_speaking")
    if lower in {"yes", "approve", "go ahead"}:
        return VoiceRoute(raw, "approval", "backend", action="approve")
    if lower.startswith("approve "):
        return VoiceRoute(raw, "approval", "backend", action="approve", spoken_target=raw[len("approve ") :].strip())
    if lower in {"no", "reject", "deny"}:
        return VoiceRoute(raw, "approval", "backend", action="reject")
    if lower.startswith("reject ") or lower.startswith("deny "):
        target = raw.split(" ", 1)[1].strip()
        return VoiceRoute(raw, "approval", "backend", action="reject", spoken_target=target)

    reasoning_markers = ["why", "what is", "explain", "is this", "should", "cheaper", "cost", "iam", "amplify", "error"]
    if any(marker in lower for marker in reasoning_markers):
        return VoiceRoute(raw, "reasoning_question", "codex", reason="requires explanation or repo/cloud reasoning")

    operation_markers = ["click", "create", "delete", "deploy", "publish", "change", "set up", "use "]
    if any(marker in lower for marker in operation_markers):
        return VoiceRoute(raw, "planned_cloud_action", "planner", reason="cloud operation request needs planning and approvals")

    return VoiceRoute(raw, "unknown", "clarify", reason="command not recognized")
