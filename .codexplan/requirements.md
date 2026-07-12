# Requirements Document: Cloud CUA

## Introduction

Cloud CUA is a local deployment assistant for developers who have finished building an app and want to deploy it to AWS or GCP from their coding environment.

The product starts from the moment a developer says something like:

```text
Deploy this repo with Cloud CUA in Vibe mode.
```

Cloud CUA connects Codex, H Company CUA, and independent cloud verifiers:

- Codex understands the repo, system design constraints, user requests, and code changes.
- H Company CUA operates the logged-in AWS/GCP browser session.
- Cloud CUA owns the run state, dashboard, approvals, mode switching, logs, and verification.
- Independent verifier commands prove what happened without trusting the CUA's final answer.

This is one product with three surfaces:

- MCP server for Codex and other coding agents.
- Local dashboard for the human user.
- CLI for installation, startup, credentials, and MCP registration.

The product now supports generalized AWS deployment planning across Amplify, S3 static hosting, ECS Express Mode, Lambda, and IaC discovery. App Runner is treated as blocked/deprecated for new AWS accounts. GCP Cloud Run has a real approval-gated plan and verifier path, but still requires `gcloud` auth and manual GCP browser login.

## Non-Negotiable Rules

1. **CUA is the visible cloud operator.** H Company CUA must operate the cloud console as a main product feature, not as a hidden afterthought.
2. **Manual login is required.** Cloud CUA must not attempt to solve AWS/GCP login, captcha, MFA, SSO, or password-manager prompts.
3. **Verification is independent of CUA.** H CUA's own final answer is never treated as proof.
4. **Secrets are stored outside the repo by default.** The H API key is saved per machine, not in the project repo.
5. **Mode switching is live.** The user can switch between Vibe, Teach, and Expert mode from the dashboard during a run.
6. **NVIDIA NemoClaw is out of scope.** The product will not use NemoClaw.

## Glossary

- **Cloud_CUA_System**: The full local deployment assistant.
- **MCP_Server**: The local MCP server that exposes Cloud CUA tools to Codex and other coding agents.
- **Local_Dashboard**: The local web UI, served from the user's machine, used for status, approvals, mode switching, logs, and voice.
- **CLI_Launcher**: The `cloud-cua` command used to initialize credentials, start the local service, and run the MCP server.
- **Repo_Context**: Framework, build commands, env vars, ports, deploy target, existing config, and git state inferred from the user's repo.
- **Dedicated_Browser_Profile**: The Chrome profile used only for Cloud CUA cloud-console work.
- **Login_Modal**: The blocking dashboard modal that tells the user to log into AWS/GCP manually.
- **H_CUA_Run**: A bounded H Company computer-use session that operates the browser or desktop.
- **Run_Event_Log**: The append-only `.cloud-cua/runs/<run-id>/events.jsonl` file recording every plan, command, observation, objection, approval, mode change, voice command, result, and error.
- **Verifier_Stack**: The non-CUA checks: git/build checks, AWS/GCP CLI/API checks, audit logs, HTTP checks, Playwright render checks, and final report checks.
- **Voice_Command_Router**: The local classifier that receives Gradium STT text or typed commands and decides whether to execute a direct backend action, ask Codex, create an approval-gated cloud plan, or ask for clarification.
- **Vibe_Mode**: The lowest-friction mode for users who just want the deployment to work.
- **Teach_Mode**: The mode that explains cloud steps in simple language and supports voice questions through Gradium.
- **Expert_Mode**: The mode that asks real infrastructure tradeoff questions and exposes config details.
- **Deployment_Report**: The final repo-written report describing what was deployed, how it was verified, resources created, risks, and next steps.

## Requirements

### Requirement 1: Product Entry From Coding Environment

**User Story:** As a developer who just finished building an app, I want to call Cloud CUA from Codex or my coding environment, so that deployment starts without leaving my repo workflow.

#### Acceptance Criteria

1. WHEN Codex calls the MCP_Server with a repo path, THE Cloud_CUA_System SHALL create a new deployment run for that repo.
2. WHEN a run starts, THE Cloud_CUA_System SHALL open or provide a link to the Local_Dashboard for that run.
3. THE MCP_Server SHALL expose explicit tools for starting a deployment, reading status, reading events, setting mode, pausing/resuming H CUA, requesting approval, running verifiers, and writing the report.
4. THE Cloud_CUA_System SHALL support Codex IDE/desktop/CLI as callers through MCP without requiring the user to understand Codex CLI.
5. IF the MCP_Server is called without a valid repo path, THEN THE Cloud_CUA_System SHALL reject the request with a clear error and SHALL NOT start H CUA.

### Requirement 2: CLI Setup and Startup

**User Story:** As a user, I want one simple local command to set up and start Cloud CUA, so that I do not manually wire the backend, dashboard, and MCP server.

#### Acceptance Criteria

1. THE CLI_Launcher SHALL provide `cloud-cua init`, `cloud-cua start`, and `cloud-cua mcp`.
2. WHEN `cloud-cua init` runs, THE CLI_Launcher SHALL create the user config directory if missing.
3. WHEN `cloud-cua init` runs, THE CLI_Launcher SHALL collect or validate `HAI_API_KEY` and optional `GRADIUM_API_KEY`.
4. WHEN `cloud-cua start` runs, THE CLI_Launcher SHALL start the local backend and Local_Dashboard.
5. WHEN `cloud-cua mcp` runs, THE CLI_Launcher SHALL expose the MCP_Server over stdio.
6. IF a required local dependency is missing, THEN THE CLI_Launcher SHALL display the missing dependency and the exact next command or action.

### Requirement 3: API Key Handling

**User Story:** As a user, I want to enter my H Company API key once per machine, so that I am not asked every deployment and I do not accidentally commit secrets.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL use `HAI_API_KEY` as the H Company API key name.
2. THE Cloud_CUA_System SHALL store the key by default in `~/.cloud-cua/credentials.env`.
3. ON Windows, THE Cloud_CUA_System SHALL support `C:\Users\<user>\.cloud-cua\credentials.env`.
4. THE Cloud_CUA_System SHALL ask for the H key only when it is missing, invalid, changed by the user, or running on a new machine.
5. THE Cloud_CUA_System SHALL NOT store secrets in the target repo by default.
6. IF project-local credentials are supported, THEN THE Cloud_CUA_System SHALL store them only under `.cloud-cua/.env.local` and SHALL add that path to `.gitignore`.
7. THE MCP_Server SHALL NOT bypass the H key requirement; it SHALL call the local backend, which loads credentials from the configured local credential store.

### Requirement 4: Dedicated Browser and Manual Cloud Login

**User Story:** As a user, I want to log into AWS/GCP myself and then let H CUA continue, so that the agent does not fight MFA, captcha, SSO, or password prompts.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL create or attach to a Dedicated_Browser_Profile for cloud-console work.
2. THE Cloud_CUA_System SHALL open the cloud console URL in that dedicated profile.
3. BEFORE starting H CUA, THE Local_Dashboard SHALL show a blocking Login_Modal.
4. FOR AWS, THE Login_Modal SHALL display the exact copy: `Log into AWS in this browser window. Click Continue when done.`
5. FOR GCP, THE Login_Modal SHALL display the exact copy: `Log into GCP in this browser window. Click Continue when done.`
6. THE Login_Modal SHALL blur or dim the rest of the Local_Dashboard until the user clicks Continue.
7. THE Cloud_CUA_System SHALL NOT ask H CUA to solve captcha, MFA, SSO, or password-manager prompts.
8. AFTER the user clicks Continue, THE Cloud_CUA_System SHALL start the H_CUA_Run against the same browser session.

### Requirement 5: Repo Analysis

**User Story:** As a developer, I want Cloud CUA to understand my repo before opening cloud consoles, so that it chooses the right deployment path and avoids random clicking.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL inspect package files, framework markers, build scripts, start scripts, Dockerfile presence, env examples, ports, and git state.
2. THE Cloud_CUA_System SHALL classify the repo into at least one deployment category: frontend/static, Next.js/full-stack frontend, containerized web app, API service, or unknown.
3. THE Cloud_CUA_System SHALL produce a Repo_Context object before any paid cloud resource creation.
4. IF the repo category is unknown, THEN THE Cloud_CUA_System SHALL ask the user or Codex for clarification before creating cloud resources.
5. THE Cloud_CUA_System SHALL write a repo-analysis event into the Run_Event_Log.

### Requirement 6: Deployment Target Selection

**User Story:** As a user, I want Cloud CUA to recommend a deployment target, so that I do not need to know AWS/GCP service names.

#### Acceptance Criteria

1. FOR frontend-style repos, THE Cloud_CUA_System SHALL support AWS Amplify planning and approval-gated H CUA tasks.
2. FOR static frontend repos, THE Cloud_CUA_System SHALL support S3 static hosting as a low-cost AWS target with cleanup and verifier support.
3. FOR containerized/API repos with a Dockerfile, THE Cloud_CUA_System SHALL recommend AWS ECS Express Mode first, prepare an ECR image when possible, and SHALL NOT recommend AWS App Runner for new AWS accounts.
4. FOR GCP, THE Cloud_CUA_System SHALL support Cloud Run planning, approval gating, and `gcloud run services list` verification.
5. WHEN the repo does not fit an implemented target, THE Cloud_CUA_System SHALL stop before cloud changes and report the unsupported reason.
6. THE Cloud_CUA_System SHALL NOT pretend to support a target that has no verifier implementation.

### Requirement 7: H CUA Task Boundaries

**User Story:** As a user, I want H CUA to do bounded cloud-console actions, so that I can trust and debug what it is doing.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL send H CUA short, specific tasks with success criteria.
2. THE Cloud_CUA_System SHALL NOT send H CUA vague tasks like `Deploy this app`.
3. THE Cloud_CUA_System SHALL log every H CUA task request and result in the Run_Event_Log.
4. THE Cloud_CUA_System SHALL allow the user or Codex to pause H CUA from the dashboard or MCP.
5. IF H CUA reports `blocked`, `failed`, `timed_out`, or ambiguous success, THEN THE Cloud_CUA_System SHALL stop the workflow and run independent verification before proceeding.

### Requirement 8: Codex and H CUA Coordination

**User Story:** As a developer, I want Codex and H CUA to work together, so that repo reasoning and visual cloud operation can correct each other.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL be the coordinator between Codex and H CUA.
2. THE Cloud_CUA_System SHALL store all coordination in the Run_Event_Log.
3. Codex SHALL be able to submit plans, objections, verifier requests, and repo-change recommendations through MCP.
4. H CUA observations SHALL be recorded as evidence, not hidden chat.
5. WHEN Codex disagrees with H CUA's observation or proposed next step, THE Cloud_CUA_System SHALL record an `objection` event with evidence.
6. THE Cloud_CUA_System SHALL require user approval before continuing past unresolved objections that affect cost, security, public exposure, or destructive changes.

### Requirement 9: Live Mode Switching

**User Story:** As a user, I want to switch between Vibe, Teach, and Expert mode during deployment, so that the assistant adapts to how much I care at that moment.

#### Acceptance Criteria

1. THE Local_Dashboard SHALL show a visible mode control with `[ Vibe ] [ Teach ] [ Expert ]`.
2. WHEN the user clicks a mode, THE Cloud_CUA_System SHALL update the current run mode immediately.
3. WHEN the mode changes, THE Cloud_CUA_System SHALL write a `mode_changed` event with the old and new mode.
4. WHEN the mode changes, THE MCP_Server SHALL expose the new mode through status/events so Codex sees it.
5. WHEN the mode changes, THE next H CUA task or steering message SHALL include the new behavior policy.
6. THE Cloud_CUA_System SHALL keep the same deployment run alive unless the current step is unsafe to continue.

### Requirement 10: Vibe Mode

**User Story:** As a vibe coder, I want Cloud CUA to make safe default decisions and only interrupt me when needed, so that deployment feels like a deploy button.

#### Acceptance Criteria

1. IN Vibe_Mode, THE Cloud_CUA_System SHALL ask the fewest questions possible.
2. IN Vibe_Mode, THE Cloud_CUA_System SHALL choose the simplest safe supported deployment path.
3. IN Vibe_Mode, THE Cloud_CUA_System SHALL pause for paid resources, destructive actions, broad permissions, public exposure, missing secrets, or login.
4. IN Vibe_Mode, THE Cloud_CUA_System SHALL summarize major risks and final results without long teaching explanations.

### Requirement 11: Teach Mode With Gradium

**User Story:** As a learner, I want Cloud CUA to explain what is happening and answer voice questions, so that I understand AWS/GCP while deploying.

#### Acceptance Criteria

1. IN Teach_Mode, THE Cloud_CUA_System SHALL explain each major cloud step in simple language.
2. IN Teach_Mode, THE Cloud_CUA_System SHALL support Gradium STT for voice questions when `GRADIUM_API_KEY` is configured.
3. IN Teach_Mode, THE Cloud_CUA_System SHALL support Gradium TTS for spoken explanations when `GRADIUM_API_KEY` is configured.
4. IF Gradium is not configured, THEN Teach_Mode SHALL continue with text-only explanations.
5. IN Teach_Mode, THE Cloud_CUA_System SHALL pause before explaining important concepts including IAM, env vars, domain, SSL, region, cost, and logs.
6. THE Cloud_CUA_System SHALL NOT route every STT result through Codex or H CUA.
7. THE Cloud_CUA_System SHALL send STT output first to a local Voice_Command_Router.

### Requirement 11A: Voice Command Router

**User Story:** As a user, I want simple voice controls to happen quickly, so that commands like pause or switch mode do not wait for Codex or H CUA.

#### Acceptance Criteria

1. WHEN Gradium STT returns text, THE Voice_Command_Router SHALL classify it before sending it to Codex or H CUA.
2. IF the STT text is a direct control command such as pause, continue, stop, switch to Vibe mode, switch to Teach mode, switch to Expert mode, open logs, mute voice, or run verifier, THEN THE Cloud_CUA_System SHALL execute the backend/dashboard action directly.
3. IF the STT text is a reasoning question such as "why this service?", "what is IAM?", "is this cheaper?", or "explain this error", THEN THE Cloud_CUA_System SHALL route it to Codex or the explanation engine.
4. IF the STT text requests a cloud operation, THEN THE Cloud_CUA_System SHALL convert it into a bounded planned action and SHALL require approval when the action affects cost, security, public exposure, secrets, or destructive changes.
5. THE Cloud_CUA_System SHALL never send raw voice text directly to H CUA as an instruction.
6. THE Voice_Command_Router SHALL write a `voice_command` event with the transcript, classification, and selected route.
7. THE Voice_Command_Router SHALL support text fallback so the same command router can process typed user messages.
8. THE Cloud_CUA_System SHOULD target sub-second handling for direct control commands after STT returns text.

### Requirement 12: Expert Mode

**User Story:** As an infra-literate user, I want Cloud CUA to ask real tradeoff questions, so that it does not hide important architecture choices.

#### Acceptance Criteria

1. IN Expert_Mode, THE Cloud_CUA_System SHALL ask tradeoff questions when multiple valid deployment choices exist.
2. IN Expert_Mode, THE Cloud_CUA_System SHALL show concrete options with cost, security, reliability, and operational implications.
3. IN Expert_Mode, THE Cloud_CUA_System SHALL allow the user to override the recommended target or config when supported.
4. IN Expert_Mode, THE Cloud_CUA_System SHALL avoid beginner explanations unless asked.

### Requirement 13: Local Dashboard

**User Story:** As a user, I want a clear local dashboard, so that I can supervise the deployment without reading terminal logs.

#### Acceptance Criteria

1. THE Local_Dashboard SHALL show repo name/path, cloud provider, current mode, current step, H CUA status, verifier status, and final deployed URL when available.
2. THE Local_Dashboard SHALL show the Run_Event_Log in a readable activity feed.
3. THE Local_Dashboard SHALL include pause/resume controls for H CUA.
4. THE Local_Dashboard SHALL include approval prompts for risky actions.
5. THE Local_Dashboard SHALL show verifier results separately from H CUA observations.
6. THE Local_Dashboard SHALL run locally and SHALL NOT require a hosted SaaS account for the MVP.

### Requirement 14: Independent Verifier Stack

**User Story:** As a user, I want proof that deployment worked, so that I am not trusting the CUA's claim.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL verify local repo state with git diff and relevant build/test commands.
2. THE Cloud_CUA_System SHALL verify cloud identity with `aws sts get-caller-identity` for AWS or `gcloud auth list` and `gcloud config get-value project` for GCP.
3. THE Cloud_CUA_System SHALL verify resources with cloud CLI/API `describe/list` commands for the selected target.
4. THE Cloud_CUA_System SHALL verify cloud actions with AWS CloudTrail Event history or GCP Cloud Audit Logs when available.
5. THE Cloud_CUA_System SHALL verify the live app with `curl` or equivalent HTTP checks.
6. THE Cloud_CUA_System SHALL verify visible rendering with Playwright.
7. THE Cloud_CUA_System SHALL NOT treat H CUA's answer as ground truth.
8. THE Cloud_CUA_System SHALL treat Terraform as optional later IaC consistency support, not the primary MVP verifier.

### Requirement 15: Deployment Report

**User Story:** As a developer, I want a report written back into the repo, so that I know what changed and how to reproduce or clean it up.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL write `DEPLOYMENT_REPORT.md` after each completed or stopped deployment run.
2. THE Deployment_Report SHALL include repo summary, cloud provider, target, created/modified resources, approvals, verifier results, live URL, risks, cleanup instructions, and next steps.
3. THE Deployment_Report SHALL include links or references to the run event log.
4. THE Deployment_Report SHALL identify any manual cloud-console state that has no durable repo representation.
5. IF deployment fails or is blocked, THEN THE Deployment_Report SHALL explain the blocking step and the next human action.

### Requirement 16: Safety and Approval Gates

**User Story:** As a user, I want Cloud CUA to ask before expensive or risky changes, so that it does not silently create unsafe infrastructure.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL require approval before creating paid cloud resources.
2. THE Cloud_CUA_System SHALL require approval before broad IAM permissions.
3. THE Cloud_CUA_System SHALL require approval before public network exposure.
4. THE Cloud_CUA_System SHALL require approval before deleting or replacing cloud resources.
5. THE Cloud_CUA_System SHALL require approval before sharing secrets with any cloud service.
6. THE approval record SHALL be written to the Run_Event_Log.

### Requirement 17: AWS Deployment Paths

**User Story:** As a developer, I want Cloud CUA to choose a reasonable AWS deployment path for my repo, so that the product is not limited to one Amplify demo.

#### Acceptance Criteria

1. WHEN the repo is classified as frontend-style and AWS is selected, THE Cloud_CUA_System SHALL recommend AWS Amplify or S3 static hosting according to repo fit and user intent.
2. THE Cloud_CUA_System SHALL guide H CUA through AWS Amplify console setup after manual login.
3. THE Cloud_CUA_System SHALL pause for GitHub OAuth or account-linking approval when required.
4. THE Cloud_CUA_System SHALL collect required build command, output directory, branch, and environment variables from Repo_Context or user approval.
5. THE Cloud_CUA_System SHALL tag new resources with `cloud-cua=true`, `cloud-cua-repo`, and `cloud-cua-run` whenever the cloud console exposes tags.
6. THE Cloud_CUA_System SHALL verify AWS identity, selected service resources, tagged resources, and live URLs with independent CLI/HTTP/Playwright checks where possible.

### Requirement 18: Out-of-Scope Deployment Targets

**User Story:** As a user, I want unsupported targets to be clearly identified, so that Cloud CUA does not overpromise.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL identify App Runner as blocked/deprecated for new AWS accounts and SHALL steer containerized web apps toward ECS Express Mode.
2. THE Cloud_CUA_System SHALL identify GCP Cloud Run as implemented for planning and verification, but blocked until local `gcloud` auth and manual browser login are available.
3. THE Cloud_CUA_System SHALL identify databases, queues, domains, and production networking as planned advanced scope unless implemented with verifiers.
4. THE Cloud_CUA_System SHALL stop and report unsupported scope rather than improvising unverified deployment paths.

### Requirement 19: Persistence and Replay

**User Story:** As a developer, I want every deployment run to be replayable, so that I can debug or continue later.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL store each run under `.cloud-cua/runs/<run-id>/`.
2. THE Cloud_CUA_System SHALL write `events.jsonl` for each run.
3. THE Cloud_CUA_System SHALL write verifier artifacts under the run directory.
4. THE Cloud_CUA_System SHALL avoid writing secrets to the run directory.
5. IF local artifacts may contain sensitive screenshots or logs, THEN THE Cloud_CUA_System SHALL warn before sharing them.

### Requirement 20: MVP Success Criteria

**User Story:** As the builder, I want objective MVP pass/fail criteria, so that we know when the first version is real.

#### Acceptance Criteria

1. THE MVP SHALL allow Codex to start a Cloud CUA run through MCP.
2. THE MVP SHALL open the Local_Dashboard.
3. THE MVP SHALL show the blocking Login_Modal.
4. THE MVP SHALL start an H CUA inspect-only browser task after manual login.
5. THE MVP SHALL record Codex, H CUA, user, and verifier events in `events.jsonl`.
6. THE MVP SHALL run at least identity, HTTP, Playwright, and report verifiers.
7. THE MVP SHALL support live mode switching.
8. THE first deployment MVP SHALL run at least one low-cost real AWS deployment smoke, verify it independently, and clean it up.
9. THE H-driven cloud-console deployment MVP SHALL remain blocked until the H-controlled browser profile is manually logged into the target cloud account.

### Requirement 21: Skills, Contracts, and Safe Learning

**User Story:** As a developer, I want H CUA to gain bounded autonomy from reusable deployment skills while independent checks prevent repeated mistakes.

#### Acceptance Criteria

1. THE Cloud_CUA_System SHALL store reviewed deployment skills as local YAML and synchronize them to the user's H skill catalog.
2. BEFORE a skilled H deployment session, THE Cloud_CUA_System SHALL create or update the active H skill and attach its name to the H agent.
3. IF H skill synchronization fails, THEN THE Cloud_CUA_System SHALL block the H deployment session.
4. THE Cloud_CUA_System SHALL save a per-run `contract.json` containing the exact image, port, region, tags, health path, skill hash, and autonomy level available for the target.
5. FOR ECS Express, H CUA SHALL inspect the creation form without mutation before receiving the approved creation milestone.
6. IF H's structured inspection conflicts with the contract, THEN Codex/backend SHALL record an objection and SHALL NOT send the creation milestone.
7. THE Run_Event_Log SHALL record H trajectory events incrementally while the H session runs.
8. THE ECS verifier SHALL independently compare the exact run-tagged service's task-definition image and port to `contract.json`, require healthy targets, and verify a real non-console application URL.
9. ON a milestone or verifier failure, THE Cloud_CUA_System SHALL write `lesson_candidate.json` with failure evidence, a proposed general rule, and a required test.
10. THE Cloud_CUA_System SHALL NOT automatically promote lesson candidates into trusted skills.
11. THE Local_Dashboard SHALL show the active skill, H sync state, autonomy level, contract facts, missing facts, verifier gates, and pending lesson.
