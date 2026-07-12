from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


URL_RE = re.compile(r"https?://[^\s<>)\"']+")
RESOURCE_RE = re.compile(r"\bcloud-cua-[a-zA-Z0-9_.-]+\b")


@dataclass
class ResourceRecord:
    run_id: str
    cloud: str
    target: str
    urls: list[str] = field(default_factory=list)
    resource_names: list[str] = field(default_factory=list)
    notes: str = ""


def extract_resource_record(run_id: str, cloud: str, target: str, text: str) -> ResourceRecord:
    urls = sorted(set(match.rstrip(".,;") for match in URL_RE.findall(text or "")))
    resources = sorted(set(match.rstrip(".,;") for match in RESOURCE_RE.findall(text or "")))
    return ResourceRecord(run_id=run_id, cloud=cloud, target=target, urls=urls, resource_names=resources, notes=(text or "")[:2000])


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
        records.append(ResourceRecord(**item))
    return records
