from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cloud_cua.aws_costs import PriceListClient, build_cost_policy, load_cost_policy, save_cost_policy, start_cost_clock
from cloud_cua.cost_monitor import CostMonitor
from cloud_cua.orchestrator import Orchestrator
from cloud_cua.run_store import RunStore


class FakePricing:
    PRICES = {
        ("AmazonECS", "USE1-Fargate-vCPU-Hours:perCPU"): (0.04, "hours"),
        ("AmazonECS", "USE1-Fargate-GB-Hours"): (0.004, "hours"),
        ("AWSELB", "LoadBalancerUsage"): (0.0225, "Hrs"),
        ("AWSELB", "LCUUsage"): (0.008, "LCU-Hrs"),
        ("AmazonECR", "TimedStorage-ByteHrs"): (0.10, "GB-Mo"),
    }

    def price(self, service, usage, region, **kwargs):
        price, unit = self.PRICES[(service, usage)]
        return price, unit, f"sku-{usage}", "2026-01-01"


def test_ecs_cost_policy_uses_all_required_live_components():
    policy = build_cost_policy("aws_ecs_express", "us-east-1", 5.0, FakePricing())
    assert policy.status == "ready"
    assert len(policy.components) == 5
    assert policy.fixed_hourly_usd > 0.05
    assert policy.missing_prices == []


def test_cost_policy_blocks_when_any_required_price_is_missing():
    class MissingPricing(FakePricing):
        def price(self, service, usage, region, **kwargs):
            if usage == "LCUUsage":
                raise RuntimeError("not found")
            return super().price(service, usage, region, **kwargs)

    policy = build_cost_policy("aws_ecs_express", "us-east-1", 5.0, MissingPricing())
    assert policy.status == "blocked"
    assert any("LCU" in item for item in policy.missing_prices)


def test_cost_clock_persists_deadline_and_reaches_blocking_level(tmp_path):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    policy = build_cost_policy("aws_ecs_express", "us-east-1", 5.0, FakePricing())
    start_cost_clock(policy, now=start)
    path = save_cost_policy(tmp_path / "cost-policy.json", policy)
    later = start + timedelta(hours=(5.0 / policy.fixed_hourly_usd) + 1)
    loaded = load_cost_policy(path, now=later)
    assert loaded is not None
    assert loaded.warning_level == 100
    assert loaded.deadline_at


def test_cost_monitor_blocks_run_without_deleting_resources(tmp_path):
    store = RunStore(tmp_path)
    run = store.create_run("aws", "vibe")
    run.status = "completed"
    store.save_run(run)
    policy = build_cost_policy("aws_ecs_express", "us-east-1", 0.01, FakePricing())
    policy.started_at = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    save_cost_policy(store.run_dir(run.run_id) / "cost-policy.json", policy)
    status = CostMonitor(interval_seconds=3600).evaluate(tmp_path, run.run_id)
    updated = store.load_run(run.run_id)
    assert status["warning_level"] == 100
    assert updated.status == "cost_action_required"
    assert updated.current_step == "cleanup_or_cost_extension_required"


def test_approved_cost_extension_persists_the_new_cap(tmp_path):
    orchestrator = Orchestrator(tmp_path)
    run = orchestrator.store.create_run("aws", "vibe")
    policy = build_cost_policy("aws_ecs_express", "us-east-1", 5.0, FakePricing())
    policy.started_at = datetime.now(UTC).isoformat()
    save_cost_policy(orchestrator.store.run_dir(run.run_id) / "cost-policy.json", policy)

    approval = orchestrator.request_cost_extension(run.run_id, 10.0)
    orchestrator.decide_approval(run.run_id, approval["approval_id"], True)
    result = orchestrator.request_cost_extension(run.run_id, 10.0)

    persisted = load_cost_policy(orchestrator.store.run_dir(run.run_id) / "cost-policy.json")
    assert result["max_spend_usd"] == 10.0
    assert persisted is not None
    assert persisted.max_spend_usd == 10.0
