from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse


URL_RE = re.compile(r"https?://[^\s<>)\"']+")
RESOURCE_RE = re.compile(r"\bcloud-cua-[a-zA-Z0-9_.-]+\b")


@dataclass
class ResourceRecord:
    run_id: str
    cloud: str
    target: str
    urls: list[str] = field(default_factory=list)
    app_urls: list[str] = field(default_factory=list)
    resource_names: list[str] = field(default_factory=list)
    notes: str = ""


def extract_resource_record(run_id: str, cloud: str, target: str, text: str) -> ResourceRecord:
    urls = set(match.rstrip(".,;") for match in URL_RE.findall(text or ""))
    try:
        structured = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        structured = None
    if isinstance(structured, dict):
        for key in ("public_app_url", "application_url", "live_url"):
            value = structured.get(key)
            if isinstance(value, str) and value.strip():
                normalized = value.strip()
                if not normalized.startswith(("http://", "https://")):
                    normalized = "https://" + normalized
                urls.add(normalized.rstrip(".,;"))
    urls = sorted(urls)
    app_urls = sorted(url for url in urls if is_public_app_url(url))
    resources = sorted(set(match.rstrip(".,;") for match in RESOURCE_RE.findall(text or "")))
    return ResourceRecord(run_id=run_id, cloud=cloud, target=target, urls=urls, app_urls=app_urls, resource_names=resources, notes=(text or "")[:4000])


def save_resource_record(path: Path, record: ResourceRecord) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_resource_records(path)
    existing.append(record)
    path.write_text(json.dumps([asdict(item) for item in existing], indent=2), encoding="utf-8")
    return path


def load_resource_records(path: Path) -> list[ResourceRecord]:
    if not path.exists():
        return []
    records: list[ResourceRecord] = []
    for item in json.loads(path.read_text(encoding="utf-8")):
        item.setdefault("app_urls", [url for url in item.get("urls", []) if is_public_app_url(url)])
        records.append(ResourceRecord(**item))
    return records


def is_public_app_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = (parsed.netloc or "").lower()
    if not parsed.scheme.startswith("http") or not host:
        return False
    control_plane_hosts = [
        "console.aws.amazon.com",
        "signin.aws.amazon.com",
        "us-east-1.console.aws.amazon.com",
        "console.cloud.google.com",
    ]
    if any(host == item or host.endswith("." + item) for item in control_plane_hosts):
        return False
    return True
