# Cloud CUA Validation Evidence

## Managed Installation And MCP

- Built `cloud_cua-0.1.0-py3-none-any.whl` and included it in `dist/cloud-cua-shareable.zip`.
- Installed wheel plus H browser dependencies in a clean isolated virtual environment.
- Ran the full test suite in that installed environment: 110 tests passed at that checkpoint.
- Started the MCP server from an unrelated directory with `python -I -m cloud_cua.cli mcp`.
- A real MCP client initialized the server, discovered 31 tools, and created run `20260712T090154Z-3e082455` with an exact `repo_path` and `run_id` dashboard URL.
- Installed the user runtime at `~/.cloud-cua/runtime-venv` and configured Codex to use its absolute Python path.

## Real H Browser Identity

- Inspect-only run: `20260712T090559Z-3fc149d7`.
- H session: `eb4421b5-0b99-4740-8b23-2c62aa6e9d2b`.
- H read AWS browser account `575078236462` from the console.
- AWS CLI independently returned account `575078236462` for profile `cloud-cua-dev`.
- Cloud CUA marked the account proof `matched` before allowing modification.

## Real H-Operated S3 Deployment

- Run: `20260712T092622Z-21720232`.
- Target: `aws_s3_static_site`.
- H created and tagged bucket `cloud-cua-aws-smoke-site-622z21720232`.
- Required tags were `cloud-cua=true`, `cloud-cua-repo=aws-smoke-site`, and the exact run ID.
- H configured static website hosting with `index.html` as index and error document.
- Cloud CUA independently verified the tags and website configuration before applying its generated bucket-scoped public-read policy through AWS's structured API.
- Cloud CUA uploaded the staged static artifact after excluding local state and secret files.

All required verifiers passed:

- AWS CLI identity;
- exact run-tagged S3 bucket;
- website configuration and `index.html` object;
- AWS Resource Groups Tagging API;
- CloudTrail `CreateBucket` evidence;
- HTTP 200 at the public website URL;
- managed Python Playwright render with title `Cloud CUA smoke`;
- deployment report existence;
- exact cleanup discovery.

The run ended `completed`. Cleanup then deleted the exact bucket and object. A final Cloud CUA dry run found zero actions, and AWS Resource Groups Tagging API returned no resources for the run tag.

The later global audit also removed a retained ECS task definition and CloudWatch log group missed by the earlier cleanup implementation. AWS's tagging index still returns two older ECS Express service ARNs whose service status is `INACTIVE`; AWS rejects deletion and untagging for inactive services. They are retained service metadata, not running or billable resources, and Cloud CUA correctly reports no executable cleanup action for them.

## Dashboard And Tests

- Development suite: 453 tests passed after asynchronous H control, 150-case AWS conformance expansion, fixture-contract enforcement, runtime-secret, cost-monitor, Docker, and Amplify verifier hardening.
- Browser smoke: 30 checks passed across desktop, mobile, login modal, runtime-secret modal, and cost-action modal.
- Browser checks include JavaScript console errors and horizontal overflow.

## Asynchronous H Controls And Recovery

- Real H run `20260712T105238Z-0ca30198` reached hosted `paused`, returned to `running`, and ended hosted `interrupted` after cancel.
- The local manager polls hosted state before reporting success, retries asynchronous control delivery, prevents duplicate workers, and persists the H session/milestone/heartbeat cursor.
- A backend-restart exercise proved that the local browser bridge cannot be reattached across process death. Cloud CUA now cancels only the exact Cloud CUA H session and bridge and blocks at `h_job_recovery_required` instead of replaying a submit milestone.
- Final H quota audit reported limit 3, active 0, available 3.

## Runtime Secrets And Cost Policy

- Live run `20260712T112604Z-98de613c` provisioned two synthetic values as tagged SSM Standard `SecureString` parameters.
- Plaintext marker scans found zero matches in run files; only SSM ARNs entered the contract. Exact cleanup removed both parameters.
- AWS Price List resolution returned current Fargate vCPU/memory, load balancer, LCU, and ECR prices without fallback values.
- Tests cover 50%, 80%, and 100% cost gates, restart recovery, approved cap extension, and clock freezing after cleanup.

## Docker And Release Artifact

- Docker Compose built and ran on a non-default host port with a mounted target repository and writable named state volume.
- Container doctor passed Python, Node, npm, AWS CLI/identity, Docker, credentials, and Playwright. Host-only Chrome/H bridge checks were explicitly skipped.
- A real MCP handshake inside the container discovered 31 tools and created an exact run/dashboard URL; host Playwright loaded that run without console errors.
- The rebuilt shareable archive contains no `.env`, `.git`, or `.kiro` files.
- Its wheel was installed in a fresh temporary virtual environment outside the repository. Under isolated Python, the MCP handshake discovered 31 tools and package imports passed.

## Amplify Acceptance Status

- Run `20260712T121251Z-41762fb7` reached the real Amplify manual-deploy form and correctly blocked before submit when AWS reported S3 source validation/access errors.
- Cloud CUA now instructs H to use Browse S3 and select the exact contract bucket/object instead of typing an S3 URI; the staged object explicitly uses `bucket-owner-full-control`. Unit tests pass and the revised hosted H skill is synced.
- Fresh run `20260712T122151Z-30d3fb6b` failed closed at browser identity because the dedicated H Chrome profile had logged out. A user must manually log into that dedicated browser once before the final real Amplify create/verify/cleanup smoke can run.

## Explicit Deferred Scope

GCP is not production-ready. `gcloud` is not installed or authenticated on this machine, so Cloud Run remains planning-only until project identity, exact verification, a real deployment, and cleanup are proven.

## Jiyun Evaluation And Fixture Validation

- Imported Jiyun's seven agent-project commits with original authorship and imported the AWS evaluation catalog without replacing newer main tests.
- Executed every one of the 150 AWS service cases with complete evidence and with an unknown-fact failure variant.
- Materialized exactly 53 local skills and verified all 53 hashes are synced in H's hosted skill catalog.
- ReceiptSplit passed 11 unit/component tests, its build, and one Playwright flow.
- InvoiceOps passed 29 unit/component tests, its build, and three Playwright flows.
- Managed MCP runs `20260712T131038Z-6881fd62` and `20260712T131040Z-a48ce9f0` attached to the exact child repositories and blocked frontend-only success because their backends are absent.
- Frontend-only Amplify apps were published and exact tags/branches/jobs, HTTP, and root/deep-link Playwright rendering passed:
  - ReceiptSplit: `https://jiyun-test.dlxrss6fqphr3.amplifyapp.com`
  - InvoiceOps: `https://jiyun-test.d5mex5o827iae.amplifyapp.com`
- The full authenticated AWS fixture workflows remain blocked because backend code/adapters are absent, H's dedicated AWS browser is logged out, and the AWS account has no verified SES sender identity.
