from __future__ import annotations

from .base import VerifierResult


def verify_playwright_url(url: str) -> VerifierResult:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                browser_source = "installed Chrome"
            except Exception:
                browser = playwright.chromium.launch(headless=True)
                browser_source = "Playwright Chromium"
            page = browser.new_page()
            browser_errors: list[str] = []

            def record_console_error(message) -> None:
                location_url = str((message.location or {}).get("url") or "")
                if message.type == "error" and not location_url.endswith("/favicon.ico"):
                    browser_errors.append(message.text)

            page.on("console", record_console_error)
            page.on("pageerror", lambda error: browser_errors.append(str(error)))
            response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            title = page.title()
            body = page.locator("body").inner_text(timeout=10_000).strip()
            status = response.status if response else None
            browser.close()
        if status is not None and not 200 <= status < 300:
            return VerifierResult("playwright_render", "failed", "playwright chromium channel=chrome", f"Browser navigation returned HTTP {status}.")
        if browser_errors:
            return VerifierResult(
                "playwright_render",
                "failed",
                "playwright chromium channel=chrome",
                "Browser console/page errors: " + " | ".join(browser_errors[:5]),
            )
        if not body:
            return VerifierResult("playwright_render", "failed", "playwright chromium channel=chrome", "Rendered page body was empty.")
        return VerifierResult(
            "playwright_render",
            "passed",
            f"playwright {browser_source}",
            f"Rendered HTTP {status} with {browser_source}; title={title!r}; bodyLength={len(body)}.",
        )
    except Exception as exc:
        return VerifierResult("playwright_render", "failed", "playwright chromium channel=chrome", f"Playwright render failed: {type(exc).__name__}: {exc}")
