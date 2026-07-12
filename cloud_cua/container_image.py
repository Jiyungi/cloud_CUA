from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .aws_cli import aws_command
from .deployments.aws_general import DEFAULT_AWS_REGION, RESOURCE_PREFIX


@dataclass
class ContainerImagePrepResult:
    status: str
    summary: str
    image_uri: str = ""
    repository_name: str = ""
    registry: str = ""
    commands: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def prepare_ecr_image(repo_path: str | Path, repo_name: str, run_id: str, region: str = DEFAULT_AWS_REGION) -> ContainerImagePrepResult:
    return prepare_ecr_image_with_progress(repo_path, repo_name, run_id, region)


def prepare_ecr_image_with_progress(
    repo_path: str | Path,
    repo_name: str,
    run_id: str,
    region: str = DEFAULT_AWS_REGION,
    progress: Callable[[str, str, dict], None] | None = None,
) -> ContainerImagePrepResult:
    root = Path(repo_path).resolve()
    if not (root / "Dockerfile").exists():
        _emit(progress, "container_image_skipped", "No Dockerfile found; skipping ECR image preparation.")
        return ContainerImagePrepResult("skipped", "No Dockerfile found; ECR image preparation was skipped.")

    slug = _slug(repo_name)
    suffix = _slug(run_id)[-12:]
    repository = f"{RESOURCE_PREFIX}-{slug}-{suffix}"[:255].strip("-")
    image_tag = f"run-{suffix}"
    commands: list[str] = []

    _emit(progress, "container_image_account", "Checking AWS account for ECR image preparation.")
    account_command = aws_command(["sts", "get-caller-identity", "--query", "Account", "--output", "text"])
    account = _run(account_command, timeout=30)
    commands.append(" ".join(account_command))
    if account.returncode != 0:
        return _failed("Could not determine AWS account for ECR image preparation.", account, commands)
    account_id = account.stdout.strip()
    if not re.fullmatch(r"\d{12}", account_id):
        return ContainerImagePrepResult("failed", f"Unexpected AWS account id from CLI: {account_id!r}", commands=commands)

    registry = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    image_uri = f"{registry}/{repository}:{image_tag}"

    _emit(progress, "container_image_ecr_repository", "Creating or reusing Cloud CUA ECR repository.", {"repository": repository, "region": region})
    create_repo = _run(
        aws_command(
            [
                "ecr",
                "create-repository",
                "--repository-name",
                repository,
                "--image-scanning-configuration",
                "scanOnPush=true",
                "--tags",
                "Key=cloud-cua,Value=true",
                f"Key=cloud-cua-repo,Value={repo_name}",
                f"Key=cloud-cua-run,Value={run_id}",
                "--region",
                region,
            ]
        ),
        timeout=60,
    )
    commands.append(" ".join(aws_command(["ecr", "create-repository", "--repository-name", repository, "--tags", "...", "--region", region])))
    if create_repo.returncode != 0 and "RepositoryAlreadyExistsException" not in create_repo.stderr:
        return _failed("Could not create or reuse the Cloud CUA ECR repository.", create_repo, commands, image_uri, repository, registry)

    _emit(progress, "container_image_ecr_login_token", "Requesting ECR login token.", {"registry": registry})
    password_command = aws_command(["ecr", "get-login-password", "--region", region])
    password = _run(password_command, timeout=60)
    commands.append(" ".join(password_command))
    if password.returncode != 0:
        return _failed("Could not get an ECR login token.", password, commands, image_uri, repository, registry)

    _emit(progress, "container_image_docker_login", "Logging Docker into ECR.", {"registry": registry})
    login = subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        input=password.stdout,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
    )
    commands.append(f"docker login --username AWS --password-stdin {registry}")
    if login.returncode != 0:
        return _failed("Docker could not log in to ECR. Check that Docker Desktop is running.", login, commands, image_uri, repository, registry)

    local_tag = f"{RESOURCE_PREFIX}-{slug}:{image_tag}"
    _emit(progress, "container_image_building", "Building local Docker image for ECS Express Mode.", {"local_tag": local_tag})
    build = _run(["docker", "build", "-t", local_tag, str(root)], timeout=900)
    commands.append(f"docker build -t {local_tag} {root}")
    if build.returncode != 0:
        return _failed("Docker build failed for the local repo.", build, commands, image_uri, repository, registry)

    _emit(progress, "container_image_tagging", "Tagging Docker image for ECR.", {"image_uri": image_uri})
    tag = _run(["docker", "tag", local_tag, image_uri], timeout=60)
    commands.append(f"docker tag {local_tag} {image_uri}")
    if tag.returncode != 0:
        return _failed("Docker could not tag the image for ECR.", tag, commands, image_uri, repository, registry)

    _emit(progress, "container_image_pushing", "Pushing Docker image to ECR. This can take a few minutes.", {"image_uri": image_uri})
    push = _run(["docker", "push", image_uri], timeout=900)
    commands.append(f"docker push {image_uri}")
    if push.returncode != 0:
        return _failed("Docker push to ECR failed.", push, commands, image_uri, repository, registry)

    return ContainerImagePrepResult(
        "passed",
        f"Built and pushed container image for ECS Express Mode: {image_uri}",
        image_uri=image_uri,
        repository_name=repository,
        registry=registry,
        commands=commands,
    )


def _run(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout)
    except Exception as exc:
        return subprocess.CompletedProcess(command, 1, "", f"{type(exc).__name__}: {exc}")


def _failed(
    summary: str,
    proc: subprocess.CompletedProcess[str],
    commands: list[str],
    image_uri: str = "",
    repository_name: str = "",
    registry: str = "",
) -> ContainerImagePrepResult:
    detail = (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
    return ContainerImagePrepResult(
        "failed",
        f"{summary} {detail}"[:1000],
        image_uri=image_uri,
        repository_name=repository_name,
        registry=registry,
        commands=commands,
    )


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9-]+", "-", value.lower())
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "app"


def _emit(progress: Callable[[str, str, dict], None] | None, step: str, message: str, evidence: dict | None = None) -> None:
    if progress:
        progress(step, message, evidence or {})
