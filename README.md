# Cloud CUA

Cloud CUA is a local deployment assistant that lets Codex start and supervise cloud deployment work while H Company CUA operates the logged-in cloud console.

The current build is the local MVP shell:

- CLI: `cloud-cua init`, `cloud-cua start`, `cloud-cua mcp`, `cloud-cua check`, `cloud-cua doctor`, `cloud-cua install-mcp`, `cloud-cua aws-cleanup`
- MCP tools for Codex
- local dashboard at `http://127.0.0.1:3000`
- blocking manual AWS/GCP login modal
- run/event log under `.cloud-cua/runs/<run-id>/`
- live Vibe / Teach / Expert mode switching
- fast voice command router
- Gradium TTS/STT adapter boundary
- browser microphone recording and TTS playback in the dashboard when Gradium is configured
- independent verifier framework
- deployment report writer
- generalized AWS deployment planner for Amplify, App Runner, ECS, Lambda, S3 static hosting, and IaC discovery
- H session cleanup for stale local browser bridge sessions
- Cloud-CUA-tagged AWS cleanup dry run and delete command

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
python -m cloud_cua.cli doctor
python -m cloud_cua.cli h-status
python -m cloud_cua.cli h-cleanup
python -m cloud_cua.cli start
```

Then open:

```text
http://127.0.0.1:3000
```

## Codex MCP Setup

Install Cloud CUA as a local MCP server in Codex config:

```powershell
python -m cloud_cua.cli install-mcp
```

That writes this server entry into `~/.codex/config.toml` and creates a backup if the file already existed:

```toml
[mcp_servers.cloud-cua]
command = "<this Python executable>"
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
- `cloud_cua_get_gcp_plan`
- `cloud_cua_run_gcp_cloud_run_task`
- `cloud_cua_cleanup_h_sessions`
- `cloud_cua_cleanup_aws_resources`
- `cloud_cua_run_verifier`
- `cloud_cua_write_report`

Restart Codex after installing the MCP server so it reloads config.

## Docker Quickstart

The Docker path runs the dashboard, MCP server code, repo analyzer, and verifiers in a container:

```powershell
docker compose up --build
```

Open:

```text
http://127.0.0.1:3000
```

Docker mounts your local `.aws`, `.config/gcloud`, and `.cloud-cua` folders read-only. It does not remove the need for manual cloud login in a browser. H local browser takeover still depends on a host browser session, because the cloud-console login, MFA, and Chrome profile live on your machine.

## AWS Deployment Scope

Cloud CUA now treats Amplify as one AWS target, not the whole product.

The AWS planner maps repo shape to deployment options:

- frontend/static and Next.js: AWS Amplify first, S3 static hosting as an alternate
- Dockerized web apps and API services: AWS App Runner first, ECS Fargate as the heavier alternate
- serverless repos: Lambda/SAM-style inspection
- Terraform/CDK/IaC repos: console inspection and verifier support, not blind console drift
- unknown repos: CUA discovery, then stop with a recommendation

The generalized AWS runner always uses a $5 maximum spend guard, asks for approval before H operates AWS, and tells H to stop before billing changes, broad IAM, deletion of non-Cloud-CUA resources, public exposure surprises, or GitHub OAuth/account linking.

Cloud CUA tells H to tag new resources with:

```text
cloud-cua=true
cloud-cua-repo=<repo-name>
cloud-cua-run=<run-id>
```

The verifier checks tagged resources through AWS Resource Groups Tagging API so proof is tied to the exact run when AWS exposes tags for the selected service.

Cleanup is explicit:

```powershell
python -m cloud_cua.cli aws-cleanup
python -m cloud_cua.cli aws-cleanup --run-id <run-id>
python -m cloud_cua.cli aws-cleanup --yes
```

Without `--yes`, cleanup is a dry run.

## GCP Scope

GCP is now a real planned path for Cloud Run, not just a note. The product can:

- analyze whether the repo fits Cloud Run;
- create an approval-gated GCP Cloud Run H task;
- verify `gcloud auth`, selected project, and Cloud Run services.

It still requires local `gcloud` auth and manual GCP browser login before H operates the console.

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
