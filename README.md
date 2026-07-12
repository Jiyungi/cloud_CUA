# Cloud CUA

Cloud CUA is a local deployment assistant that lets Codex start and supervise cloud deployment work while H Company CUA operates the logged-in cloud console.

The current build is the local MVP shell:

- CLI: `cloud-cua init`, `cloud-cua start`, `cloud-cua mcp`, `cloud-cua check`, `cloud-cua doctor`, `cloud-cua install-mcp`, `cloud-cua h-skills`, `cloud-cua aws-cleanup`
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
- generalized AWS deployment planner for Amplify, ECS Express Mode, Lambda, S3 static hosting, and IaC discovery
- H session cleanup for stale local browser bridge sessions
- Cloud-CUA-tagged AWS cleanup dry run and delete command
- local YAML deployment skills that auto-sync to the user's H skill catalog
- per-run deployment contracts, milestone supervision, and review-only lesson candidates

## Install The Local Product

From a source checkout on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

On macOS/Linux:

```bash
./scripts/install.sh
```

The installer creates `~/.cloud-cua/runtime-venv`, installs Cloud CUA and H's browser dependencies, and writes the Codex MCP entry with that environment's absolute Python path. Restart Codex after installation.

Service controls:

```powershell
cloud-cua service status
cloud-cua service start
cloud-cua service stop
cloud-cua service restart
```

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
args = ["-I", "-m", "cloud_cua.cli", "mcp"]
```

Then Codex can call tools such as:

- `cloud_cua_start_deployment`
- `cloud_cua_get_status`
- `cloud_cua_get_recent_events`
- `cloud_cua_watch_run`
- `cloud_cua_get_pending_actions`
- `cloud_cua_set_mode`
- `cloud_cua_send_user_message`
- `cloud_cua_get_aws_plan`
- `cloud_cua_run_aws_deployment_task`
- `cloud_cua_get_gcp_plan`
- `cloud_cua_run_gcp_cloud_run_task`
- `cloud_cua_cleanup_h_sessions`
- `cloud_cua_get_skill_status`
- `cloud_cua_sync_h_skills`
- `cloud_cua_get_lesson_candidate`
- `cloud_cua_get_runtime_configuration_status`
- `cloud_cua_get_cost_status`
- `cloud_cua_cancel_h_cua`
- `cloud_cua_cleanup_aws_resources`
- `cloud_cua_run_verifier`
- `cloud_cua_write_report`

Restart Codex after installing the MCP server so it reloads config.

## H Deployment Skills

Cloud CUA stores reviewed deployment recipes under `cloud_cua/skills/` and publishes them to the user's private H skill catalog. These are real H skills attached to the browser agent by name:

- `cloud-cua/aws-ecs-express`
- `cloud-cua/aws-amplify`
- `cloud-cua/aws-s3-static`
- `cloud-cua/gcp-cloud-run`

Inspect or synchronize them from the CLI:

```powershell
python -m cloud_cua.cli h-skills list
python -m cloud_cua.cli h-skills sync --dry-run
python -m cloud_cua.cli h-skills sync
```

The active skill auto-syncs before a deployment H session. A failed sync blocks browser operation instead of falling back to hidden prompt instructions. Synced skills are also visible in the H web skill catalog for the API key's organization.

For ECS Express, Cloud CUA saves `.cloud-cua/runs/<run-id>/contract.json` and uses three H milestones: inspect without mutation, prepare without submission, then submit once. The backend reviews structured H answers after the first two milestones and stores clear checkpoints in `milestones.json`. H trajectory events and hosted session IDs appear in the dashboard while the session runs.

If H or a verifier fails, Cloud CUA writes `.cloud-cua/runs/<run-id>/lesson_candidate.json`. The dashboard and MCP expose it, but Cloud CUA never silently rewrites a trusted skill from one failed run. A later strict success marks stale lesson evidence `resolved` instead of deleting it.

## Docker Quickstart

The Docker path runs the dashboard, MCP server code, repo analyzer, AWS CLI verifiers, and Docker image prep in a container:

```powershell
docker compose up -d --build --wait
```

Open:

```text
http://127.0.0.1:3000
```

If port 3000 is already in use, set `CLOUD_CUA_DOCKER_PORT` before starting Compose. Set `CLOUD_CUA_REPO_PATH` to deploy a repository other than the directory containing this Compose file.

Docker mounts your local `.aws`, `.config/gcloud`, `.cloud-cua`, and host Docker socket. It does not remove the need for manual cloud login in a browser. Full H local browser takeover still works best from the host-local Python app, because the cloud-console login, MFA, Chrome profile, and H browser bridge live on your machine.

By default, Compose uses `AWS_PROFILE=cloud-cua-dev`, matching the setup profile in this repo. Override it before starting Docker if your AWS profile has another name.

The Docker image includes Playwright Chromium, AWS CLI, Node, npm, and Docker CLI so dashboard, build, and independent rendering checks work without a second setup command. H's local Chrome bridge remains host-only and blocks honestly in container mode.

## AWS Deployment Scope

Cloud CUA now treats Amplify as one AWS target, not the whole product.

The AWS planner maps repo shape to deployment options:

- frontend/static and Next.js: AWS Amplify first, S3 static hosting as an alternate
- Dockerized web apps and API services: ECS Express Mode first; Cloud CUA builds/pushes a Docker image to ECR before asking H CUA to operate the ECS console
- AWS App Runner: blocked for new AWS accounts and listed only as a deprecated option, because AWS closed App Runner to new customers and recommends ECS Express Mode
- serverless repos: Lambda/SAM-style inspection
- Terraform/CDK/IaC repos: console inspection and verifier support, not blind console drift
- unknown repos: CUA discovery, then stop with a recommendation

The generalized AWS runner uses a $5 default policy cap, asks for approval before H operates AWS, and tells H to stop before billing changes, broad IAM, deletion of non-Cloud-CUA resources, public exposure surprises, or GitHub OAuth/account linking. Required prices come from the AWS Price List API. Missing prices block the run. The dashboard warns at 50% and 80%; at 100%, cleanup or an approved extension is required. This is an estimate because AWS billing data is delayed, and Cloud CUA never automatically deletes a live deployment.

Before modification, H reads the AWS account ID visible in Chrome. Cloud CUA compares it with `aws sts get-caller-identity` and blocks mismatches.

Application secrets are entered only through the blocking dashboard configuration modal. New values go directly to tagged SSM Standard `SecureString` parameters; only parameter ARNs are retained in the contract. `VITE_*` and `NEXT_PUBLIC_*` names are treated as public build configuration, not secrets.

Cloud CUA tells H to tag new resources with:

```text
cloud-cua=true
cloud-cua-repo=<repo-name>
cloud-cua-run=<run-id>
```

For ECS Express, the verifier checks the exact run tag, task-definition image, contracted container port, running task count, rollout state, target health, public app URL, HTTP response, Playwright rendering, report, and cleanup discovery. Missing proof leaves the run `blocked`.

Cleanup is explicit:

```powershell
python -m cloud_cua.cli aws-cleanup
python -m cloud_cua.cli aws-cleanup --run-id <run-id>
python -m cloud_cua.cli aws-cleanup --yes
```

Without `--yes`, cleanup is a dry run.

## GCP Scope

GCP is planning-only in this release. The product can:

- analyze whether the repo fits Cloud Run;
- create an approval-gated GCP Cloud Run H task;
- verify `gcloud auth`, selected project, and Cloud Run services.

It still requires `gcloud` installation/auth, browser/CLI project identity matching, a hardened exact verifier, a real deployment, and cleanup proof before it can be called production-ready.

## Current External Tool Status

The ECS Express and S3 static paths have completed real H-operated AWS deployments and passed exact-run AWS, HTTP, and Playwright verification. Real cloud operation still depends on external tools being installed and authenticated:

- H Company Python SDK for real H CUA browser control
- Chrome with remote debugging for local browser control
- AWS CLI for AWS verifiers, ECR image preparation, and target-service checks, with `aws sts get-caller-identity --profile cloud-cua-dev` passing
- gcloud CLI for future GCP checks

If those tools are missing, Cloud CUA fails closed with `blocked` or `skipped` status rather than pretending deployment succeeded.

Current local validation:

- Chrome/Selenium local attachment works.
- AWS CLI identity verification works with profile `cloud-cua-dev`.
- H local browser control works after cleaning stale local bridge trajectories.
- H hosted skills auto-sync and attach to the browser agent before skilled runs.
- The verified ECS smoke used the exact ECR image, port, health path, and run tags, reached one healthy running task, returned HTTP 200, rendered in Playwright, and ended with zero remaining cleanup actions.
- The verified S3 smoke used H for bucket creation/tags and website configuration, applied a generated bucket-scoped policy only after API checks, returned HTTP 200, rendered in managed Playwright, and ended with zero run-tagged resources.
- If H returns HTTP 429, run `python -m cloud_cua.cli h-cleanup`; stale `surferh` bridge trajectories can consume concurrency.

## Shareable Package

Create a zip that includes an installable wheel and excludes local secrets, virtualenvs, node modules, Git metadata, `.kiro`, run artifacts, and local reference folders:

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

Questions like `why this service?` route to Codex or the explanation path.

Cloud operation requests become planned, approval-gated tasks. Raw voice is never sent directly to H CUA.

## AWS H Console Evaluations

`cloud_cua/aws_eval_catalog.yaml` defines 150 safety-focused H computer-use evaluations across 50 AWS services. Each service includes guided provisioning, a deliberate misconfiguration trap, and recovery/cleanup. These local commands validate and inspect cases or generate review-only skill candidates; they do not create AWS resources:

```bash
cloud-cua aws-evals validate
cloud-cua aws-evals list
cloud-cua aws-evals show --case ecr-misconfiguration-trap
cloud-cua aws-evals skill-seed --service ecr
cloud-cua aws-evals build-skills
```

See [the AWS H evaluation catalog guide](docs/aws-h-evaluation-catalog.md) for scoring and skill-promotion rules.

## Tests

Run tests from the activated project virtual environment:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
```

Run visual dashboard smoke checks against a running dashboard:

```powershell
npm run visual:dashboard
```

The visual smoke opens desktop and mobile Chromium viewports, verifies the main dashboard controls, checks for horizontal overflow, opens the login modal, and writes screenshots plus a JSON summary under `.cloud-cua/visual-checks/`.
