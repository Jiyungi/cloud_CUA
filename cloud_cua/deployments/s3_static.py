from __future__ import annotations

import re
from dataclasses import dataclass, asdict

from ..deployment_contract import DeploymentContract
from ..deployment_milestones import extract_json_object
from ..h_runner import HTaskResult


@dataclass(frozen=True)
class S3Review:
    status: str
    bucket_name: str = ""
    public_url: str = ""
    objections: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def s3_bucket_name(repo_name: str, run_id: str) -> str:
    repo = re.sub(r"[^a-z0-9-]+", "-", repo_name.lower()).strip("-")[:32] or "app"
    suffix = re.sub(r"[^a-z0-9]+", "", run_id.lower())[-12:]
    return f"cloud-cua-{repo}-{suffix}"[:63].rstrip("-")


def build_s3_creation_task(contract: DeploymentContract) -> str:
    return f"""Milestone: create_s3_static_website

Use the loaded cloud-cua/aws-s3-static skill. User approval is granted for this exact new Cloud CUA bucket and public static website. Do not modify an existing bucket.

Create bucket {contract.resource_name} in {contract.cloud_region}. Configure static website hosting with index.html and error.html. Configure only the minimum public-read policy needed for objects in this bucket. Apply every required tag from the contract. Do not add CloudFront, Route 53, a custom domain, logging, replication, versioning, or paid storage tiers.

Contract:
{contract.h_instructions()}

Click the final create/save actions only once. Return the structured answer with the exact bucket, region, tags, website status, public website URL, and blockers. Cloud CUA uploads the already-built artifact only after independently checking your result.
"""


def review_s3_creation(result: HTaskResult, contract: DeploymentContract) -> S3Review:
    if result.status != "completed":
        return S3Review("blocked", objections=(f"H ended with {result.status}: {result.summary}",))
    data = extract_json_object(result.summary)
    if not data:
        return S3Review("blocked", objections=("H did not return structured S3 creation evidence.",))
    objections: list[str] = []
    if data.get("bucket_name") != contract.resource_name:
        objections.append(f"Bucket mismatch: expected {contract.resource_name}, found {data.get('bucket_name')}.")
    if data.get("region") != contract.cloud_region:
        objections.append(f"Region mismatch: expected {contract.cloud_region}, found {data.get('region')}.")
    if data.get("website_enabled") is not True:
        objections.append("Static website hosting was not confirmed enabled.")
    tags = data.get("tags") if isinstance(data.get("tags"), dict) else {}
    for key, value in contract.required_tags.items():
        if str(tags.get(key, "")) != str(value):
            objections.append(f"Tag {key} does not match the contract.")
    url = str(data.get("public_app_url") or "")
    if not url.startswith("http") or "console.aws.amazon.com" in url:
        objections.append("H did not return a public S3 website URL.")
    if data.get("blockers"):
        objections.extend(str(item) for item in data["blockers"])
    return S3Review("blocked" if objections else "clear", str(data.get("bucket_name") or ""), url, tuple(objections))
