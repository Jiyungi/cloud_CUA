from __future__ import annotations

from .models import RepoContext, Run


def explain_run_question(question: str, run: Run, context: RepoContext, cost_status: dict | None = None) -> str:
    lower = question.lower()
    if "why" in lower and any(word in lower for word in ("service", "ecs", "amplify", "s3", "target")):
        return (
            f"Cloud CUA selected {run.target} because the repository was classified as {context.category} "
            f"with framework {context.framework}. The deterministic recommendation was {context.recommendation}."
        )
    if "cost" in lower or "cheaper" in lower:
        if cost_status and cost_status.get("status") == "ready":
            return (
                f"The current live-price estimate is ${cost_status.get('fixed_hourly_usd', 0):.4f} per hour in fixed cost, "
                f"plus about ${cost_status.get('estimated_variable_usd', 0):.4f} under the saved usage assumptions. "
                f"The run policy cap is ${cost_status.get('max_spend_usd', 0):.2f}."
            )
        return "Cloud CUA has not resolved a complete live AWS price estimate for this run yet. Paid creation remains blocked until it does."
    if "iam" in lower or "permission" in lower:
        return "IAM controls which AWS identity may perform each action. Cloud CUA stops on broad or unexpected permissions and asks for approval instead of granting administrator access."
    if "error" in lower or "failed" in lower or "wrong" in lower:
        return f"The run is currently {run.status} at step {run.current_step}. The Activity and Proof panels contain the operator observation and independent verifier evidence."
    if "what is" in lower:
        return f"This run deploys a {context.category} repository to {run.target}. Cloud CUA plans and verifies it while H CUA operates the cloud console."
    return f"The run is {run.status} at {run.current_step}. Its selected target is {run.target}. Ask about the target, cost, permissions, or current error for a more specific explanation."
