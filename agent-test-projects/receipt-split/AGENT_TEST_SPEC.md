# ReceiptSplit Agent Test Specification

## Product Goal

ReceiptSplit is a consumer application for restaurant and grocery bills. One person uploads a receipt, reviews AWS-extracted merchant and line-item data, assigns items or equal shares to friends, sends settlement reminders, and records who has paid.

The sample is intentionally frontend-only. Cloud CUA is responsible for recognizing the missing backend, proposing the AWS architecture, obtaining approval, provisioning only supported resources, and verifying every claim independently.

## Fixture Boundary

The completed fixture will include four frontend views:

1. receipt list and settlement status;
2. JPG, PNG, or PDF upload, limited to 10 MiB;
3. extraction review with editable merchant, date, tax, tip, total, and line items;
4. split summary with participants, allocations, reminders, and paid status.

All money values use integer cents. A seeded fake receipt and three fake friends make the mock flow deterministic. The synthetic receipt must be visibly marked `SYNTHETIC TEST RECEIPT - NOT VALID`.

The fixture contains no server, AWS SDK initialization, infrastructure-as-code, credentials, or real cloud resource identifiers.

## Runtime Modes

### Mock mode

`VITE_DATA_MODE=mock` is the local default.

- Display a persistent `DEMO DATA` badge.
- Use only deterministic fixtures and localStorage.
- Keep uploads inside the browser; do not send them anywhere.
- Simulate extraction, reminders, and payment updates locally.
- Make zero network requests.

### AWS mode

`VITE_DATA_MODE=aws` is the deployment acceptance mode.

- Require every public AWS configuration value listed in `.env.example`.
- Authenticate through Cognito.
- Call authenticated `/health` before displaying `AWS CONNECTED`.
- Request a presigned URL, upload directly to S3, and read status through the API.
- Display a blocking configuration or request error on failure.
- Never silently fall back to mock data.

## Frontend API Contract

Every route except `/health` requires a valid Cognito JWT.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Confirm the deployed API and environment |
| `GET` | `/receipts` | List receipts owned by the current user |
| `POST` | `/receipts/upload-url` | Validate metadata and return a short-lived S3 PUT URL |
| `GET` | `/receipts/{id}` | Read extraction, line items, participants, and settlement state |
| `PATCH` | `/receipts/{id}` | Correct extracted receipt fields |
| `POST` | `/receipts/{id}/confirm` | Confirm extraction and freeze the reviewed total |
| `PUT` | `/receipts/{id}/split` | Save participants and integer-cent allocations |
| `POST` | `/receipts/{id}/reminders` | Schedule or send a settlement reminder |
| `POST` | `/settlements/{id}/mark-paid` | Record a participant payment status |

Every read and write must enforce the Cognito subject as receipt owner. Retryable write requests require idempotency keys.

## Required AWS Architecture

The target implementation must use AWS directly. A Vercel-only or third-party backend does not satisfy this test.

1. **Amplify Hosting**: connect the parent Git repository, deploy `jiyun-test`, configure `agent-test-projects/receipt-split` as the monorepo app root, run `npm ci` and `npm run build`, publish `dist`, add an SPA rewrite, and set only public `VITE_*` variables.
2. **Cognito**: create a user pool with email verification, a public SPA client without a secret, authorization-code flow with PKCE, callback/logout URLs, and an API Gateway JWT authorizer.
3. **API Gateway HTTP API**: create the listed routes, restrict CORS to localhost and the Amplify origin, and attach the JWT authorizer to protected routes.
4. **Lambda**: separate the API handler, extraction starter, extraction result normalizer, and reminder sender; give each a least-privilege role.
5. **S3**: create a private receipt bucket with Block Public Access, bucket-owner-enforced ownership, SSE-KMS, presigned PUT uploads, exact-origin CORS, an `incoming/{user-sub}/{receipt-id}/` key layout, and a short test-data lifecycle.
6. **Textract**: use asynchronous `StartExpenseAnalysis` for the S3 object, publish completion to SNS, call paginated `GetExpenseAnalysis`, and retain confidence scores and model version.
7. **SQS and SNS**: route new uploads through an extraction queue and DLQ; route the Textract completion topic through a result queue and DLQ; use restricted topic/queue policies and idempotent consumers.
8. **DynamoDB**: use an on-demand, point-in-time-recovery-enabled table for receipts, items, participants, splits, settlements, and job mappings; enforce conditional writes for replay safety.
9. **EventBridge Scheduler**: create one-time settlement reminder schedules with retries, a DLQ, and a dedicated execution role.
10. **SES**: use a verified sender and the SES mailbox simulator for automated invitation and reminder evidence while the account remains in the sandbox.
11. **KMS and IAM**: use a scoped application key where supported and explicit roles for Lambda, Textract-to-SNS, and Scheduler; do not grant administrator access or wildcard resource permissions.
12. **CloudWatch, X-Ray, and CloudTrail**: use finite log retention, tracing, correlation IDs, and alarms for API 5xx, Lambda errors, queue age, DLQ depth, and failed extraction; use CloudTrail Event History as provisioning evidence.

Step Functions is intentionally omitted from ReceiptSplit so InvoiceOps owns the human-approval workflow test. Secrets Manager is unnecessary because this design has no backend application secret.

## Security and Failure Requirements

- Unauthenticated protected API requests return `401`.
- One user cannot read or modify another user's receipt.
- Unsupported formats and files above 10 MiB are rejected before upload.
- S3 objects are private, encrypted with the intended KMS key, and unavailable through public URLs.
- An unlisted CORS origin is rejected.
- A blank or unreadable receipt reaches `NEEDS_REVIEW` or `EXTRACTION_FAILED`; it never receives fixture data.
- Duplicate S3, SQS, SNS, or Textract events do not duplicate receipt items.
- Poison messages reach a DLQ after the configured receive count.
- Logs contain correlation IDs but no receipt image contents, tokens, or credentials.

## Independent Acceptance Checks

Local fixture checks:

- `npm ci`, unit tests, component tests, production build, and Playwright pass.
- Mock mode makes zero network requests.
- Split shares always sum exactly to the reviewed total.
- Cloud CUA analyzes the exact child path as `vite`, `frontend_static`, `npm run build`, `dist`, and `aws_amplify`.

Full AWS checks:

- Amplify branch deployment succeeds, the live URL returns `200`, and deep links render.
- A dedicated Cognito test user completes the real upload flow.
- A known synthetic receipt traverses S3 -> SQS -> Lambda -> Textract -> SNS/SQS -> DynamoDB.
- Extracted merchant and total match the fixture's documented expected values within the stated tolerance.
- Replaying the same event produces no duplicate line items.
- A reminder schedule invokes Lambda and produces an SES simulator message ID.
- Verifiers inspect the exact Amplify app/branch/job, Cognito pool/client, API routes/authorizer, S3 policy/encryption/CORS, Lambda configuration, DynamoDB PITR, queue redrive policies, SNS subscription, Scheduler target, alarms, and relevant CloudTrail events.
- An H CUA completion message without these verifier results is not a pass.

## Cleanup Contract

Use region `us-east-1`, prefix every resource with `receiptsplit-test-<run-id>`, and tag supported resources with:

```text
Project=ReceiptSplit
Environment=test
ManagedBy=Cloud-CUA
TestFixture=receipt-split
```

The deployment report must list every created resource, live URL, verifier artifact, estimated cost exposure, cleanup order, and any resource that could not be deleted. Cleanup requires separate approval and must preserve evidence before removing test resources.

## Known Current-Agent Expectations

The current Cloud CUA implementation should successfully recognize and plan the Amplify frontend. It does not yet implement the backend services above, exact resource verifiers, monorepo app-root selection, or the `jiyun-test` branch override. Until those exist, the correct result is a clearly documented blocked/unsupported backend—not a completed deployment.
