# Cloud CUA Target Product State

## Product Definition

Cloud CUA is a local deployment assistant for developers who have finished coding an app and want to deploy it to AWS or GCP.

It connects three roles:

- Codex understands the repo and the user's constraints.
- H Company CUA operates the cloud console in a logged-in browser.
- Cloud/API verifiers check what actually happened without trusting the CUA.

The product is not a generic AWS click bot, not a Terraform-first tool, and not a hosted SaaS in the first version.

## Main User Flow

1. The user is already working in VS Code, Codex, Cursor, or another coding environment.
2. The user says: "Deploy this repo with Cloud CUA in Vibe mode."
3. Codex calls the Cloud CUA MCP server.
4. Cloud CUA starts or connects to its local backend.
5. The local dashboard opens at `http://localhost:3000`.
6. The user chooses AWS or GCP, confirms the mode, and reviews the detected repo.
7. Cloud CUA opens a dedicated browser profile for cloud-console work.
8. A blocking login popup appears.
9. The user logs into AWS or GCP manually.
10. After login, the user clicks Continue.
11. H CUA controls that same browser session and performs the cloud-console work.
12. Codex watches events, checks the repo context, objects when something looks wrong, and suggests fixes.
13. Independent verifiers check cloud state, audit logs, and the live app URL.
14. Cloud CUA writes a final deployment report back into the repo.

## Required Login Popup

Before H CUA can operate AWS or GCP, the dashboard must show a prominent blocking modal.

The modal must blur or dim the rest of the dashboard until the user finishes login.

Required copy:

```text
Log into AWS in this browser window. Click Continue when done.
```

For GCP, use:

```text
Log into GCP in this browser window. Click Continue when done.
```

The user must log in manually. Cloud CUA must not try to solve captcha, MFA, SSO, or password-manager prompts.

## Product Surfaces

Cloud CUA has three surfaces, but it is one product.

| Surface | Who uses it | Purpose |
| --- | --- | --- |
| MCP server | Codex and other coding agents | Lets the agent call Cloud CUA from the repo context. |
| Local dashboard | Human user | Shows status, approvals, voice controls, logs, and deployment result. |
| CLI | Installer and launcher | Starts the backend, installs MCP config, and manages credentials. |

The CLI is not the main user experience. It exists so the dashboard and MCP server can start reliably.

Expected commands:

```bash
cloud-cua init
cloud-cua start
cloud-cua mcp
```

## API Key Handling

Ask for the H Company API key once per machine, not every deployment.

Use the official environment variable name:

```env
HAI_API_KEY=...
```

Default credential storage:

```text
~/.cloud-cua/credentials.env
```

Windows path:

```text
C:\Users\<user>\.cloud-cua\credentials.env
```

Example:

```env
HAI_API_KEY=...
GRADIUM_API_KEY=...
```

Ask again only when:

- the key is missing;
- the key is invalid;
- the user clicks "Change key";
- the user is on a new machine.

Do not save secrets in the repo by default.

If project-local credentials are supported later, they must go in:

```text
.cloud-cua/.env.local
```

and Cloud CUA must add this to `.gitignore`:

```gitignore
.cloud-cua/.env.local
```

MCP does not bypass the H key. MCP only connects Codex to Cloud CUA. Cloud CUA still needs `HAI_API_KEY` to call H.

## Browser Ownership

Cloud CUA must not vaguely "take over Chrome."

It must create or attach to a dedicated browser profile for cloud-console work.

Target behavior:

1. Open a dedicated Chrome profile.
2. Open AWS or GCP console.
3. Show the blocking login popup.
4. Wait for the user to click Continue.
5. Start the H CUA run against that same browser.

Use one cloud-console browser profile, one deployment task, and one primary console tab per run.

Do not use the user's everyday browser profile by default.

## Agent Coordination

Codex and H CUA must coordinate through Cloud CUA. They should not free-chat.

Cloud CUA owns the run state and event log.

Event log path:

```text
.cloud-cua/runs/<run-id>/events.jsonl
```

Event shape:

```json
{
  "time": "2026-07-11T12:00:00Z",
  "source": "codex | h_cua | verifier | user | system",
  "type": "plan | command | observation | objection | approval | result | error",
  "message": "Plain-English event text",
  "evidence": {}
}
```

Codex and H CUA "argue" by posting objections with evidence.

Example:

```json
{
  "source": "codex",
  "type": "objection",
  "message": "Do not continue. The AWS console is asking for GitHub OAuth approval, which requires user consent.",
  "evidence": {
    "h_observation": "GitHub authorization screen is visible"
  }
}
```

## MCP Tools

The MCP server should expose small, explicit tools.

Minimum tools:

```text
cloud_cua_start_deployment(repo_path, cloud, mode)
cloud_cua_open_dashboard(run_id)
cloud_cua_get_status(run_id)
cloud_cua_get_recent_events(run_id)
cloud_cua_set_mode(run_id, mode)
cloud_cua_send_user_message(run_id, message)
cloud_cua_pause_h_cua(run_id)
cloud_cua_resume_h_cua(run_id)
cloud_cua_request_approval(run_id, action, reason)
cloud_cua_run_verifier(run_id, verifier_name)
cloud_cua_write_report(run_id)
```

H CUA desktop/browser tasks must be short and specific.

Bad task:

```text
Deploy this app.
```

Good task:

```text
Open the AWS console tab, go to CloudTrail Event history, search for CreateService events from the last 30 minutes, and report whether any ECS service was created. Do not change anything.
```

## Modes

The modes are behavior policies, not separate products.

The user can switch modes from the dashboard at any time.

Required dashboard control:

```text
[ Vibe ] [ Teach ] [ Expert ]
```

When the user clicks a mode button, Cloud CUA must:

1. update the current run mode immediately;
2. write a `mode_changed` event to the run log;
3. notify Codex through MCP status/events;
4. include the new mode instructions in the next H CUA task or steering message;
5. keep the existing deployment run alive unless the current step is unsafe to continue.

Example event:

```json
{
  "source": "user",
  "type": "mode_changed",
  "message": "User switched from Vibe Mode to Teach Mode.",
  "evidence": {
    "from": "vibe",
    "to": "teach"
  }
}
```

### Vibe Mode

User goal: "Just make this work."

Behavior:

- ask the fewest questions;
- choose safe defaults;
- pause for paid resources, destructive actions, broad permissions, missing secrets, or user login;
- explain only the result and major risks.

### Teach Mode

User goal: "Deploy this and teach me what is happening."

Behavior:

- explain each major cloud step in simple language;
- use Gradium voice for user questions and agent explanations;
- pause before important concepts like IAM, region, database, SSL, domain, and budget;
- keep explanations short and tied to the current screen.

### Expert Mode

User goal: "I know infra. Ask me the real tradeoffs."

Behavior:

- ask architecture tradeoff questions;
- show service choices and consequences;
- let user override defaults;
- skip beginner explanations.

Example expert questions:

```text
Use AWS Amplify for a simpler frontend flow, or ECS Express Mode for container control?
Use an existing DATABASE_URL, or provision a managed database?
Single-region low cost, or multi-AZ reliability?
Public endpoint behind HTTPS, or private service only?
```

## Chosen Verifier Stack

The verifier must not depend on CUA. It must use APIs, CLIs, audit logs, local repo checks, and normal HTTP/browser checks.

Use this stack first because it is mostly free, independent of H CUA, and checks the actual system rather than the agent's opinion.

| Layer | Tool | What it proves | Cost note |
| --- | --- | --- | --- |
| Local repo proof | Git diff, framework build/test commands | The repo still builds and Cloud CUA changed only expected files. | Free. |
| Identity proof | `aws sts get-caller-identity`, `gcloud auth list`, `gcloud config get-value project` | The verifier is checking the intended cloud account/project. | Free commands; normal local credentials required. |
| Resource proof | AWS CLI/SDK `describe/list`, GCP `gcloud ... describe/list` | The claimed cloud resources actually exist. | Usually no separate verifier cost, but permissions are required. |
| Action proof | AWS CloudTrail Event history, GCP Cloud Audit Logs | What console/API actions happened and who performed them. | AWS management event history is available for 90 days at no additional CloudTrail charge; GCP Admin Activity logs are the free baseline. |
| Live app proof | `curl` or `fetch` against the deployed URL | The app endpoint responds. | Free. |
| Render proof | Playwright against the deployed URL | The app renders the expected page and not only a blank/error response. | Free local tool; not CUA. |
| Report proof | `DEPLOYMENT_REPORT.md` and `.cloud-cua/runs/<run-id>/events.jsonl` | The deployment has a replayable record for the user and Codex. | Free. |

Terraform is not the primary verifier for the MVP. Use Terraform later for IaC consistency checks or import notes, but do not treat Terraform state as ground truth for console-driven work.

CloudWatch and Cloud Logging are useful for debugging, but they are not the first verifier because log ingestion, storage, and query usage can cost money. Use them when the live app check fails or the cloud resource is unhealthy.

Avoid making H CUA's final answer the verifier. H's own outcome is useful routing data, not ground truth.

### MVP Verifier Commands

For AWS:

```bash
aws sts get-caller-identity
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=<expected-event>
```

Then run service-specific checks depending on the deployment target:

```bash
aws amplify list-apps
aws ecs describe-services --cluster <cluster> --services <service>
aws elbv2 describe-load-balancers --names <name>
```

For GCP:

```bash
gcloud auth list
gcloud config get-value project
gcloud run services describe <service> --region <region>
gcloud logging read '<audit-or-service-filter>' --limit 20
```

For the live app:

```bash
curl -I <deployed-url>
npx playwright test
```

## What To Reuse

### H Company

Reuse:

- Computer-Use Agents for visual browser work.
- Local browser control for signed-in user sessions.
- HoloDesktop CLI MCP for quick Codex-to-desktop experiments.
- Session status, changes, and events for progress and replay.
- Custom tools for local checks and API calls during an H run.
- HoloTab only as UX inspiration, not as the product itself.

Do not build:

- a new browser-control model;
- a generic HoloTab clone;
- a captcha/MFA bypasser;
- a fake verifier based on screenshots only.

### OpenAI Codex

Reuse:

- Codex repo understanding.
- Codex MCP client support.
- Codex config for local/project MCP server registration.
- Codex IDE/desktop/CLI surfaces as entry points.

Do not build first:

- a full VS Code extension;
- a second coding agent;
- a custom IDE.

MCP is enough for the first integration.

### AWS

Reuse:

- AWS CLI and SDKs.
- CloudTrail Event history.
- Resource Explorer.
- CloudWatch logs only when needed.
- ECS Express Mode, Amplify, S3/CloudFront, Lambda, or other managed deploy targets depending on repo type.

Do not scrape AWS console for verification when an API or audit log can answer the question.

### GCP

Reuse:

- `gcloud` CLI.
- Cloud Run for simple container/web deployments.
- Cloud Audit Logs.
- Cloud Logging only when needed.

### Gradium

Reuse:

- STT for user voice commands.
- TTS for Teach Mode explanations.
- WebSocket/streaming paths for low-latency voice when available.

Do not build a custom speech model.

## Constraints

### H Company Constraints

- Local browser control is Python SDK centered today.
- A local Python process drives one local browser at a time.
- H local browser uses a dedicated Chrome profile and remote debugging.
- HoloDesktop CLI MCP exposes one blocking `holo_desktop(task: str)` tool.
- Long desktop MCP calls can be hard to cancel depending on the host.
- H sessions can end `completed` while still being wrong.
- `blocked` can mean login wall, captcha, or missing permissions.
- H vaults are 1Password-based and cloud-browser only; local browser runs rely on local cookies/logins.
- Hosted model mode can send task text, visual observations, and action history to H Company.

### Codex Constraints

- Codex needs MCP config before it can call Cloud CUA.
- GUI-launched hosts may not inherit shell environment variables.
- MCP is a tool bridge, not a user interface.
- Codex should not be trusted as the sole verifier.

### Cloud Constraints

- AWS/GCP resources can cost money.
- Cloud console state can lag.
- Audit logs can lag.
- Verifier commands need permissions.
- CloudWatch/Cloud Logging usage can cost money beyond free tiers.
- User approval is required before creating paid, broad-permission, destructive, or public-network resources.

## Build Plan

### Spike 0: Prove Codex Can Call H

Goal:

```text
Codex can call H and make H navigate to AWS without changing anything.
```

Steps:

1. Install H CLI/HoloDesktop.
2. Log into H.
3. Register HoloDesktop MCP with Codex.
4. Ask Codex to call H for a safe task:

```text
Open Chrome and navigate to https://console.aws.amazon.com. Stop when the AWS sign-in page or console home is visible. Do not create, edit, or delete anything.
```

Pass condition:

- H opens or focuses the browser.
- H reaches AWS sign-in or console home.
- Codex receives a readable result.

### MVP 1: Local Control Loop

Build:

- CLI launcher;
- MCP server;
- local dashboard;
- blocking login modal;
- event log;
- H CUA inspect-only task;
- independent verifier runner.

No real deployment yet.

### MVP 2: First Real Deployment

Support one narrow path first:

- GCP Cloud Run for containerized apps, or
- AWS Amplify for simple frontend apps, or
- AWS ECS Express Mode for containerized web apps.

Required result:

- live URL;
- verifier output;
- deployment report;
- no hidden console-only state.

### MVP 3: Modes And Voice

Add:

- Vibe Mode defaults;
- Teach Mode explanations;
- Expert Mode tradeoff questions;
- Gradium STT/TTS.

### Target State

The mature product should let a user say from Codex:

```text
Deploy this repo to AWS with Cloud CUA in Teach mode.
```

Then Cloud CUA should:

1. inspect the repo;
2. open the dashboard;
3. require manual cloud login;
4. operate the cloud console with H CUA;
5. let Codex object or revise when repo/cloud evidence conflicts;
6. ask the user for approvals;
7. verify the deployment independently;
8. write a clear report and any durable config back to the repo.

## Sources Checked

- H Computer-Use Agents introduction: https://hub.hcompany.ai/computer-use-agents/introduction
- H local browser control: https://hub.hcompany.ai/computer-use-agents/browser/local-control
- H browser configuration: https://hub.hcompany.ai/computer-use-agents/browser/configuration
- H observe and steer: https://hub.hcompany.ai/computer-use-agents/observe-and-steer
- H custom tools: https://hub.hcompany.ai/computer-use-agents/custom-tools
- H vaults: https://hub.hcompany.ai/computer-use-agents/vaults/overview
- HoloDesktop MCP: https://hub.hcompany.ai/holo-desktop-cli/integrations/use-mcp
- HoloDesktop security and privacy: https://hub.hcompany.ai/holo-desktop-cli/security-and-privacy
- HoloTab: https://hcompany.ai/holotab
- Codex MCP: https://developers.openai.com/codex/mcp
- Codex config basics: https://developers.openai.com/codex/config-basic
- Codex IDE: https://developers.openai.com/codex/ide
- AWS CloudTrail Event history: https://docs.aws.amazon.com/awscloudtrail/latest/userguide/view-cloudtrail-events.html
- AWS CloudTrail pricing: https://aws.amazon.com/cloudtrail/pricing
- AWS STS get-caller-identity: https://docs.aws.amazon.com/cli/latest/reference/sts/get-caller-identity.html
- AWS Resource Explorer pricing: https://aws.amazon.com/resourceexplorer/pricing
- GCP Cloud Audit Logs: https://docs.cloud.google.com/logging/docs/audit
- GCP Cloud Run describe command: https://docs.cloud.google.com/sdk/gcloud/reference/run/services/describe
- Gradium API reference: https://docs.gradium.ai/api-reference/introduction
