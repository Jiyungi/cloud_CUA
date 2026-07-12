from __future__ import annotations

from cloud_cua.aws_cleanup import CleanupAction, _actions_from_arn, _dedupe_actions


def test_amplify_arn_extracts_real_app_id() -> None:
    actions = _actions_from_arn("arn:aws:amplify:us-east-1:123456789012:apps/dlxrss6fqphr3")
    assert len(actions) == 1
    assert actions[0].resource == "dlxrss6fqphr3"
    assert actions[0].command[-2:] == ["--app-id", "dlxrss6fqphr3"]


def test_cleanup_deduplicates_same_command_from_name_and_tag_discovery() -> None:
    command = ["aws", "amplify", "delete-app", "--app-id", "app123"]
    actions = _dedupe_actions(
        [
            CleanupAction("amplify", "cloud-cua-demo", command),
            CleanupAction("amplify", "app123", command),
        ]
    )
    assert len(actions) == 1
