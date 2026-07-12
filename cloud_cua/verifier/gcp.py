from __future__ import annotations

from .base import run_command


def verify_gcp_identity():
    return run_command("gcp_auth_list", ["gcloud", "auth", "list"], timeout=30)


def verify_gcp_project():
    return run_command("gcp_project", ["gcloud", "config", "get-value", "project"], timeout=30)


def verify_gcp_cloud_run_services(region: str = "us-central1"):
    return run_command(
        "gcp_cloud_run_services",
        ["gcloud", "run", "services", "list", "--region", region, "--format=json"],
        timeout=45,
    )
