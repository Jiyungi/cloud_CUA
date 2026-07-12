from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .paths import browser_profile_dir


def find_chrome() -> str | None:
    candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("google-chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def cloud_console_url(cloud: str) -> str:
    if cloud == "gcp":
        return "https://console.cloud.google.com/"
    return "https://console.aws.amazon.com/"


def launch_dedicated_browser(cloud: str, debugging_port: int = 9222) -> dict:
    exe = find_chrome()
    if not exe:
        return {"status": "blocked", "message": "Chrome or Edge was not found in PATH or standard install locations."}
    profile = browser_profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    url = cloud_console_url(cloud)
    args = [
        exe,
        f"--user-data-dir={profile}",
        f"--remote-debugging-port={debugging_port}",
        "--new-window",
        url,
    ]
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"status": "started", "url": url, "profile": str(profile), "debugging_port": debugging_port}

