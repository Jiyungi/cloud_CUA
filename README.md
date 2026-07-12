# Cloud CUA

Cloud CUA is a local deployment assistant that lets Codex start and supervise cloud deployment work while H Company CUA operates the logged-in cloud console.

The current build is the local MVP shell:

- CLI: `cloud-cua init`, `cloud-cua start`, `cloud-cua mcp`, `cloud-cua check`
- MCP tools for Codex
- local dashboard at `http://127.0.0.1:3000`
- blocking manual AWS/GCP login modal
- run/event log under `.cloud-cua/runs/<run-id>/`
- live Vibe / Teach / Expert mode switching
- fast voice command router
- Gradium TTS/STT adapter boundary
- independent verifier framework
- deployment report writer
- generalized AWS deployment planner for Amplify, App Runner, ECS, Lambda, S3 static hosting, and IaC discovery
- H session cleanup for stale local browser bridge sessions

## Credentials

For local development, this repo can read `.env`, but real product usage should store keys outside the repo:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.cloud-cua"
notepad "$env:USERPROFILE\.cloud-cua\credentials.env"
```

Use:

```env
HAI_API_KEY=...
GRADIUM_API_KEY=...
```

`HAI_API_KEY` is required for real H Company CUA runs. `GRADIUM_API_KEY` is optional and enables Teach Mode voice.

## Run Locally

Use a project virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[h,dev]"
npm install
npx playwright install chromium
```

```powershell
$env:AWS_PROFILE="cloud-cua-dev"
$env:AWS_REGION="us-east-1"
python -m cloud_cua.cli check
python -m cloud_cua.cli h-status
python -m cloud_cua.cli h-cleanup
python -m cloud_cua.cli start
```

Then open:

```text
http://127.0.0.1:3000
```

## Codex MCP Setup

Add Cloud CUA as a local MCP server in Codex config:

```toml
[mcp_servers.cloud-cua]
command = "python"
args = ["-m", "cloud_cua.cli", "mcp"]
```

Then Codex can call tools such as:

- `cloud_cua_start_deployment`
- `cloud_cua_get_status`
- `cloud_cua_get_recent_events`
- `cloud_cua_set_mode`
- `cloud_cua_send_user_message`
- `cloud_cua_get_aws_plan`
- `cloud_cua_run_aws_deployment_task`
- `cloud_cua_cleanup_h_sessions`
- `cloud_cua_run_verifier`
- `cloud_cua_write_report`

## AWS Deployment Scope

Cloud CUA now treats Amplify as one AWS target, not the whole product.

The AWS planner maps repo shape to deployment options:

- frontend/static and Next.js: AWS Amplify first, S3 static hosting as an alternate
- Dockerized web apps and API services: AWS App Runner first, ECS Fargate as the heavier alternate
- serverless repos: Lambda/SAM-style inspection
- Terraform/CDK/IaC repos: console inspection and verifier support, not blind console drift
- unknown repos: CUA discovery, then stop with a recommendation

The generalized AWS runner always uses a $5 maximum spend guard, asks for approval before H operates AWS, and tells H to stop before billing changes, broad IAM, deletion of non-Cloud-CUA resources, public exposure surprises, or GitHub OAuth/account linking.

## Current External Tool Status

This repo currently has the product shell and verifier framework. Real cloud operation still depends on external tools being installed and authenticated:

- H Company Python SDK for real H CUA browser control
- Chrome with remote debugging for local browser control
- AWS CLI for AWS verifiers and Amplify checks, with `aws sts get-caller-identity --profile cloud-cua-dev` passing
- gcloud CLI for future GCP checks

If those tools are missing, Cloud CUA fails closed with `blocked` or `skipped` status rather than pretending deployment succeeded.

Current local validation:

- Chrome/Selenium local attachment works.
- AWS CLI identity verification works with profile `cloud-cua-dev`.
- H local browser control works after cleaning stale local bridge trajectories.
- If H returns HTTP 429, run `python -m cloud_cua.cli h-cleanup`; stale `surferh` bridge trajectories can consume concurrency.

## Shareable Package

Create a zip that excludes local secrets, virtualenvs, node modules, Git metadata, `.kiro`, run artifacts, and local reference folders:

```powershell
python -m cloud_cua.cli package
```

Default output:

```text
dist/cloud-cua-shareable.zip
```

## Voice Routing

Voice does not go straight to Codex or H CUA.

```text
User voice -> Gradium STT -> Cloud CUA Voice Router
```

Fast commands like `pause`, `continue`, `switch to Teach mode`, and `run verifier` execute directly in the backend.

Questions like `why Amplify?` route to Codex or the explanation path.

Cloud operation requests become planned, approval-gated tasks. Raw voice is never sent directly to H CUA.

## Tests

Run tests from the activated project virtual environment:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
```
