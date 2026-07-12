# InvoiceOps

InvoiceOps is a frontend-only B2B fixture for testing whether Cloud CUA can recognize and safely plan a substantial AWS invoice-processing backend. Local development uses deterministic mock users and invoices and makes no network requests.

## Local development

```bash
npm install
npm run dev
```

Use the role switcher to compare vendor, AP clerk, property manager, and finance administrator visibility. The default `.env.example` selects mock mode. Never commit real invoice data, AWS identifiers, credentials, or secrets.

The local workflow is deliberately deterministic: upload a PDF/JPG/PNG of at most 10 MiB as vendor Rosa, review the extracted fields as AP clerk Daniel, then switch to property manager Priya to approve or reject it. Finance administrator Morgan has read-only oversight. Every transition is written to the browser-only audit history; no document is uploaded anywhere.

## Synthetic document

`public/test-fixtures/synthetic-invoice.pdf` is a clearly marked, two-page fake invoice for the upload flow. It contains no real company, bank, tax, or payment data. To regenerate it after installing ReportLab:

```bash
npm run fixture:generate
```

The generator lives in `scripts/generate-invoice-fixture.py`. Generated render previews belong under ignored `tmp/pdfs/`, not in source control.

## Local verification

```bash
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The Playwright scenarios cover upload, manual extraction review, AP correction, approval and rejection, every fixture role, and failure states. They also fail on application `fetch`/XHR calls, browser console errors, or uncaught page errors.

## Test contract

Read `AGENT_TEST_SPEC.md` before running Cloud CUA. A rendered mock frontend is not a successful AWS deployment.
