from __future__ import annotations

import json
import re
from pathlib import Path

from .models import RepoContext


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _detect_package_manager(root: Path) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        return "bun"
    if (root / "package-lock.json").exists():
        return "npm"
    if (root / "package.json").exists():
        return "npm"
    return "unknown"


def _script_cmd(pm: str, script: str) -> str:
    if pm == "pnpm":
        return f"pnpm {script}"
    if pm == "yarn":
        return f"yarn {script}"
    if pm == "bun":
        return f"bun run {script}"
    return f"npm run {script}"


def _env_vars(root: Path) -> list[str]:
    names: set[str] = set()
    for filename in [".env.example", ".env.sample", ".env.template"]:
        path = root / filename
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key = line.split("=", 1)[0].strip()
                if key and re.match(r"^[A-Z0-9_]+$", key):
                    names.add(key)
    return sorted(names)


def analyze_repo(repo_path: str | Path) -> RepoContext:
    root = Path(repo_path).resolve()
    pkg = _read_json(root / "package.json")
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    scripts = pkg.get("scripts", {})
    pm = _detect_package_manager(root)
    dockerfile = (root / "Dockerfile").exists()
    risks: list[str] = []

    framework = "unknown"
    category = "unknown"
    output = None

    if "next" in deps or (root / "next.config.js").exists() or (root / "next.config.mjs").exists():
        framework = "nextjs"
        category = "nextjs"
        output = ".next"
    elif "vite" in deps or (root / "vite.config.ts").exists() or (root / "vite.config.js").exists():
        framework = "vite"
        category = "frontend_static"
        output = "dist"
    elif "react" in deps and pkg:
        framework = "react"
        category = "frontend_static"
        output = "build"
    elif (root / "index.html").exists():
        framework = "static"
        category = "frontend_static"
        output = "."
    elif dockerfile:
        framework = "container"
        category = "containerized_web"
    elif any(name in deps for name in ["express", "fastify", "@nestjs/core", "hono"]):
        framework = "node_api"
        category = "node_api"
    elif (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
        text = ""
        for candidate in ["requirements.txt", "pyproject.toml"]:
            path = root / candidate
            if path.exists():
                text += path.read_text(encoding="utf-8", errors="ignore").lower()
        if any(name in text for name in ["fastapi", "flask", "django", "uvicorn", "gunicorn"]):
            framework = "python_api"
            category = "python_api"
    if any((root / name).exists() for name in ["serverless.yml", "serverless.yaml", "template.yaml", "samconfig.toml"]):
        framework = "serverless"
        category = "serverless"
    if any((root / name).exists() for name in ["main.tf", "cdk.json"]) or (root / "infra").exists():
        framework = "iac"
        category = "iac"

    build_command = _script_cmd(pm, "build") if "build" in scripts else None
    start_command = _script_cmd(pm, "start") if "start" in scripts else None

    if category == "frontend_static" and not build_command and framework != "static":
        risks.append("frontend repo has no build script")
    if not _env_vars(root):
        risks.append("no env example found")
    if category == "unknown":
        risks.append("repo category is unknown")

    if category in {"frontend_static", "nextjs"}:
        recommendation = "aws_amplify"
    elif category == "containerized_web":
        recommendation = "aws_ecs_express"
    elif category in {"node_api", "python_api"}:
        recommendation = "aws_lambda"
    elif category == "serverless":
        recommendation = "aws_lambda"
    elif category == "iac":
        recommendation = "aws_iac_review"
    else:
        recommendation = "blocked_unknown_repo"

    return RepoContext(
        framework=framework,
        category=category,
        package_manager=pm,
        build_command=build_command,
        output_directory=output,
        start_command=start_command,
        dockerfile=dockerfile,
        env_vars=_env_vars(root),
        risks=risks,
        recommendation=recommendation,
    )
