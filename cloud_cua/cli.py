from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys

from .aws_cleanup import cleanup_cloud_cua_aws_resources
from .codex_config import install_cloud_cua_mcp
from .credentials import inspect_credentials, save_credentials
from .doctor import run_doctor
from .h_admin import cleanup_h_sessions, get_h_quota
from .h_skills import get_h_skill_status, sync_h_skills
from .mcp_server import main as mcp_main
from .packaging import build_shareable_package
from .paths import default_dashboard_port


def cmd_init(_args: argparse.Namespace) -> int:
    creds = inspect_credentials()
    if creds.hai_api_key_present:
        print(f"HAI_API_KEY already configured from {creds.source}.")
        return 0
    hai = getpass.getpass("Enter HAI_API_KEY: ").strip()
    gradium = getpass.getpass("Enter GRADIUM_API_KEY (optional): ").strip()
    path = save_credentials(hai, gradium or None)
    print(f"Saved credentials to {path}.")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    port = args.port or default_dashboard_port()
    host = args.host
    print(f"Starting Cloud CUA dashboard at http://{host}:{port}")
    return subprocess.call([sys.executable, "-m", "uvicorn", "cloud_cua.server:app", "--host", host, "--port", str(port)])


def cmd_mcp(_args: argparse.Namespace) -> int:
    mcp_main()
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    creds = inspect_credentials(os.getcwd())
    print("Cloud CUA environment check")
    print(f"HAI_API_KEY present: {creds.hai_api_key_present}")
    print(f"GRADIUM_API_KEY present: {creds.gradium_api_key_present}")
    print(f"Credential source: {creds.source}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = run_doctor(os.getcwd(), include_network=not args.offline)
    failed = 0
    print("Cloud CUA doctor")
    for check in checks:
        marker = "OK" if check.status == "passed" else ("SKIP" if check.status == "skipped" else "FAIL")
        print(f"[{marker}] {check.name}: {check.summary}")
        if check.status == "failed":
            failed += 1
    return 1 if failed else 0


def cmd_install_mcp(args: argparse.Namespace) -> int:
    result = install_cloud_cua_mcp(args.config, dry_run=args.dry_run)
    print(result.summary)
    print(f"Config: {result.config_path}")
    print(f"Command: {result.command}")
    print(f"Args: {' '.join(result.args)}")
    if result.backup_path:
        print(f"Backup: {result.backup_path}")
    return 0 if result.status == "passed" else 1


def cmd_h_status(_args: argparse.Namespace) -> int:
    quota = get_h_quota(os.getcwd())
    if quota is None:
        print("HAI_API_KEY is not configured.")
        return 1
    print(f"H sessions: limit={quota.limit} active={quota.active} available={quota.available}")
    return 0


def cmd_h_cleanup(_args: argparse.Namespace) -> int:
    result = cleanup_h_sessions(os.getcwd())
    print(result.summary)
    if result.before:
        print(f"Before: limit={result.before.limit} active={result.before.active} available={result.before.available}")
    if result.after:
        print(f"After: limit={result.after.limit} active={result.after.active} available={result.after.available}")
    return 0 if result.status in {"passed", "skipped"} else 1


def cmd_h_skills(args: argparse.Namespace) -> int:
    if args.h_skills_cmd == "list":
        report = get_h_skill_status(os.getcwd())
    else:
        report = sync_h_skills(os.getcwd(), names=args.name or None, dry_run=args.dry_run)
    print(report.message)
    for item in report.skills:
        suffix = f" - {item.message}" if item.message else ""
        print(f"- {item.name}: {item.status}{suffix}")
    return 0 if report.status == "passed" else 1


def cmd_package(args: argparse.Namespace) -> int:
    result = build_shareable_package(os.getcwd(), args.output)
    print(result.summary)
    print(result.path)
    return 0 if result.status == "passed" else 1


def cmd_aws_cleanup(args: argparse.Namespace) -> int:
    result = cleanup_cloud_cua_aws_resources(run_id=args.run_id, dry_run=not args.yes)
    print(result.summary)
    for action in result.actions:
        prefix = "would run" if result.dry_run else action.status
        print(f"- {prefix}: {action.service} {action.resource} :: {' '.join(action.command)}")
        if action.summary:
            print(f"  {action.summary}")
    if result.dry_run:
        print("Run again with --yes to delete only discovered Cloud CUA resources.")
    return 0 if result.status == "passed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cloud-cua")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    start = sub.add_parser("start")
    start.add_argument("--host", default="127.0.0.1")
    start.add_argument("--port", type=int)
    start.set_defaults(func=cmd_start)
    sub.add_parser("mcp").set_defaults(func=cmd_mcp)
    sub.add_parser("check").set_defaults(func=cmd_check)
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--offline", action="store_true", help="Skip network checks such as H quota.")
    doctor.set_defaults(func=cmd_doctor)
    install_mcp = sub.add_parser("install-mcp")
    install_mcp.add_argument("--config", help="Path to Codex config.toml. Defaults to CODEX_HOME/config.toml or ~/.codex/config.toml.")
    install_mcp.add_argument("--dry-run", action="store_true")
    install_mcp.set_defaults(func=cmd_install_mcp)
    sub.add_parser("h-status").set_defaults(func=cmd_h_status)
    sub.add_parser("h-cleanup").set_defaults(func=cmd_h_cleanup)
    h_skills = sub.add_parser("h-skills", help="List or sync Cloud CUA deployment skills with H.")
    h_skills_sub = h_skills.add_subparsers(dest="h_skills_cmd", required=True)
    h_skills_sub.add_parser("list").set_defaults(func=cmd_h_skills)
    h_skills_sync = h_skills_sub.add_parser("sync")
    h_skills_sync.add_argument("--dry-run", action="store_true")
    h_skills_sync.add_argument("--name", action="append", help="Sync only this H skill name. May be repeated.")
    h_skills_sync.set_defaults(func=cmd_h_skills)
    aws_cleanup = sub.add_parser("aws-cleanup")
    aws_cleanup.add_argument("--run-id", help="Only clean resources tagged with this Cloud CUA run id.")
    aws_cleanup.add_argument("--yes", action="store_true", help="Actually delete discovered Cloud CUA resources. Without this, only prints a dry run.")
    aws_cleanup.set_defaults(func=cmd_aws_cleanup)
    package = sub.add_parser("package")
    package.add_argument("--output")
    package.set_defaults(func=cmd_package)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
