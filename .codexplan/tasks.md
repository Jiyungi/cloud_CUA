# Implementation Plan: Cloud CUA

## Overview

This plan builds Cloud CUA as a local-first deployment assistant with:

- a CLI launcher;
- an MCP server for Codex and other coding agents;
- a local dashboard for the user;
- H Company CUA integration for browser/cloud-console operation;
- independent verifiers that prove deployment state without trusting CUA;
- live Vibe/Teach/Expert mode switching;
- AWS Amplify/S3 for frontend repos and ECS Express Mode for Docker/container repos.

The work is ordered so the core risk is tested first: can Codex call Cloud CUA, and can Cloud CUA delegate bounded browser work to H CUA after manual login?

## Owners

Owner labels are suggested for parallel work.

- **Agent/Backend**: CLI, MCP, backend API, run store, H runner, verifiers.
- **Frontend/Product**: dashboard, login modal, mode controls, approvals, activity feed, voice UI.
- **Cloud/Verification**: AWS target adapters, ECR/ECS checks, AWS/GCP CLI checks, Playwright checks, report output.
- **Both**: spike validation, integration tests, final demo path.

## Tasks

- [x] 1. Create the project skeleton (Owner: Agent/Backend)
  - [x] 1.1 Create Python package structure
    - Add `cloud_cua/` package with `cli.py`, `server.py`, `mcp_server.py`, `credentials.py`, `repo_analyzer.py`, `run_store.py`, `mode_policy.py`, `browser_profile.py`, `h_runner.py`, `reports.py`
    - Add `cloud_cua/verifier/` and `cloud_cua/deployments/`
    - Add `tests/`
    - _Requirements: 1, 2, 19_

  - [x] 1.2 Add dependency and run configuration
    - Add project metadata for CLI entrypoint `cloud-cua`
    - Add dependencies for FastAPI, MCP server support, H SDK/CLI integration, dotenv parsing, pytest, Playwright test support
    - Add a dev README section for local commands
    - _Requirements: 2, 20_

- [ ] 2. Implement credential setup (Owner: Agent/Backend)
  - [x] 2.1 Implement credential paths and file loading
    - Read/write `~/.cloud-cua/credentials.env`
    - Support Windows path expansion
    - Load `HAI_API_KEY` and optional `GRADIUM_API_KEY`
    - Never write credentials into the repo
    - _Requirements: 3_

  - [ ] 2.2 Implement `cloud-cua init`
    - Create config directory
    - Prompt for missing `HAI_API_KEY`
    - Save credentials
    - Validate basic shape without printing the secret
    - Status: saves credentials today, but key-shape validation still needs to be added.
    - _Requirements: 2, 3_

  - [ ]* 2.3 Test credential behavior
    - Missing key prompts setup
    - Existing key is reused
    - Key is never written under repo path
    - _Requirements: 3_

- [x] 3. Implement the run store and event log (Owner: Agent/Backend)
  - [x] 3.1 Implement run directory creation
    - Create `.cloud-cua/runs/<run-id>/`
    - Create `run.json`
    - Create `events.jsonl`
    - _Requirements: 8, 19_

  - [x] 3.2 Implement append-only event writer
    - Enforce source/type fields
    - Strip or reject known secret fields
    - Write JSONL events
    - _Requirements: 8, 9, 16, 19_

  - [x]* 3.3 Test event log safety
    - Events append in order
    - `mode_changed` events store old/new mode
    - Secret-like values are not persisted
    - _Requirements: 8, 9, 19_

- [x] 4. Implement CLI and backend startup (Owner: Agent/Backend)
  - [x] 4.1 Implement `cloud-cua start`
    - Start FastAPI backend
    - Serve or link to local dashboard
    - Print dashboard URL
    - _Requirements: 2, 13_

  - [x] 4.2 Implement health/status endpoints
    - `/health`
    - `/runs/{run_id}`
    - `/runs/{run_id}/events`
    - _Requirements: 1, 13, 19_

  - [x]* 4.3 Test backend startup and run status
    - Health endpoint works
    - Run status returns current mode/status/current step
    - Events endpoint returns latest events
    - _Requirements: 1, 13_

- [x] 5. Implement MCP server (Owner: Agent/Backend)
  - [x] 5.1 Implement `cloud-cua mcp`
    - Run MCP server over stdio
    - Connect tools to local backend or in-process orchestrator
    - _Requirements: 1, 2_

  - [x] 5.2 Add minimum MCP tools
    - `cloud_cua_start_deployment`
    - `cloud_cua_open_dashboard`
    - `cloud_cua_get_status`
    - `cloud_cua_get_recent_events`
    - `cloud_cua_set_mode`
    - `cloud_cua_send_user_message`
    - `cloud_cua_submit_codex_plan`
    - `cloud_cua_submit_objection`
    - `cloud_cua_pause_h_cua`
    - `cloud_cua_resume_h_cua`
    - `cloud_cua_request_approval`
    - `cloud_cua_run_verifier`
    - `cloud_cua_write_report`
    - _Requirements: 1, 8, 9, 14, 15_

  - [x]* 5.3 Test MCP tool calls
    - Start deployment creates a run
    - Set mode writes `mode_changed`
    - Get events returns structured events
    - _Requirements: 1, 8, 9_

- [ ] 6. Spike: prove Codex can call H safely (Owner: Both)
  - [x] 6.1 Install and validate H tooling
    - Install H CLI/HoloDesktop or H SDK path chosen for local control
    - Run a tiny safe local task outside AWS
    - Confirm hosted/local model config is available
    - _Requirements: 20_

  - [ ] 6.2 Register H tool path with Codex or call through Cloud CUA
    - Confirm Codex can call Cloud CUA MCP
    - Confirm Cloud CUA can ask H to open/focus a browser
    - _Requirements: 1, 7, 20_

  - [ ] 6.3 Run safe AWS navigation task
    - Task: open `https://console.aws.amazon.com`
    - Success: AWS sign-in page or console home is visible
    - Constraint: do not create/edit/delete anything
    - _Requirements: 4, 7, 20_

  - [ ] 6.4 Record spike result
    - Write result into `DEPLOYMENT_REPORT.md` or a spike report
    - Note whether H local browser or HoloDesktop MCP is the better path
    - _Requirements: 15, 20_

- [x] 7. Implement dedicated browser profile and login modal backend (Owner: Agent/Backend)
  - [x] 7.1 Implement browser profile manager
    - Create `~/.cloud-cua/chrome-profile`
    - Launch Chrome or detect H SDK-managed Chrome
    - Open AWS/GCP console URL
    - _Requirements: 4_

  - [x] 7.2 Implement login-gated run state
    - Set run status to `waiting_for_login`
    - Do not start H CUA until user clicks Continue
    - After Continue, run identity verifier before modification tasks
    - _Requirements: 4, 14_

  - [x]* 7.3 Test login gating
    - H task cannot start before Continue
    - Continue changes status
    - Failed identity verifier blocks modification
    - _Requirements: 4, 14_

- [ ] 8. Build local dashboard shell (Owner: Frontend/Product)
  - [x] 8.1 Create dashboard app
    - Local page at `http://localhost:3000` or backend-served equivalent
    - Run list/detail page
    - Current run status
    - _Requirements: 13_

  - [ ] 8.2 Build required run panels
    - Repo summary
    - Cloud/provider target
    - Current step
    - H CUA status
    - Verifier status
    - Activity feed
    - Final URL/report
    - _Requirements: 13, 15_

  - [x] 8.3 Build blocking login modal
    - AWS copy exactly: `Log into AWS in this browser window. Click Continue when done.`
    - GCP copy exactly: `Log into GCP in this browser window. Click Continue when done.`
    - Blur/dim dashboard while modal is active
    - Continue and Cancel actions
    - _Requirements: 4, 13_

  - [x]* 8.4 Test dashboard modal behavior
    - Modal blocks controls behind it
    - Exact copy renders
    - Continue calls backend
    - _Requirements: 4, 13_

- [x] 9. Implement live mode switching (Owner: Frontend/Product)
  - [x] 9.1 Build mode control
    - Render `[ Vibe ] [ Teach ] [ Expert ]`
    - Highlight active mode
    - Call backend/MCP equivalent on click
    - _Requirements: 9_

  - [x] 9.2 Implement mode policy backend
    - Store mode in run state
    - Write `mode_changed` event
    - Adjust next H CUA task instructions based on mode
    - _Requirements: 9, 10, 11, 12_

  - [x]* 9.3 Test mode switching
    - Vibe to Teach writes event
    - Status reflects new mode
    - Run stays alive
    - _Requirements: 9_

- [x] 10. Implement repo analyzer (Owner: Agent/Backend)
  - [x] 10.1 Build deterministic repo scanner
    - Read package/framework markers
    - Detect package manager
    - Detect build/start commands
    - Detect Dockerfile
    - Detect env var names without reading secret values
    - _Requirements: 5_

  - [x] 10.2 Classify deployment category
    - frontend/static
    - Next.js/full-stack frontend
    - containerized web app
    - API service
    - unknown
    - _Requirements: 5, 6_

  - [x] 10.3 Produce deployment recommendation
    - Recommend AWS Amplify only for supported frontend-style repos
    - Recommend ECS Express Mode for Dockerfile repos
    - Treat App Runner as blocked/deprecated for new AWS accounts
    - Mark GCP Cloud Run as planned/approval-gated when GCP is selected
    - _Requirements: 6, 17, 18_

  - [x]* 10.4 Test repo analyzer fixtures
    - Vite app recommends Amplify
    - Dockerfile app is planned ECS scope
    - Unknown app blocks before cloud work
    - _Requirements: 5, 6, 18_

- [ ] 11. Implement H CUA runner (Owner: Agent/Backend)
  - [ ] 11.1 Implement inspect-only H task runner
    - Accept bounded task payload
    - Include success criteria
    - Log command/result
    - Respect pause state
    - _Requirements: 7, 8_

  - [ ] 11.2 Implement H result handling
    - Handle completed, blocked, failed, timed_out, ambiguous
    - Stop workflow on blocked/ambiguous modification steps
    - Trigger verifier where useful
    - _Requirements: 7, 14_

  - [ ]* 11.3 Test H runner with fake adapter
    - Bounded task logged
    - Blocked result sets run blocked
    - Pause prevents next task
    - _Requirements: 7, 8_

- [ ] 12. Implement independent verifiers (Owner: Cloud/Verification)
  - [ ] 12.1 Implement repo verifier
    - Git diff summary
    - Optional build/test command hooks
    - _Requirements: 14_

  - [x] 12.2 Implement AWS identity verifier
    - Run `aws sts get-caller-identity`
    - Store sanitized output
    - _Requirements: 14_

  - [ ] 12.3 Implement AWS action/resource verifiers
    - CloudTrail lookup wrapper
    - Amplify list/get wrapper
    - Result parser
    - _Requirements: 14, 17_

  - [x] 12.4 Implement HTTP and Playwright verifiers
    - `curl`/fetch status check
    - Playwright page render check
    - _Requirements: 14, 17_

  - [x] 12.5 Implement GCP verifier basics
    - `gcloud auth list`
    - `gcloud config get-value project`
    - `gcloud run services list`
    - Skip cleanly when `gcloud` is not installed
    - _Requirements: 14, 18_

  - [x]* 12.6 Test verifier result schema
    - passed/failed/skipped statuses
    - raw artifact path
    - no secret leakage
    - _Requirements: 14, 19_

- [x] 13. Implement approval gates (Owner: Frontend/Product)
  - [x] 13.1 Build approval model and backend endpoints
    - Pending approval object
    - Approve/deny actions
    - Event log records decision
    - _Requirements: 16_

  - [x] 13.2 Build dashboard approval panel
    - Show action, reason, risk level
    - Approve and Deny buttons
    - _Requirements: 13, 16_

  - [x] 13.3 Add required approval triggers
    - paid resources
    - broad IAM
    - public exposure
    - delete/replace
    - secret sharing
    - GitHub OAuth/account linking
    - _Requirements: 16, 17_

  - [x]* 13.4 Test approval gates
    - Modification task waits for approval
    - Deny stops the step
    - Approval event is written
    - _Requirements: 16_

- [ ] 14. Implement AWS frontend adapter through the generalized AWS runner (Owner: Cloud/Verification)
  - [x] 14.1 Build Amplify deployment plan generator
    - App name
    - Branch
    - Build command
    - Output directory
    - Env var names and missing values
    - _Requirements: 6, 17_

  - [ ] 14.2 Build Amplify inspect tasks for H CUA
    - Check if AWS console is logged in
    - Check if Amplify page is reachable
    - Check if GitHub connection is required
    - Do not modify during inspect tasks
    - _Requirements: 7, 17_

  - [ ] 14.3 Build Amplify modifying tasks for H CUA
    - Only after approval
    - Use short task steps
    - Stop on OAuth/permission prompts
    - _Requirements: 7, 16, 17_

  - [ ] 14.4 Wire Amplify verifiers
    - AWS identity
    - Amplify app/branch
    - CloudTrail actions
    - live URL
    - Playwright render
    - _Requirements: 14, 17_

  - [ ]* 14.5 Test adapter with mocked H/AWS
    - Supported repo builds plan
    - OAuth prompt creates approval/block event
    - Verifier result gates completion
    - _Requirements: 17_

- [x] 15. Implement report writer (Owner: Cloud/Verification)
  - [x] 15.1 Generate `DEPLOYMENT_REPORT.md`
    - Repo summary
    - Cloud provider and target
    - Resources created/modified
    - Approvals
    - Verifier results
    - Live URL
    - Risks
    - Cleanup
    - Next steps
    - _Requirements: 15_

  - [x] 15.2 Write blocked/failed report path
    - Blocking step
    - Evidence
    - Next human action
    - _Requirements: 15_

  - [x]* 15.3 Test report contents
    - Completed report has required sections
    - Failed report has blocking step
    - Report links event log
    - _Requirements: 15_

- [ ] 16. Implement Teach Mode voice with Gradium and fast command routing (Owner: Frontend/Product)
  - [x] 16.1 Build voice UI
    - Voice button in dashboard
    - Text transcript fallback
    - Voice disabled state when no key
    - _Requirements: 11, 11A, 13_

  - [ ] 16.2 Implement Voice Command Router
    - Classify STT or typed text before Codex/H CUA sees it
    - Route direct controls to backend actions immediately
    - Route reasoning questions to Codex or the explanation engine
    - Route cloud-operation requests into planned actions and approval gates
    - Never send raw voice text directly to H CUA
    - Write `voice_command` events with transcript, classification, and route
    - _Requirements: 11, 11A_

  - [x] 16.3 Implement Gradium STT adapter
    - Browser records or streams user audio
    - Backend uses `GRADIUM_API_KEY` or short-lived browser token flow
    - STT result goes to Voice Command Router first
    - API key is never exposed in browser JavaScript
    - Text fallback uses the same router
    - _Requirements: 11, 11A_

  - [x] 16.4 Implement Gradium TTS adapter
    - Speak short Teach Mode explanations, warnings, questions, and final results
    - Do not speak every internal event
    - TTS is output only; it does not choose actions
    - Text fallback on failure
    - _Requirements: 11_

  - [ ]* 16.5 Test voice routing and fallback
    - Missing key disables voice without breaking Teach Mode
    - `pause` routes directly to backend pause
    - `switch to Expert mode` routes directly to mode switch
    - `why this service?` routes to Codex/explanation path
    - `click this in AWS` does not go directly to H CUA
    - STT transcript becomes `voice_command` event
    - _Requirements: 11, 11A_

- [ ] 17. End-to-end local control loop checkpoint (Owner: Both)
  - [ ] 17.1 Run full inspect-only flow
    - Codex/MCP starts run
    - Dashboard opens
    - Login modal blocks
    - User continues
    - H CUA runs inspect-only task
    - Events are written
    - Verifiers can run
    - Report is written
    - _Requirements: 1, 4, 7, 8, 13, 14, 15, 20_

  - [ ] 17.2 Fix gaps found in checkpoint
    - Keep changes scoped
    - Update requirements/design/tasks if product decisions change
    - _Requirements: 20_

- [ ] 18. End-to-end AWS deployment checkpoint (Owner: Both)
  - [ ] 18.1 Prepare sample frontend repo
    - Simple Vite/React or static app
    - Known build command
    - Known output directory
    - _Requirements: 5, 17_

  - [ ] 18.2 Run H CUA AWS console deployment flow
    - Manual login
    - H CUA console operation
    - User approval for resource creation
    - AWS verifiers
    - HTTP verifier
    - Playwright verifier
    - Report
    - _Requirements: 14, 16, 17, 20_

  - [x] 18.3 Run real low-cost AWS smoke deployment
    - Created tagged S3 static website bucket under `cloud-cua-smoke-*`
    - Verified public website endpoint returned the run marker
    - Deleted object, bucket policy, website config, and bucket
    - Confirmed `cloud-cua` cleanup dry-run found zero leftover resources
    - _Requirements: 14, 16, 17, 20_

  - [x] 18.4 Record target-state gaps
    - H CUA console deployment still needs manual login in the H-controlled browser profile
    - ECS Express console creation remains unproven until H CUA completes it in the user's AWS account
    - GCP Cloud Run needs local `gcloud` installation/auth before real deployment
    - What still needs stronger security/cost handling
    - _Requirements: 18, 20_

- [x] 19. Documentation and install instructions (Owner: Both)
  - [x] 19.1 Write README usage flow
    - What Cloud CUA is
    - Install/start commands
    - API key setup
    - How Codex calls MCP
    - Manual AWS login requirement
    - Verifier stack
    - _Requirements: 1, 2, 3, 4, 14_

  - [x] 19.2 Document constraints honestly
    - CUA can fail
    - Login/captcha/MFA manual
    - Frontend uses Amplify/S3; Docker uses ECS Express Mode
    - GCP planned/approval-gated but still depends on local `gcloud` auth
    - App Runner blocked/deprecated for new AWS accounts
    - NemoClaw not used
    - _Requirements: 6, 18_

  - [x] 19.3 Document security handling
    - Secrets outside repo
    - Dedicated browser profile
    - H hosted model privacy note
    - Local artifacts may be sensitive
    - _Requirements: 3, 4, 19_

- [ ] 20. Final MVP validation (Owner: Both)
  - [x] 20.1 Run test suite
    - Unit tests
    - Integration tests
    - Verifier tests
    - _Requirements: 20_

  - [ ] 20.2 Run full dashboard QA
    - Login modal
    - Mode switching
    - Approval gates
    - Pause/resume
    - Activity feed
    - Report link
    - Automated visual smoke for desktop/mobile is implemented, but full dashboard QA is not complete.
    - _Requirements: 4, 9, 13, 16_

  - [ ] 20.3 Confirm MVP pass/fail criteria
    - Codex can start Cloud CUA via MCP
    - Dashboard opens
    - H CUA inspect task works
    - Independent verifiers run
    - Low-cost AWS deployment smoke works and cleans up
    - H CUA AWS console deployment has documented manual-login blocker
    - _Requirements: 20_

- [x] 21. Shareable product hardening (Owner: Both)
  - [x] 21.1 Add `cloud-cua install-mcp`
    - Writes Codex MCP config
    - Backs up existing config before editing
    - _Requirements: 1, 2_

  - [x] 21.2 Add `cloud-cua doctor`
    - Checks Python, Node, npm, AWS CLI, AWS identity, gcloud, Chrome, Chrome debug port, Playwright, Docker, credentials, Codex MCP config
    - _Requirements: 2, 14, 20_

  - [x] 21.3 Add Docker quickstart
    - `Dockerfile`
    - `docker-compose.yml`
    - `.dockerignore`
    - Does not expose H or Gradium keys in rendered Compose config
    - _Requirements: 2, 3_

  - [x] 21.4 Add AWS cleanup command
    - Dry-run by default
    - Deletes only discovered Cloud CUA named/tagged resources when `--yes` is used
    - _Requirements: 16, 17_

  - [x] 21.5 Commit shareable release artifact
    - `dist/cloud-cua-shareable.zip`
    - Excludes `.env`, `.kiro`, `readme files`, local run artifacts, venvs, node_modules, and git metadata
    - _Requirements: 2, 19_

- [ ] 22. ECS Express Mode end-to-end hardening (Owner: Cloud/Verification)
  - [x] 22.1 Make Docker repos prefer ECS Express Mode
    - App Runner is deprecated/blocked for new AWS accounts
    - AWS planner lists App Runner only to explain why it will not be used
    - _Requirements: 6, 17, 18_

  - [x] 22.2 Prepare ECR images before H CUA runs
    - Create a Cloud-CUA-tagged ECR repository
    - Docker build/tag/push the local repo image
    - Pass the exact image URI to H CUA for ECS Express Mode
    - _Requirements: 5, 7, 17_

  - [ ] 22.3 Prove real ECS Express console deployment
    - User logs into AWS manually in the H-controlled browser
    - H CUA creates/updates an ECS Express service from the prepared ECR image
    - Verifier proves the exact service/resource URL for the run
    - _Requirements: 14, 16, 17, 20_

  - [ ] 22.4 Tighten exact-run verification
    - Extract ECS Express service name/cluster/load balancer URL from H final answer or AWS APIs
    - Verify HTTP and Playwright against the exact live URL
    - Write exact resource names into `DEPLOYMENT_REPORT.md`
    - _Requirements: 14, 15, 17_

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "3.1", "4.1", "5.1"] },
    { "id": 2, "tasks": ["2.2", "3.2", "4.2", "5.2", "5.3", "8.1"] },
    { "id": 3, "tasks": ["6.1", "7.1", "8.2", "9.1", "10.1", "12.1"] },
    { "id": 4, "tasks": ["6.2", "6.3", "7.2", "8.3", "9.2", "10.2", "10.3", "11.1", "12.2", "12.3", "12.4", "13.1"] },
    { "id": 5, "tasks": ["11.2", "13.2", "13.3", "14.1", "14.2", "15.1", "16.1"] },
    { "id": 6, "tasks": ["14.3", "14.4", "15.2", "16.2", "16.3", "16.4"] },
    { "id": 7, "tasks": ["16.5", "17.1", "17.2"] },
    { "id": 8, "tasks": ["18.1", "18.2", "18.3"] },
    { "id": 9, "tasks": ["19.1", "19.2", "19.3", "20.1", "20.2", "20.3"] }
  ]
}
```

## Notes

- Tasks marked with `*` are test tasks. They should not be skipped for serious product work, but can be deferred during a short spike.
- Update `requirements.md` before changing product behavior.
- Update `design.md` before changing architecture.
- Update `tasks.md` when implementation scope changes.
- Do not add NemoClaw tasks.
- Current H status: host-local doctor can confirm H credentials/quota and Chrome prerequisites, but the latest full H browser takeover is not proven after local bridge failures. Docker mode intentionally blocks H browser takeover; use host-local `python -m cloud_cua.cli start` for real H CUA work.
- Current visual QA status: `npm run visual:dashboard` passes desktop/mobile/login-modal smoke checks and writes screenshots under `.cloud-cua/visual-checks/`, but this is not a full manual dashboard QA pass.
- Current AWS smoke status: AWS CLI profile `cloud-cua-dev` created a tagged S3 static website, verified its public endpoint, deleted it, and `cloud-cua aws-cleanup` found zero leftover Cloud CUA resources.
