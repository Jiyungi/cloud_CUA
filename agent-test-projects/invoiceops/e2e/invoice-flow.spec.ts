import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

interface BrowserEvidence {
  apiRequests: string[];
  consoleErrors: string[];
  pageErrors: string[];
}

function collectBrowserEvidence(page: Page): BrowserEvidence {
  const evidence: BrowserEvidence = { apiRequests: [], consoleErrors: [], pageErrors: [] };
  page.on("request", (request) => {
    if (["fetch", "xhr"].includes(request.resourceType())) {
      evidence.apiRequests.push(request.url());
    }
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      evidence.consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => evidence.pageErrors.push(error.message));
  return evidence;
}

function expectCleanBrowser(evidence: BrowserEvidence): void {
  expect(evidence.apiRequests).toEqual([]);
  expect(evidence.consoleErrors).toEqual([]);
  expect(evidence.pageErrors).toEqual([]);
}

test("completes vendor upload, AP review, and manager approval without application API calls", async ({ page }, testInfo) => {
  const evidence = collectBrowserEvidence(page);

  await page.goto("/invoices");
  await expect(page.getByText("DEMO DATA")).toBeVisible();
  await page.getByLabel("Viewing as").selectOption("user-vendor-rosa");
  await page.getByRole("main").getByRole("link", { name: "Upload invoice" }).click();
  await page.getByLabel(/choose an invoice/i).setInputFiles(
    path.resolve("public/test-fixtures/synthetic-invoice.pdf"),
  );
  await page.getByRole("button", { name: "Extract invoice" }).click();

  await expect(page.getByRole("heading", { name: "Pacific HVAC Services" })).toBeVisible();
  await expect(page.getByText("Needs AP review")).toBeVisible();
  await page.getByLabel("Viewing as").selectOption("user-ap-daniel");
  await page.getByLabel("Invoice number").fill("PH-1048-VERIFIED");
  await page.getByLabel("Correction or verification note").fill(
    "Matched the synthetic service detail to work order WO-4821.",
  );
  await page.getByRole("button", { name: /submit for property approval/i }).click();

  await expect(page.getByText("Pending approval")).toBeVisible();
  await page.getByLabel("Viewing as").selectOption("user-manager-priya");
  await page.getByLabel("Decision reason").fill("Approved for the synthetic payment run.");
  await page.getByRole("button", { name: "Approve" }).click();

  await expect(page.getByText("Approved", { exact: true })).toBeVisible();
  for (const action of [
    "Invoice uploaded",
    "Extraction started",
    "Extraction completed",
    "AP review completed",
    "Invoice approved",
  ]) {
    await expect(page.getByText(action, { exact: true })).toBeVisible();
  }

  await page.screenshot({ path: testInfo.outputPath("invoiceops-approved-flow.png"), fullPage: true });
  expectCleanBrowser(evidence);
});

test("rejects unsupported files and sends unreadable invoices to manual AP review", async ({ page }) => {
  const evidence = collectBrowserEvidence(page);

  await page.goto("/invoices");
  await page.getByLabel("Viewing as").selectOption("user-vendor-rosa");
  await page.getByRole("main").getByRole("link", { name: "Upload invoice" }).click();
  await page.getByLabel(/choose an invoice/i).setInputFiles({
    name: "invoice.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not an invoice"),
  });
  await expect(page.getByRole("alert")).toContainText("PDF, JPG, JPEG, or PNG");

  await page.getByLabel(/choose an invoice/i).setInputFiles({
    name: "unreadable-invoice.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("synthetic unreadable PDF fixture"),
  });
  await page.getByRole("button", { name: "Extract invoice" }).click();

  await expect(page.getByText("Number not extracted")).toBeVisible();
  await expect(page.getByText("0% confidence")).toBeVisible();
  await expect(page.getByText("Extraction needs manual review", { exact: true })).toBeVisible();
  await page.getByLabel("Viewing as").selectOption("user-ap-daniel");
  await expect(page.getByLabel("Invoice number")).toHaveValue("");
  await expect(page.getByLabel("Invoice date")).toHaveValue("");
  await expect(page.getByLabel("Due date")).toHaveValue("");

  expectCleanBrowser(evidence);
});

test("enforces role-sensitive visibility and records a manager rejection", async ({ page }) => {
  const evidence = collectBrowserEvidence(page);

  await page.goto("/invoices/invoice-greenline-7781");
  await expect(page.getByText(/Only the assigned property manager/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);

  await page.getByLabel("Viewing as").selectOption("user-finance-morgan");
  await expect(page.getByText(/Only the assigned property manager/i)).toBeVisible();
  await expect(page.getByRole("button", { name: "Reject" })).toHaveCount(0);

  await page.getByLabel("Viewing as").selectOption("user-vendor-rosa");
  await expect(page.getByText(/not visible to the active role/i)).toBeVisible();

  await page.getByLabel("Viewing as").selectOption("user-manager-priya");
  await page.getByLabel("Decision reason").fill("Vendor must correct the synthetic work-order detail.");
  await page.getByRole("button", { name: "Reject" }).click();

  await expect(page.getByText("Rejected", { exact: true })).toBeVisible();
  await expect(page.getByText("Invoice rejected", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Vendor must correct the synthetic work-order detail.", { exact: true }).first(),
  ).toBeVisible();
  expectCleanBrowser(evidence);
});
