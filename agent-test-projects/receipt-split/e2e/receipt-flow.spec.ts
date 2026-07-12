import path from "node:path";
import { expect, test } from "@playwright/test";

test("completes the mock upload, review, split, and reminder flow without application API calls", async ({ page }, testInfo) => {
  const apiRequests: string[] = [];
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];

  page.on("request", (request) => {
    if (["fetch", "xhr"].includes(request.resourceType())) {
      apiRequests.push(request.url());
    }
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/receipts");
  await expect(page.getByText("DEMO DATA")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Harbor Table" })).toBeVisible();

  await page.getByRole("link", { name: "Add a receipt" }).click();
  await page.getByLabel(/choose a receipt/i).setInputFiles(
    path.resolve("public/test-fixtures/synthetic-receipt.png"),
  );
  await page.getByRole("button", { name: /review extracted receipt/i }).click();

  await expect(page.getByRole("heading", { name: "Sunset Market" })).toBeVisible();
  await page.getByLabel("Merchant").fill("Sunset Market Picnic");
  await page.getByRole("button", { name: /confirm and continue/i }).click();

  await expect(page.getByRole("heading", { name: "Sunset Market Picnic" })).toBeVisible();
  await page.getByLabel("Friend name").fill("Sam");
  await page.getByLabel("Email").fill("sam@example.test");
  await page.getByRole("button", { name: "Add friend" }).click();
  await page.getByRole("button", { name: /split all equally/i }).click();
  await page.getByRole("button", { name: /save exact split/i }).click();
  await expect(page.getByText(/split saved locally/i)).toBeVisible();

  await page.getByRole("button", { name: /remind unpaid friends/i }).click();
  await expect(page.getByText(/demo reminder scheduled locally/i)).toBeVisible();
  await page.getByRole("button", { name: "Mark paid" }).first().click();
  await expect(page.getByText(/payment status updated locally/i)).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath("receipt-split-flow.png"), fullPage: true });
  expect(apiRequests).toEqual([]);
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});
