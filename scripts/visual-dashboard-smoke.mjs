import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const baseUrl = process.env.CLOUD_CUA_VISUAL_URL || "http://127.0.0.1:3000";
const outDir = process.env.CLOUD_CUA_VISUAL_OUT || path.join(".cloud-cua", "visual-checks");
const stamp = new Date().toISOString().replace(/[:.]/g, "-");

const checks = [];

function record(name, passed, detail = "") {
  checks.push({ name, passed, detail });
  if (!passed) {
    throw new Error(`${name}: ${detail}`);
  }
}

async function visibleText(page, text) {
  return (await page.getByText(text, { exact: false }).count()) > 0;
}

async function assertNoHorizontalOverflow(page, label) {
  const overflow = await page.evaluate(() => ({
    width: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
  }));
  const maxScrollWidth = Math.max(overflow.scrollWidth, overflow.bodyScrollWidth);
  record(`${label}: no horizontal overflow`, maxScrollWidth <= overflow.width + 2, JSON.stringify(overflow));
}

async function runViewport(browser, label, viewport) {
  const page = await browser.newPage({ viewport });
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  record(`${label}: dashboard loaded`, await visibleText(page, "Cloud CUA"));
  record(`${label}: deploy button visible`, await page.getByRole("button", { name: "Deploy" }).isVisible());
  record(`${label}: control loop visible`, await page.getByRole("heading", { name: "Control Loop" }).isVisible());
  record(`${label}: skills panel visible`, await page.getByRole("heading", { name: "Skills" }).isVisible());
  record(`${label}: skill sync control visible`, await page.getByRole("button", { name: "Sync H skills" }).isVisible());
  record(`${label}: proof visible`, await page.getByRole("heading", { name: "Proof" }).isVisible());
  record(`${label}: no legacy Amplify button`, !(await visibleText(page, "Run Amplify step")));
  record(`${label}: no App Runner copy`, !(await visibleText(page, "App Runner")));
  await assertNoHorizontalOverflow(page, label);

  await page.screenshot({ path: path.join(outDir, `${stamp}-${label}.png`), fullPage: true });
  await page.close();
}

async function runInteraction(browser) {
  const page = await browser.newPage({ viewport: { width: 1365, height: 768 } });
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  await page.getByRole("button", { name: "Start local repo" }).click();
  const modal = page.getByRole("dialog");
  await modal.waitFor({ state: "visible", timeout: 10000 });
  record("login modal copy", await page.getByText("Log into AWS in this browser window. Click Continue when done.").isVisible());
  await page.screenshot({ path: path.join(outDir, `${stamp}-login-modal.png`), fullPage: true });

  const caps = await (await page.request.get(`${baseUrl}/capabilities?repo_path=${encodeURIComponent(process.cwd())}`)).json();
  record("capabilities endpoint has container flag", Object.hasOwn(caps, "container_mode"));
  await page.close();
}

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  await runViewport(browser, "desktop", { width: 1365, height: 768 });
  await runViewport(browser, "mobile", { width: 390, height: 844 });
  await runInteraction(browser);
} finally {
  await browser.close();
}

const summary = { baseUrl, createdAt: new Date().toISOString(), checks };
await writeFile(path.join(outDir, `${stamp}-summary.json`), JSON.stringify(summary, null, 2));
console.log(`Visual dashboard smoke passed with ${checks.length} checks.`);
