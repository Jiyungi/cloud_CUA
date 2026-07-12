from __future__ import annotations

import os
import shutil
import subprocess


DEFAULT_PROFILE = "cloud-cua-dev"


def aws_command(args: list[str]) -> list[str]:
    profile = selected_aws_profile()
    if profile:
        return ["aws", "--profile", profile, *args]
    return ["aws", *args]


def selected_aws_profile() -> str | None:
    if os.environ.get("AWS_PROFILE") or os.environ.get("AWS_ACCESS_KEY_ID"):
        return None
    if not shutil.which("aws"):
        return None
    try:
        proc = subprocess.run(["aws", "configure", "list-profiles"], text=True, capture_output=True, timeout=10)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    profiles = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    return DEFAULT_PROFILE if DEFAULT_PROFILE in profiles else None
