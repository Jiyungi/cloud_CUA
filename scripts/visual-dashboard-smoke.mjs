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
  const consoleErrors = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", error => consoleErrors.push(error.message));
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  record(`${label}: dashboard loaded`, await visibleText(page, "Cloud CUA"));
  record(`${label}: deploy button visible`, await page.getByRole("button", { name: "Deploy" }).isVisible());
  record(`${label}: control loop visible`, await page.getByRole("heading", { name: "Control Loop" }).isVisible());
  record(`${label}: skills panel visible`, await page.getByRole("heading", { name: "Skills" }).isVisible());
  record(`${label}: safety panel visible`, await page.getByRole("heading", { name: "Safety" }).isVisible());
  record(`${label}: skill sync control visible`, await page.getByRole("button", { name: "Sync H skills" }).isVisible());
  record(`${label}: proof visible`, await page.getByRole("heading", { name: "Proof" }).isVisible());
  record(`${label}: no legacy Amplify button`, !(await visibleText(page, "Run Amplify step")));
  record(`${label}: no App Runner copy`, !(await visibleText(page, "App Runner")));
  await page.locator("#reportState").evaluate(element => {
    element.textContent = "a/very/long/repository/path/that/must/remain/inside/its/proof/cell/DEPLOYMENT_REPORT.md";
  });
  const reportContained = await page.locator("#reportState").evaluate(element => {
    const parent = element.parentElement.getBoundingClientRect();
    const child = element.getBoundingClientRect();
    return child.left >= parent.left && child.right <= parent.right + 1;
  });
  record(`${label}: long proof value stays contained`, reportContained);
  await assertNoHorizontalOverflow(page, label);
  record(`${label}: no browser errors`, consoleErrors.length === 0, consoleErrors.join(" | "));

  await page.screenshot({ path: path.join(outDir, `${stamp}-${label}.png`), fullPage: true });
  await page.close();
}

async function runInteraction(browser) {
  const page = await browser.newPage({ viewport: { width: 1365, height: 768 } });
  const consoleErrors = [];
  page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", error => consoleErrors.push(error.message));
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  await page.locator("details.devtools").evaluate(element => { element.open = true; });
  await page.getByRole("button", { name: "Start local repo" }).click();
  const modal = page.getByRole("dialog");
  await modal.waitFor({ state: "visible", timeout: 10000 });
  record("login modal copy", await page.getByText("Log into AWS in this browser window. Click Continue when done.").isVisible());
  await page.screenshot({ path: path.join(outDir, `${stamp}-login-modal.png`), fullPage: true });

  await page.evaluate(() => {
    hideLogin();
    showRuntimeModal({ missing_names: ["DATABASE_URL", "API_TOKEN"], public_build_names: ["VITE_API_URL"] });
  });
  record("runtime secret modal", await page.getByRole("heading", { name: "Runtime configuration required" }).isVisible());
  record("runtime secret inputs", await page.locator("input[type=password]").count() === 2);
  await page.screenshot({ path: path.join(outDir, `${stamp}-runtime-modal.png`), fullPage: true });
  await page.evaluate(() => {
    runtimeModal.style.display = "none";
    costModal.style.display = "flex";
  });
  record("cost action modal", await page.getByRole("heading", { name: "Cost action required" }).isVisible());
  await page.screenshot({ path: path.join(outDir, `${stamp}-cost-modal.png`), fullPage: true });

  const caps = await (await page.request.get(`${baseUrl}/capabilities?repo_path=${encodeURIComponent(process.cwd())}`)).json();
  record("capabilities endpoint has container flag", Object.hasOwn(caps, "container_mode"));
  record("interaction has no browser errors", consoleErrors.length === 0, consoleErrors.join(" | "));
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
