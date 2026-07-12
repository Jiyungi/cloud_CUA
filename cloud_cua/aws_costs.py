from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .aws_cli import selected_aws_profile
from .run_store import now_iso


HOURS_PER_MONTH = 730.0


@dataclass(frozen=True)
class PriceComponent:
    name: str
    service_code: str
    usage_type: str
    unit: str
    unit_price_usd: float
    quantity: float
    cadence: str
    estimated_usd: float
    sku: str
    publication_date: str


@dataclass
class CostPolicy:
    status: str
    target: str
    region: str
    max_spend_usd: float
    fixed_hourly_usd: float = 0.0
    estimated_variable_usd: float = 0.0
    estimated_accrued_usd: float = 0.0
    percent_used: float = 0.0
    started_at: str = ""
    deadline_at: str = ""
    warning_level: int = 0
    components: list[PriceComponent] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    missing_prices: list[str] = field(default_factory=list)
    message: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {**asdict(self), "components": [asdict(item) for item in self.components]}


class PriceListClient:
    def __init__(self, client: Any | None = None):
        self.client = client or self._client()

    def price(
        self,
        service_code: str,
        usage_type: str,
        region: str,
        *,
        operation: str | None = None,
        product_family: str | None = None,
    ) -> tuple[float, str, str, str]:
        filters = [
            {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
            {"Type": "TERM_MATCH", "Field": "usagetype", "Value": usage_type},
        ]
        if operation:
            filters.append({"Type": "TERM_MATCH", "Field": "operation", "Value": operation})
        response = self.client.get_products(ServiceCode=service_code, Filters=filters, FormatVersion="aws_v1", MaxResults=100)
        candidates: list[tuple[float, str, str, str]] = []
        for raw in response.get("PriceList", []):
            data = json.loads(raw) if isinstance(raw, str) else raw
            product = data.get("product", {})
            if product_family and product.get("productFamily") != product_family:
                continue
            sku = str(product.get("sku") or "")
            for term in data.get("terms", {}).get("OnDemand", {}).values():
                for dimension in term.get("priceDimensions", {}).values():
                    if str(dimension.get("beginRange", "0")) != "0":
                        continue
                    price = float(dimension.get("pricePerUnit", {}).get("USD", "0"))
                    candidates.append((price, str(dimension.get("unit") or ""), sku, str(data.get("publicationDate") or "")))
        unique = {(round(item[0], 12), item[1], item[2]): item for item in candidates if item[0] >= 0}
        if len(unique) != 1:
            raise RuntimeError(f"Expected one live price for {service_code}/{usage_type}/{operation or '*'}, found {len(unique)}.")
        return next(iter(unique.values()))

    @staticmethod
    def _client():
        import boto3

        profile = selected_aws_profile()
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        return session.client("pricing", region_name="us-east-1")


def build_cost_policy(target: str, region: str, max_spend_usd: float, pricing: PriceListClient | None = None) -> CostPolicy:
    source = pricing or PriceListClient()
    components: list[PriceComponent] = []
    missing: list[str] = []
    assumptions: list[str] = []

    def add(name: str, service: str, usage: str, quantity: float, cadence: str, *, operation: str | None = None, family: str | None = None) -> None:
        try:
            price, unit, sku, published = source.price(service, usage, region, operation=operation, product_family=family)
        except Exception as exc:
            missing.append(f"{name}: {exc}")
            return
        estimate = price * quantity
        if cadence == "monthly_to_hourly":
            estimate /= HOURS_PER_MONTH
        components.append(PriceComponent(name, service, usage, unit, price, quantity, cadence, estimate, sku, published))

    if target == "aws_ecs_express":
        add("Fargate vCPU", "AmazonECS", "USE1-Fargate-vCPU-Hours:perCPU", 0.5, "hourly")
        add("Fargate memory", "AmazonECS", "USE1-Fargate-GB-Hours", 1.0, "hourly")
        add("Application Load Balancer", "AWSELB", "LoadBalancerUsage", 1.0, "hourly", operation="LoadBalancing:Application", family="Load Balancer-Application")
        add("Application Load Balancer LCU", "AWSELB", "LCUUsage", 1.0, "hourly", operation="LoadBalancing:Application", family="Load Balancer-Application")
        add("ECR storage", "AmazonECR", "TimedStorage-ByteHrs", 0.5, "monthly_to_hourly", family="EC2 Container Registry")
        assumptions.extend(["One running Linux task: 0.5 vCPU and 1 GB memory.", "One Application Load Balancer and one LCU-hour.", "0.5 GB of ECR image storage.", "Traffic and internet data transfer can add variable cost."])
    elif target == "aws_amplify":
        prefix = "USE1-" if region == "us-east-1" else ""
        if not prefix:
            missing.append(f"Amplify live-price usage prefix is not implemented for region {region}.")
        add("Amplify build", "AWSAmplify", f"{prefix}BuildDuration", 5.0, "one_time", family="AWS Amplify")
        add("Amplify storage", "AWSAmplify", f"{prefix}DataStorage", 0.5, "monthly_to_hourly", family="AWS Amplify")
        add("Amplify transfer", "AWSAmplify", f"{prefix}DataTransferOut", 1.0, "one_time", family="AWS Amplify")
        assumptions.extend(["Five build minutes.", "0.5 GB hosted storage.", "1 GB outbound transfer; additional traffic is variable."])
    elif target == "aws_s3_static_site":
        add("S3 Standard storage", "AmazonS3", "TimedStorage-ByteHrs", 0.5, "monthly_to_hourly", family="Storage")
        add("S3 write requests", "AmazonS3", "Requests-Tier1", 1.0, "one_time", family="API Request")
        add("S3 read requests", "AmazonS3", "Requests-Tier2", 1.0, "one_time", family="API Request")
        assumptions.extend(["0.5 GB stored.", "One pricing unit each of Tier 1 and Tier 2 requests.", "Internet data transfer is variable."])
    else:
        missing.append(f"No live cost model is implemented for target {target}.")

    hourly = sum(item.estimated_usd for item in components if item.cadence in {"hourly", "monthly_to_hourly"})
    variable = sum(item.estimated_usd for item in components if item.cadence == "one_time")
    status = "ready" if not missing else "blocked"
    return CostPolicy(
        status,
        target,
        region,
        max_spend_usd,
        fixed_hourly_usd=hourly,
        estimated_variable_usd=variable,
        components=components,
        assumptions=assumptions,
        missing_prices=missing,
        message="Live AWS prices resolved." if status == "ready" else "Required live AWS prices could not be resolved.",
        updated_at=now_iso(),
    )


def save_cost_policy(path: Path, policy: CostPolicy) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(policy.to_dict(), indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def ensure_cost_policy(run_dir: Path, target: str, region: str, max_spend_usd: float, pricing: PriceListClient | None = None) -> CostPolicy:
    path = run_dir / "cost-policy.json"
    existing = load_cost_policy(path)
    if existing and existing.target == target and existing.region == region and existing.max_spend_usd == max_spend_usd:
        return existing
    policy = build_cost_policy(target, region, max_spend_usd, pricing)
    save_cost_policy(path, policy)
    return policy


def start_run_cost_clock(run_dir: Path, *, now: datetime | None = None) -> CostPolicy | None:
    path = run_dir / "cost-policy.json"
    policy = load_cost_policy(path, now=now)
    if not policy:
        return None
    start_cost_clock(policy, now=now)
    save_cost_policy(path, policy)
    return policy


def load_cost_policy(path: Path, *, now: datetime | None = None) -> CostPolicy | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["components"] = [PriceComponent(**item) for item in data.get("components", [])]
        policy = CostPolicy(**data)
    except (OSError, TypeError, json.JSONDecodeError):
        return None
    return refresh_cost_policy(policy, now=now)


def start_cost_clock(policy: CostPolicy, *, now: datetime | None = None) -> CostPolicy:
    current = now or datetime.now(UTC)
    if not policy.started_at:
        policy.started_at = current.isoformat()
    refresh_cost_policy(policy, now=current)
    if policy.fixed_hourly_usd > 0:
        remaining = max(0.0, policy.max_spend_usd - policy.estimated_accrued_usd)
        policy.deadline_at = (current + timedelta(hours=remaining / policy.fixed_hourly_usd)).isoformat()
    policy.updated_at = current.isoformat()
    return policy


def refresh_cost_policy(policy: CostPolicy, *, now: datetime | None = None) -> CostPolicy:
    current = now or datetime.now(UTC)
    accrued = policy.estimated_variable_usd
    if policy.started_at:
        started = datetime.fromisoformat(policy.started_at)
        accrued += max(0.0, (current - started).total_seconds() / 3600.0) * policy.fixed_hourly_usd
    policy.estimated_accrued_usd = round(accrued, 6)
    policy.percent_used = round((accrued / policy.max_spend_usd) * 100, 2) if policy.max_spend_usd else 100.0
    policy.warning_level = 100 if policy.percent_used >= 100 else 80 if policy.percent_used >= 80 else 50 if policy.percent_used >= 50 else 0
    policy.updated_at = current.isoformat()
    return policy
