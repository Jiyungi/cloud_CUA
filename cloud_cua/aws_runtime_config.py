from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .aws_cli import selected_aws_profile
from .run_store import now_iso


PUBLIC_FRONTEND_PREFIXES = ("VITE_", "NEXT_PUBLIC_", "PUBLIC_")


@dataclass(frozen=True)
class RuntimeVariableReference:
    name: str
    reference: str
    source: str = "ssm_secure_string"
    public_build_value: bool = False


@dataclass
class RuntimeConfiguration:
    status: str
    required_names: list[str] = field(default_factory=list)
    missing_names: list[str] = field(default_factory=list)
    public_build_names: list[str] = field(default_factory=list)
    references: list[RuntimeVariableReference] = field(default_factory=list)
    updated_at: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "references": [asdict(item) for item in self.references],
        }

    def reference_map(self) -> dict[str, str]:
        return {item.name: item.reference for item in self.references}


def runtime_config_path(run_dir: Path) -> Path:
    return run_dir / "runtime-config.json"


def load_runtime_configuration(run_dir: Path, required_names: list[str]) -> RuntimeConfiguration:
    path = runtime_config_path(run_dir)
    references: list[RuntimeVariableReference] = []
    updated_at = ""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            references = [RuntimeVariableReference(**item) for item in data.get("references", [])]
            updated_at = str(data.get("updated_at") or "")
        except (OSError, TypeError, json.JSONDecodeError):
            references = []
    configured = {item.name for item in references}
    public_names = sorted(name for name in required_names if name.startswith(PUBLIC_FRONTEND_PREFIXES))
    secret_names = sorted(name for name in required_names if name not in public_names)
    missing = [name for name in secret_names if name not in configured]
    status = "ready" if not missing else "required"
    return RuntimeConfiguration(
        status=status,
        required_names=secret_names,
        missing_names=missing,
        public_build_names=public_names,
        references=references,
        updated_at=updated_at,
        message="Runtime configuration is ready." if status == "ready" else "Runtime secret values or existing SSM references are required.",
    )


def provision_aws_runtime_configuration(
    run_dir: Path,
    run_id: str,
    repo_name: str,
    required_names: list[str],
    values: dict[str, str],
    existing_references: dict[str, str],
    *,
    region: str,
    account_id: str,
    ssm_client: Any | None = None,
) -> RuntimeConfiguration:
    status = load_runtime_configuration(run_dir, required_names)
    allowed = set(status.required_names)
    unknown = (set(values) | set(existing_references)) - allowed
    if unknown:
        raise ValueError("Runtime configuration included unknown variable names: " + ", ".join(sorted(unknown)))
    client = ssm_client or _ssm_client(region)
    references = {item.name: item for item in status.references}
    try:
        for name, value in values.items():
            if not value:
                raise ValueError(f"{name} cannot be empty.")
            parameter_name = f"/cloud-cua/{_safe(run_id)}/{_safe(name)}"
            client.put_parameter(Name=parameter_name, Value=value, Type="SecureString", Tier="Standard", Overwrite=True)
            client.add_tags_to_resource(
                ResourceType="Parameter",
                ResourceId=parameter_name,
                Tags=[
                    {"Key": "cloud-cua", "Value": "true"},
                    {"Key": "cloud-cua-run", "Value": run_id},
                    {"Key": "cloud-cua-repo", "Value": repo_name[:256]},
                ],
            )
            arn = f"arn:aws:ssm:{region}:{account_id}:parameter{parameter_name}"
            references[name] = RuntimeVariableReference(name, arn)
        for name, reference in existing_references.items():
            normalized = _validate_reference(reference, region, account_id)
            references[name] = RuntimeVariableReference(name, normalized, source="existing_ssm_reference")
    finally:
        for name in list(values):
            values[name] = ""
        values.clear()

    record = RuntimeConfiguration(
        status="ready",
        required_names=status.required_names,
        missing_names=[],
        public_build_names=status.public_build_names,
        references=sorted(references.values(), key=lambda item: item.name),
        updated_at=now_iso(),
        message="Runtime values were stored in AWS SSM; only parameter references were retained locally.",
    )
    path = runtime_config_path(run_dir)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
    temporary.replace(path)
    return record


def _ssm_client(region: str):
    import boto3

    profile = selected_aws_profile()
    session = boto3.Session(profile_name=profile, region_name=region) if profile else boto3.Session(region_name=region)
    return session.client("ssm", region_name=region)


def _validate_reference(reference: str, region: str, account_id: str) -> str:
    value = reference.strip()
    if value.startswith(f"arn:aws:ssm:{region}:{account_id}:parameter/"):
        return value
    if value.startswith("/") and re.fullmatch(r"/[A-Za-z0-9_.\-/]+", value):
        return f"arn:aws:ssm:{region}:{account_id}:parameter{value}"
    raise ValueError("Existing SSM references must be a parameter path or an ARN in the verified account and region.")


def _safe(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return cleaned[:96] or "value"
