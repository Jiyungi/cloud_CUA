# InvoiceOps Agent Test Specification

## Product Goal

InvoiceOps is a B2B accounts-payable portal for a commercial property-management company. Maintenance vendors upload invoices, an AP clerk reviews extracted fields, the responsible property manager approves or rejects the invoice, and finance administrators monitor audit history and overdue work.

Users and permissions:

- `vendor`: upload and view only invoices belonging to its vendor account;
- `ap_clerk`: correct extracted fields and send invoices for approval;
- `property_manager`: approve or reject invoices assigned to managed properties;
- `finance_admin`: view every invoice, decision, and audit entry.

Accepted documents are synthetic PDF, JPG, PNG, or JPEG invoices up to 10 MiB. The included two-page invoice must contain fake vendor, property, invoice number, dates, work-order/PO reference, line items, and total, and be marked `SYNTHETIC TEST INVOICE - NOT VALID`.

The sample is intentionally frontend-only. Cloud CUA must build and prove the missing AWS backend rather than treating mock UI behavior as deployment success.

## Fixture Boundary

The completed fixture will provide:

1. sign-in or a mock role switcher;
2. an invoice queue with status and due-date filters;
3. an upload dialog;
4. invoice detail and editable extracted fields;
5. approve/reject actions with reasons and audit history.

The fixture contains no server, AWS SDK initialization, infrastructure-as-code, credentials, real invoices, or provisioned AWS resource identifiers.

Invoice states are:

```text
UPLOADED -> EXTRACTING -> PENDING_REVIEW -> PENDING_APPROVAL -> APPROVED | REJECTED
```

## Runtime Modes

### Mock mode

`VITE_DATA_MODE=mock` is the local default.

- Display a persistent `DEMO DATA` badge.
- Use seeded fake roles, vendors, properties, invoices, and audit events.
- Simulate upload, extraction, correction, and approval locally.
- Persist only nonsensitive fixture state in localStorage.
- Make zero network requests.

### AWS mode

`VITE_DATA_MODE=aws` is the deployment acceptance mode.

- Require every public AWS configuration value listed in `.env.example`.
- Replace the role switcher with Cognito authentication and JWT claims.
- Call authenticated `/health` before displaying `AWS CONNECTED`.
- Request a presigned S3 upload URL and use the deployed API for all state.
- Display a blocking configuration or request error on failure.
- Never silently fall back to mock data.

## Frontend API Contract

Every route except `/health` requires a valid Cognito JWT. Lambda must enforce Cognito groups and record-level tenant/vendor/property ownership; hiding a button is not authorization.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Confirm the deployed API and environment |
| `GET` | `/me` | Return the authenticated role, tenant, vendor, and property assignments |
| `GET` | `/invoices` | List only invoices visible to the current role and assignments |
| `GET` | `/invoices/{id}` | Read invoice, extraction, approval, and audit details |
| `POST` | `/invoices/upload-url` | Validate metadata and return a short-lived S3 PUT URL |
| `PATCH` | `/invoices/{id}/extracted-fields` | Correct extracted fields and advance to approval when valid |
| `POST` | `/invoices/{id}/decision` | Approve or reject an authorized pending invoice with a reason |

Retryable writes require idempotency keys and every business state transition appends an immutable audit item.

## Required AWS Architecture

The target implementation must use AWS directly. A Vercel-only or third-party backend does not satisfy this test.

1. **Amplify Hosting**: connect the parent Git repository, deploy `jiyun-test`, configure `agent-test-projects/invoiceops` as the monorepo app root, run `npm ci` and `npm run build`, publish `dist`, add an SPA rewrite, and set only public `VITE_*` variables.
2. **Cognito**: create a user pool, public SPA client without a secret, authorization-code flow with PKCE, hosted domain, callback/logout URLs, the four role groups, and synthetic test users.
3. **API Gateway HTTP API**: create the listed routes, JWT authorizer, and CORS restricted to the Amplify origin; Lambda must enforce group claims and record ownership.
4. **Lambda**: separate API handling, extraction start, extraction result processing, approval request, workflow result, and overdue reminder responsibilities with least-privilege roles.
5. **S3**: create a private invoice bucket with Block Public Access, bucket-owner-enforced ownership, versioning, exact-origin CORS, presigned PUT uploads, SSE-KMS, upload event notification, and a short test-data lifecycle.
6. **KMS**: create a customer-managed key and alias with rotation enabled for invoice objects and sensitive workflow data.
7. **Textract**: use asynchronous `StartExpenseAnalysis` and paginated `GetExpenseAnalysis`, including for the sample PDF; retain confidence scores, model version, and the job-to-invoice mapping.
8. **SNS and SQS**: publish Textract completion to an encrypted result queue, attach a processing DLQ and redrive policy, and restrict the queue policy to the completion topic.
9. **DynamoDB**: use an on-demand, point-in-time-recovery-enabled encrypted table for invoices, ownership, extraction jobs, workflow callbacks, status/due-date indexes, and append-only audit items.
10. **Step Functions Standard**: start after AP review, pause with a task-token callback for human approval, accept an authorized decision through the API, branch to approved/rejected states, and enforce a finite timeout.
11. **EventBridge Scheduler**: invoke an overdue-reminder Lambda daily with retries, a dedicated DLQ, and a least-privilege execution role.
12. **SES**: use a verified sender for approval, outcome, and overdue messages; automated evidence uses the SES mailbox simulator while the account is in the sandbox.
13. **IAM**: use separate least-privilege roles for Lambda, Textract notification, Step Functions, and Scheduler; do not use an administrator role or wildcard resource permissions.
14. **CloudWatch and CloudTrail**: use finite log retention, invoice correlation IDs, and alarms for Lambda errors, failed workflows, queue age, and DLQ depth; use CloudTrail Event History as provisioning evidence.

## Security and Failure Requirements

- Unauthenticated protected API requests return `401`.
- An authenticated but unauthorized decision returns `403`.
- Vendors cannot read other vendors' invoices or approve any invoice.
- Property managers can decide only invoices assigned to their properties.
- Unsupported formats and files above 10 MiB are rejected before upload.
- S3 objects are private, versioned, and encrypted with the intended KMS key.
- An unreadable invoice reaches an explicit review or extraction-failed state; it never receives fixture fields.
- Duplicate completion messages do not create duplicate transitions or audit entries.
- Abandoned approvals time out instead of leaving an unbounded workflow execution.
- Poison messages reach the processing DLQ after the configured receive count.
- Logs include correlation IDs but no document contents, task tokens, JWTs, or credentials.

## Independent Acceptance Checks

Local fixture checks:

- `npm ci`, unit tests, component tests, production build, and Playwright pass.
- Mock mode makes zero network requests.
- Role-sensitive UI tests cover vendor, AP clerk, property manager, and finance admin behavior.
- Cloud CUA analyzes the exact child path as `vite`, `frontend_static`, `npm run build`, `dist`, and `aws_amplify`.

Full AWS checks:

- Amplify branch deployment succeeds, the live URL returns `200`, and deep links render.
- Cognito role claims match the synthetic test users and the SPA client has no secret.
- An unauthenticated upload request returns `401`; unauthorized read/decision requests return `403`.
- The synthetic invoice is privately uploaded, is versioned and SSE-KMS encrypted, and produces a real Textract job ID.
- Extraction reaches `PENDING_REVIEW`, corrected fields persist, and AP submission starts a Standard Step Functions execution.
- The workflow waits for approval and reaches `SUCCEEDED` after an authorized decision.
- DynamoDB contains the complete state sequence and append-only audit entries.
- The reminder path returns an SES simulator message ID and leaves happy-path DLQs empty.
- Verifiers inspect the exact Amplify app/branch/job, Cognito configuration/groups, API routes/authorizer, S3 controls, KMS rotation, Lambda configuration, Textract job, queue redrive policies, DynamoDB PITR/indexes, Step Functions execution, Scheduler target, alarms, and relevant CloudTrail events.
- An H CUA completion message without these verifier results is not a pass.

## Cleanup Contract

Use region `us-east-1`, prefix every resource with `invoiceops-test-<run-id>`, and tag supported resources with:

```text
Project=InvoiceOps
Environment=test
ManagedBy=Cloud-CUA
TestFixture=invoiceops
```

The deployment report must list every resource, live URL, verifier artifact, estimated cost exposure, workflow execution, and cleanup dependency. Cleanup requires separate approval; preserve verification evidence before removing test resources, disable schedules first, stop active workflows, empty versioned objects, and report anything that remains.

## Known Current-Agent Expectations

The current Cloud CUA implementation should successfully recognize and plan the Amplify frontend. It does not yet implement the backend services above, exact service verifiers, monorepo app-root selection, or the `jiyun-test` branch override. Until those exist, the correct result is a clearly documented blocked/unsupported backend—not a completed deployment.
