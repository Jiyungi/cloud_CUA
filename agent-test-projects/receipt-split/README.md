# ReceiptSplit

ReceiptSplit is a frontend-only B2C fixture for testing whether Cloud CUA can recognize and safely plan a substantial AWS backend. Local development uses deterministic mock data and makes no network requests.

## Local development

```bash
npm install
npm run dev
```

The default `.env.example` selects mock mode. Copy it to `.env.local` only when local overrides are needed; never commit real identifiers or credentials.

The safe upload fixture lives at `public/test-fixtures/synthetic-receipt.png`. Regenerate it from its tracked SVG source with:

```bash
npm run fixture:generate
```

## Test contract

Read `AGENT_TEST_SPEC.md` before running Cloud CUA. A rendered mock frontend is not a successful AWS deployment.
