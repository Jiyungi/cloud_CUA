# Agent Test Validation

## Imported Scope

Jiyun's `jiyun-test` branch was merged without replacing newer main-branch tests. The imported history includes:

- the 50-service, 150-case AWS H evaluation catalog;
- ReceiptSplit and InvoiceOps under `agent-test-projects/`;
- each project's unit, component, build, and Playwright fixtures.

## AWS Evaluation And Skills

- All 150 cases pass with complete structured evidence.
- All 150 cases fail closed when one required fact is unknown.
- The local registry contains exactly 53 skills.
- H's hosted catalog reports all 53 skills synced.
- Amplify's existing skill was expanded; the other 49 catalog services became new skills.

These are contract conformance tests. They are not 150 live AWS mutations. Running every provisioning and recovery case live would create high-cost services and exceed the $5 policy.

## Local Application Results

ReceiptSplit:

- 11 unit/component tests passed.
- Production build passed.
- Playwright upload, review, split, and reminder flow passed.
- Mock mode made no application API requests.

InvoiceOps:

- 29 unit/component tests passed.
- Production build passed.
- Three Playwright upload, review, role, approval, and rejection flows passed.
- Mock mode made no application API requests.

## Published Frontend Smokes

Both apps were manually deployed to Amplify Hosting from their built artifacts with branch name `jiyun-test` and exact Cloud CUA run tags.

| Fixture | Amplify app | Live URL |
| --- | --- | --- |
| ReceiptSplit | `cloud-cua-receipt-split-6881fd62` | https://jiyun-test.dlxrss6fqphr3.amplifyapp.com |
| InvoiceOps | `cloud-cua-invoiceops-a48ce9f0` | https://jiyun-test.d5mex5o827iae.amplifyapp.com |

AWS app/tag/branch/job verification, HTTP checks, and root/deep-link Playwright checks pass. The first rewrite used `/<*>`, which returned `index.html` for JavaScript assets. The corrected deployment uses AWS's extension-excluding SPA rule and the Amplify skill now records that rule. See the [AWS rewrite example](https://docs.aws.amazon.com/amplify/latest/userguide/redirect-rewrite-examples.html#redirects-for-single-page-web-apps-spa).

These deployments are frontend-only and run the fixtures' default mock mode. They are not full AWS acceptance passes.

## Full Backend Blockers

The fixture source explicitly sets `backend_initial_state` to `absent`. AWS mode currently renders `AWS backend required` and performs no AWS request. Full acceptance still requires implementation and proof for Cognito, API Gateway, Lambda, private S3/KMS, Textract, queues/topics, DynamoDB, Scheduler, SES, monitoring, and audit services. InvoiceOps additionally requires a real Step Functions approval workflow.

Cloud CUA now reads `agent-test.json` and blocks frontend-only completion before login:

- ReceiptSplit maps to 14 hosted skills; Textract and X-Ray remain explicit coverage gaps.
- InvoiceOps maps to 15 hosted skills; Textract remains an explicit coverage gap.

External prerequisites also remain:

- manually log into AWS in H's dedicated Chrome profile;
- verify an SES sender identity; the account currently has none and remains in the SES sandbox.

Cleanup remains explicit. `cloud-cua aws-cleanup` currently finds exactly the two published Amplify apps.
