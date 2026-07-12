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

## Dashboard And Tests

- Development suite: 118 tests passed after the S3 and managed Playwright fixes.
- Browser smoke: 28 checks passed across desktop, mobile, login modal, runtime-secret modal, and cost-action modal.
- Browser checks include JavaScript console errors and horizontal overflow.

## Explicit Deferred Scope

GCP is not production-ready. `gcloud` is not installed or authenticated on this machine, so Cloud Run remains planning-only until project identity, exact verification, a real deployment, and cleanup are proven.
