from __future__ import annotations

import json
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
    return f"""Milestone: prepare_s3_static_bucket

Use the loaded cloud-cua/aws-s3-static skill. User approval is granted for this exact Cloud CUA bucket. This milestone creates and tags the bucket only; do not configure website hosting or a bucket policy yet.

Open S3 and inspect whether {contract.resource_name} exists. If it does not exist, create it in {contract.cloud_region}, clear bucket-level Block Public Access with its acknowledgment, and apply every required contract tag. If it already exists, continue only when every required tag proves it belongs to this exact run; otherwise stop. Do not add CloudFront, Route 53, a custom domain, logging, replication, versioning, or paid storage tiers.

Contract:
{contract.h_instructions()}

Click each final save/create action only once. Return the structured answer with the exact bucket, region, tags, and blockers. Set website_enabled=false and public_app_url=null because those belong to the next milestone.
"""


def build_s3_website_task(contract: DeploymentContract) -> str:
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CloudCUAPublicRead",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{contract.resource_name}/*",
            }
        ],
    }
    return f"""Milestone: configure_s3_static_website

The prior saved checkpoint proved that bucket {contract.resource_name} exists in {contract.cloud_region}, has bucket-level public access unblocked, and carries every required tag for this exact run. Use the loaded cloud-cua/aws-s3-static skill.

Open this exact bucket Properties page directly: https://s3.console.aws.amazon.com/s3/buckets/{contract.resource_name}?region={contract.cloud_region}&tab=properties

Configure static website hosting with index.html as both the index and error document. Then open Permissions and add exactly this bucket-scoped public-read policy:
{json.dumps(policy, indent=2)}

Do not change tags, ownership, ACLs, versioning, logging, replication, CloudFront, Route 53, or any other bucket.

Contract:
{contract.h_instructions()}

Save each form only once. Return immediately after the Properties page visibly confirms website hosting is enabled. Return the exact bucket, region, required tags, public website endpoint, and blockers through the structured schema.
"""


def review_s3_bucket(result: HTaskResult, contract: DeploymentContract) -> S3Review:
    if result.status != "completed":
        return S3Review("blocked", objections=(f"H ended with {result.status}: {result.summary}",))
    data = extract_json_object(result.summary)
    if not data:
        return S3Review("blocked", objections=("H did not return structured S3 bucket evidence.",))
    objections: list[str] = []
    if data.get("bucket_name") != contract.resource_name:
        objections.append(f"Bucket mismatch: expected {contract.resource_name}, found {data.get('bucket_name')}.")
    if data.get("region") != contract.cloud_region:
        objections.append(f"Region mismatch: expected {contract.cloud_region}, found {data.get('region')}.")
    tags = data.get("tags") if isinstance(data.get("tags"), dict) else {}
    for key, value in contract.required_tags.items():
        if str(tags.get(key, "")) != str(value):
            objections.append(f"Tag {key} does not match the contract.")
    if data.get("blockers"):
        objections.extend(str(item) for item in data["blockers"])
    return S3Review("blocked" if objections else "clear", str(data.get("bucket_name") or ""), objections=tuple(objections))


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
