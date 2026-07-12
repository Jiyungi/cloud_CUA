# Cloud CUA Sample Applications

This directory contains intentionally incomplete applications for testing Cloud CUA. Each fixture is a real product concept with a working mock frontend, but its backend and AWS infrastructure are deliberately absent.

| Fixture | Audience | Product | AWS workload under test |
| --- | --- | --- | --- |
| `receipt-split` | B2C | Upload a receipt, review extracted items, split a bill, and track settlement | Consumer authentication, private uploads, asynchronous expense extraction, exact-money calculations, and scheduled reminders |
| `invoiceops` | B2B | Receive vendor invoices, review extracted fields, route approval, and track overdue work | Role-based access, encrypted documents, asynchronous extraction, human approval workflows, audit history, and scheduled operations |

## Intentional Boundary

The fixtures must contain:

- a Vite, React, and TypeScript frontend;
- deterministic mock data that works without a network;
- a typed frontend API boundary;
- an explicit AWS deployment contract;
- synthetic documents containing no real personal or financial information.

The fixtures must not contain:

- Lambda or server code;
- CDK, SAM, Terraform, CloudFormation, or other infrastructure code;
- AWS credentials or secret values;
- a working Vercel, Supabase, Firebase, or equivalent backend.

Mock UI success is not evidence of a successful AWS deployment. Full success requires the service-specific checks defined by each fixture's `AGENT_TEST_SPEC.md` and `agent-test.json`.

## How Cloud CUA Should Use These Fixtures

Pass the exact child directory as `repo_path`, not the parent Cloud CUA repository:

```text
agent-test-projects/receipt-split
agent-test-projects/invoiceops
```

The current Cloud CUA implementation should detect each child as a Vite frontend and recommend AWS Amplify. It does not yet implement the required backend services, so it must report that backend work as unsupported instead of claiming a complete deployment.

Amplify connects the parent Git repository. A real run must configure the fixture as a monorepo app, use the exact child app root, and deploy the `jiyun-test` branch. The current hard-coded `main` default is a known agent gap exposed by these fixtures.

Each application will have its own `package.json`, lockfile, tests, resource prefix, and AWS resources. They must not share runtime resources or install dependencies from the repository root.
