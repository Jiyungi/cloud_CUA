from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovalTrigger:
    code: str
    label: str
    reason: str
    severity: str = "high"


TRIGGERS = {
    "paid_resources": ApprovalTrigger("paid_resources", "Paid resources", "The action may create billable cloud resources."),
    "broad_iam": ApprovalTrigger("broad_iam", "Broad IAM", "The action may create or grant roles, policies, service accounts, or permissions."),
    "public_exposure": ApprovalTrigger("public_exposure", "Public exposure", "The action may expose an endpoint, bucket, app, or API publicly."),
    "deletion": ApprovalTrigger("deletion", "Deletion or replacement", "The action may delete, replace, or mutate existing infrastructure."),
    "secrets": ApprovalTrigger("secrets", "Secrets", "The action may require handling runtime secrets, env vars, tokens, or keys."),
    "oauth": ApprovalTrigger("oauth", "OAuth/account linking", "The action may connect GitHub, Google, AWS, or another external account."),
    "billing": ApprovalTrigger("billing", "Billing plan", "The action may touch billing, subscriptions, quotas, or paid plans."),
    "networking": ApprovalTrigger("networking", "Networking", "The action may create load balancers, VPC, DNS, TLS, or routing changes."),
    "database": ApprovalTrigger("database", "Database/state", "The action may create persistent data stores or queues."),
}


KEYWORDS = {
    "paid_resources": ["create", "deploy", "service", "compute", "app runner", "ecs", "fargate", "lambda", "amplify", "cloud run", "instance"],
    "broad_iam": ["iam", "role", "policy", "permission", "service role", "service account", "admin", "execution role"],
    "public_exposure": ["public", "url", "endpoint", "website", "api gateway", "bucket policy", "cloudfront", "load balancer", "domain"],
    "deletion": ["delete", "replace", "remove", "destroy", "terminate", "cleanup", "drop"],
    "secrets": ["secret", "token", "api key", "apikey", "env var", "environment variable", "password", "credential"],
    "oauth": ["github", "oauth", "connect account", "repository access", "authorize", "gitlab", "bitbucket"],
    "billing": ["billing", "paid", "subscription", "quota", "budget", "cost", "$"],
    "networking": ["vpc", "subnet", "load balancer", "dns", "domain", "route53", "cloudfront", "tls", "certificate"],
    "database": ["database", "rds", "dynamodb", "postgres", "mysql", "redis", "queue", "sqs", "stateful"],
}


def detect_approval_triggers(*texts: str) -> list[ApprovalTrigger]:
    blob = " ".join(text for text in texts if text).lower()
    found: list[ApprovalTrigger] = []
    for code, words in KEYWORDS.items():
        if any(word in blob for word in words):
            found.append(TRIGGERS[code])
    return found


def approval_reason(base: str, triggers: list[ApprovalTrigger], *, budget_usd: float | None = None) -> str:
    pieces = [base]
    if budget_usd is not None:
        pieces.append(f"Hard budget cap: ${budget_usd:.2f}.")
    if triggers:
        pieces.append("Detected approval triggers: " + ", ".join(trigger.label for trigger in triggers) + ".")
    return " ".join(pieces)


def risk_level(triggers: list[ApprovalTrigger]) -> str:
    if any(trigger.code in {"deletion", "broad_iam", "billing", "secrets"} for trigger in triggers):
        return "high"
    if triggers:
        return "medium"
    return "low"
