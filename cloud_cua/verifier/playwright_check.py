from __future__ import annotations

from .base import VerifierResult


def verify_playwright_url(url: str) -> VerifierResult:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            title = page.title()
            body = page.locator("body").inner_text(timeout=10_000).strip()
            status = response.status if response else None
            browser.close()
        if not body:
            return VerifierResult("playwright_render", "failed", "playwright chromium channel=chrome", "Rendered page body was empty.")
        return VerifierResult(
            "playwright_render",
            "passed",
            "playwright chromium channel=chrome",
            f"Rendered HTTP {status}; title={title!r}; bodyLength={len(body)}.",
        )
    except Exception as exc:
        return VerifierResult("playwright_render", "failed", "playwright chromium channel=chrome", f"Playwright render failed: {type(exc).__name__}: {exc}")
