from __future__ import annotations

import json
from pathlib import Path

from .approvals import load_approvals
from .agent_test_contract import load_agent_test_contract
from .run_store import RunStore


def write_report(repo_path: str | Path, run_id: str) -> Path:
    store = RunStore(repo_path)
    run = store.load_run(run_id)
    events = store.read_events(run_id, limit=1000)
    verifier_dir = store.verifier_dir(run_id)
    verifier_files = sorted(verifier_dir.glob("*.json"))
    approvals = load_approvals(store.run_dir(run_id))
    fixture = load_agent_test_contract(repo_path)
    path = Path(repo_path).resolve() / "DEPLOYMENT_REPORT.md"

    event_lines = "\n".join(
        f"- `{e['time']}` **{e['source']}:{e['type']}** {e['message']}" for e in events[-50:]
    )
    verifier_rows: list[str] = []
    for vf in verifier_files:
        try:
            data = json.loads(vf.read_text(encoding="utf-8"))
            verifier_rows.append(f"- `{data.get('name', vf.stem)}`: **{data.get('status', 'unknown')}** - {data.get('summary', '')[:240]} (`{vf}`)")
        except Exception:
            verifier_rows.append(f"- `{vf.name}`: `{vf}`")
    verifier_lines = "\n".join(verifier_rows) or "- No verifier artifacts yet."
    approval_lines = "\n".join(
        f"- **{item.status}** `{item.risk_level}` {item.action} - {item.reason}" for item in approvals
    ) or "- No approvals requested yet."
    next_action = "Review verifier artifacts and cloud resources before sharing or production use."
    if run.status in {"blocked", "failed"}:
        next_action = "Resolve the blocking step shown above, then rerun the verifier before continuing."
    scope_note = ""
    if run.deployment_scope == "frontend_preview" and fixture:
        missing_backend = ", ".join(fixture.required_aws_services[1:])
        scope_note = (
            "\n> Frontend preview only: Amplify hosting is in scope. "
            f"The application backend was not deployed ({missing_backend}).\n"
        )

    content = f"""# Deployment Report

## Summary

- Run: `{run.run_id}`
- Cloud: `{run.cloud}`
- Target: `{run.target}`
- Deployment scope: `{run.deployment_scope}`
- Mode: `{run.mode}`
- Status: `{run.status}`
- Current step: `{run.current_step}`
{scope_note}

## Verifier Artifacts

{verifier_lines}

## Approvals

{approval_lines}

## Recent Events

{event_lines or "- No events recorded."}

## Manual State

Cloud CUA may have operated cloud-console UI through H CUA. Any cloud-console state not captured by verifier artifacts should be reviewed before production use.

## Cleanup / Next Steps

- {next_action}
- Review cloud resources in the provider console.
- Review verifier artifacts under `.cloud-cua/runs/{run.run_id}/verifier-results/`.
- Do not share run artifacts without checking for sensitive screenshots or logs.
"""
    path.write_text(content, encoding="utf-8")
    store.append_event(run_id, "system", "result", "Wrote deployment report.", {"path": str(path)})
    return path
