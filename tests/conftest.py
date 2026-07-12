from __future__ import annotations

import pytest

from cloud_cua.aws_costs import CostPolicy, save_cost_policy


@pytest.fixture(autouse=True)
def deterministic_orchestrator_pricing(monkeypatch):
    def fake(run_dir, target, region, max_spend_usd):
        policy = CostPolicy(
            "ready",
            target,
            region,
            max_spend_usd,
            fixed_hourly_usd=0.05,
            assumptions=["test pricing"],
            message="Test prices resolved.",
        )
        save_cost_policy(run_dir / "cost-policy.json", policy)
        return policy

    monkeypatch.setattr("cloud_cua.orchestrator.ensure_cost_policy", fake)
