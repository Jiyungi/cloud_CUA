from __future__ import annotations

import json

from cloud_cua.models import RepoContext
from cloud_cua.verifier.repo import verify_repository


def test_repo_verifier_runs_detected_build(tmp_path):
    context = RepoContext("python", "api_service", "python", 'python -c "print(123)"', None, None, False, [], [], "aws_lambda")
    results = verify_repository(tmp_path, context)
    build = next(item for item in results if item.name == "repo_build")
    assert build.status == "passed"
    assert "123" in build.summary


def test_repo_verifier_refuses_unknown_executable(tmp_path):
    context = RepoContext("unknown", "unknown", "", "dangerous-command --all", None, None, False, [], [], "blocked")
    results = verify_repository(tmp_path, context)
    build = next(item for item in results if item.name == "repo_build")
    assert build.status == "failed"
    assert "Refused" in build.summary
