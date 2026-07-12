from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys

from .credentials import inspect_credentials, save_credentials
from .mcp_server import main as mcp_main
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

