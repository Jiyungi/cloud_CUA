# InvoiceOps

InvoiceOps is a frontend-only B2B fixture for testing whether Cloud CUA can recognize and safely plan a substantial AWS invoice-processing backend. Local development uses deterministic mock users and invoices and makes no network requests.

## Local development

```bash
npm install
npm run dev
```

Use the role switcher to compare vendor, AP clerk, property manager, and finance administrator visibility. The default `.env.example` selects mock mode. Never commit real invoice data, AWS identifiers, credentials, or secrets.

## Test contract

Read `AGENT_TEST_SPEC.md` before running Cloud CUA. A rendered mock frontend is not a successful AWS deployment.
