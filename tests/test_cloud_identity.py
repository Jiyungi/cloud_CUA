from __future__ import annotations

import json

from cloud_cua.cloud_identity import review_aws_browser_identity
from cloud_cua.h_runner import HTaskResult


def test_browser_identity_match_requires_exact_twelve_digit_account():
    result = HTaskResult(
        "completed",
        json.dumps({"milestone": "verify_aws_browser_identity", "status": "observed", "account_id": "1234-5678-9012", "console_url": "https://console.aws.amazon.com/"}),
    )
    proof = review_aws_browser_identity(result, "123456789012")
    assert proof.status == "matched"


def test_browser_identity_mismatch_is_blocking():
    result = HTaskResult("completed", json.dumps({"account_id": "999999999999", "console_url": "https://console.aws.amazon.com/"}))
    proof = review_aws_browser_identity(result, "123456789012")
    assert proof.status == "mismatched"
    assert proof.browser_account_id == "999999999999"


def test_browser_identity_loose_prose_is_not_evidence():
    proof = review_aws_browser_identity(HTaskResult("completed", "It looks correct."), "123456789012")
    assert proof.status == "blocked"
