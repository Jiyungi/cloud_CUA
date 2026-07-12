from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from .models import RepoContext


@dataclass(frozen=True)
class ContainerPortFact:
    port: int
    source: str
    confidence: str


@dataclass(frozen=True)
class DeploymentContract:
    target: str
    schema_version: int = 1
    run_id: str = ""
    skill_name: str = ""
    skill_hash: str = ""
    autonomy_level: int = 1
    cloud_region: str = ""
    resource_name: str = ""
    branch_name: str = ""
    build_command: str = ""
    output_directory: str = ""
    artifact_reference: str = ""
    container_image_uri: str = ""
    ecr_repository: str = ""
    expected_account_id: str = ""
    runtime_secret_references: dict[str, str] = field(default_factory=dict)
    cost_limit_usd: float = 0.0
    estimated_hourly_usd: float = 0.0
    cost_deadline_at: str = ""
    required_tags: dict[str, str] = field(default_factory=dict)
    container_ports: list[ContainerPortFact] = field(default_factory=list)
    selected_container_port: int | None = None
    health_check_path: str = "/"
    required_public_app_url: bool = True
    missing_facts: list[str] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)
    completion_checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["container_ports"] = [asdict(item) for item in self.container_ports]
        return data

    def h_instructions(self) -> str:
        lines = [
            "Deployment contract from Codex/local repo analysis:",
            f"- target: {self.target}",
            f"- run_id: {self.run_id or 'not assigned'}",
            f"- cloud_region: {self.cloud_region or 'not assigned'}",
            f"- resource_name: {self.resource_name or 'not assigned'}",
            f"- health_check_path: {self.health_check_path}",
            f"- required_public_app_url: {self.required_public_app_url}",
        ]
        if self.branch_name:
            lines.append(f"- branch_name: {self.branch_name}")
        if self.build_command:
            lines.append(f"- build_command: {self.build_command}")
        if self.output_directory:
            lines.append(f"- output_directory: {self.output_directory}")
        if self.artifact_reference:
            lines.append(f"- artifact_reference: {self.artifact_reference}")
        if self.selected_container_port is not None:
            lines.append(f"- selected_container_port: {self.selected_container_port}")
            lines.append("- use this exact container/listener/target-group port unless AWS proves it is impossible")
        if self.container_image_uri:
            lines.append(f"- container_image_uri: {self.container_image_uri}")
        if self.required_tags:
            lines.append("- required_tags:")
            lines.extend(f"  - {key}={value}" for key, value in sorted(self.required_tags.items()))
        if self.runtime_secret_references:
            lines.append("- runtime_secret_references:")
            lines.extend(f"  - {key}={value}" for key, value in sorted(self.runtime_secret_references.items()))
            lines.append("- use only these cloud secret references; never ask for or expose their plaintext values")
        if self.cost_limit_usd:
            lines.append(f"- cost_limit_usd: {self.cost_limit_usd:.2f}")
            lines.append(f"- estimated_fixed_hourly_usd: {self.estimated_hourly_usd:.6f}")
            if self.cost_deadline_at:
                lines.append(f"- estimated_cost_deadline_at: {self.cost_deadline_at}")
        if self.container_ports:
            lines.append("- detected_container_port_candidates:")
            for fact in self.container_ports:
                lines.append(f"  - {fact.port} from {fact.source} ({fact.confidence})")
        if self.missing_facts:
            lines.append("- missing_facts:")
            lines.extend(f"  - {item}" for item in self.missing_facts)
            lines.append("- stop instead of guessing if any missing fact is required by the AWS form")
        if self.stop_conditions:
            lines.append("- stop_conditions:")
            lines.extend(f"  - {item}" for item in self.stop_conditions)
        if self.completion_checks:
            lines.append("- completion_checks:")
            lines.extend(f"  - {item}" for item in self.completion_checks)
        return "\n".join(lines)

    def with_runtime_inputs(
        self,
        *,
        run_id: str,
        skill_name: str,
        skill_hash: str,
        autonomy_level: int,
        cloud_region: str,
        container_image_uri: str = "",
        ecr_repository: str = "",
        repo_name: str = "",
        resource_name: str = "",
        branch_name: str = "",
        build_command: str = "",
        output_directory: str = "",
        artifact_reference: str = "",
        expected_account_id: str = "",
        runtime_secret_references: dict[str, str] | None = None,
        cost_limit_usd: float = 0.0,
        estimated_hourly_usd: float = 0.0,
        cost_deadline_at: str = "",
    ) -> "DeploymentContract":
        return replace(
            self,
            run_id=run_id,
            skill_name=skill_name,
            skill_hash=skill_hash,
            autonomy_level=autonomy_level,
            cloud_region=cloud_region,
            resource_name=resource_name,
            branch_name=branch_name,
            build_command=build_command,
            output_directory=output_directory,
            artifact_reference=artifact_reference,
            container_image_uri=container_image_uri,
            ecr_repository=ecr_repository,
            expected_account_id=expected_account_id,
            runtime_secret_references=runtime_secret_references or {},
            cost_limit_usd=cost_limit_usd,
            estimated_hourly_usd=estimated_hourly_usd,
            cost_deadline_at=cost_deadline_at,
            required_tags={
                "cloud-cua": "true",
                "cloud-cua-repo": repo_name,
                "cloud-cua-run": run_id,
            },
        )


def save_contract(path: Path, contract: DeploymentContract) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract.to_dict(), indent=2), encoding="utf-8")
    return path


def load_contract(path: Path) -> DeploymentContract:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["container_ports"] = [ContainerPortFact(**item) for item in data.get("container_ports", [])]
    return DeploymentContract(**data)


def build_deployment_contract(repo_path: str | Path, ctx: RepoContext, target: str) -> DeploymentContract:
    root = Path(repo_path).resolve()
    ports = _detect_container_ports(root)
    selected_port: int | None = None
    missing: list[str] = []

    unique_ports = sorted({fact.port for fact in ports})
    if target in {"aws_ecs_express", "aws_ecs_fargate", "gcp_cloud_run"}:
        if len(unique_ports) == 1:
            selected_port = unique_ports[0]
        elif len(unique_ports) > 1:
            missing.append(f"Multiple possible container ports detected: {', '.join(map(str, unique_ports))}. Ask the user which one is public HTTP.")
        elif ctx.dockerfile:
            missing.append("No container port was detected from Dockerfile, Compose, package scripts, or PORT env. Ask before creating a public service.")

    return DeploymentContract(
        target=target,
        container_ports=ports,
        selected_container_port=selected_port,
        missing_facts=missing,
        stop_conditions=[
            "The cloud console cannot accept the selected_container_port or another required contract value.",
            "The deployment shows AccessDenied, missing IAM capability, failed target health, or no running tasks.",
            "Only an AWS Console URL is available; no public application URL is visible.",
            "The public application URL returns a non-2xx/3xx response.",
        ],
        completion_checks=[
            "ECS service desired tasks are running.",
            "Load balancer target health is healthy.",
            "The public application URL, not the AWS Console URL, returns HTTP success.",
            "Required Cloud CUA tags are visible or verified by AWS APIs.",
        ],
    )


def _detect_container_ports(root: Path) -> list[ContainerPortFact]:
    facts: list[ContainerPortFact] = []
    facts.extend(_dockerfile_ports(root / "Dockerfile"))
    facts.extend(_compose_ports(root))
    facts.extend(_package_script_ports(root / "package.json"))
    return _dedupe_ports(facts)


def _dockerfile_ports(path: Path) -> list[ContainerPortFact]:
    if not path.exists():
        return []
    facts: list[ContainerPortFact] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        expose = re.match(r"(?i)^EXPOSE\s+(.+)$", stripped)
        if expose:
            for token in expose.group(1).split():
                port = _port_from_token(token)
                if port:
                    facts.append(ContainerPortFact(port, f"{path.name}:EXPOSE", "high"))
        for match in re.finditer(r"(?i)\bPORT\s*=\s*(\d{2,5})\b", stripped):
            port = _valid_port(match.group(1))
            if port:
                facts.append(ContainerPortFact(port, f"{path.name}:PORT env", "medium"))
        for match in re.finditer(r"(?i)--port(?:=|\s+)(\d{2,5})\b", stripped):
            port = _valid_port(match.group(1))
            if port:
                facts.append(ContainerPortFact(port, f"{path.name}:command", "medium"))
    return facts


def _compose_ports(root: Path) -> list[ContainerPortFact]:
    facts: list[ContainerPortFact] = []
    for name in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]:
        path = root / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"['\"]?(?:\d{2,5}:)?(\d{2,5})(?:/(?:tcp|udp))?['\"]?", text):
            port = _valid_port(match.group(1))
            if port:
                facts.append(ContainerPortFact(port, f"{name}:ports", "medium"))
    return facts


def _package_script_ports(path: Path) -> list[ContainerPortFact]:
    if not path.exists():
        return []
    try:
        pkg = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    scripts = pkg.get("scripts", {})
    facts: list[ContainerPortFact] = []
    for script_name, command in scripts.items():
        for match in re.finditer(r"(?i)--port(?:=|\s+)(\d{2,5})\b", str(command)):
            port = _valid_port(match.group(1))
            if port:
                facts.append(ContainerPortFact(port, f"package.json:{script_name}", "medium"))
        for match in re.finditer(r"(?i)\bPORT\s*=\s*(\d{2,5})\b", str(command)):
            port = _valid_port(match.group(1))
            if port:
                facts.append(ContainerPortFact(port, f"package.json:{script_name}", "medium"))
    return facts


def _port_from_token(token: str) -> int | None:
    return _valid_port(token.split("/", 1)[0])


def _valid_port(value: str) -> int | None:
    try:
        port = int(value)
    except ValueError:
        return None
    if 1 <= port <= 65535:
        return port
    return None


def _dedupe_ports(facts: list[ContainerPortFact]) -> list[ContainerPortFact]:
    seen: set[tuple[int, str]] = set()
    out: list[ContainerPortFact] = []
    for fact in facts:
        key = (fact.port, fact.source)
        if key in seen:
            continue
        seen.add(key)
        out.append(fact)
    return out
