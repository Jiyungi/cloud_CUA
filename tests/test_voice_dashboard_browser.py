from __future__ import annotations

import json

from playwright.sync_api import sync_playwright

from cloud_cua.dashboard import render_dashboard


def test_voice_dashboard_has_no_browser_errors_or_horizontal_overflow() -> None:
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route_request(route) -> None:
            path = route.request.url.split("?", 1)[0]
            if path.endswith("/defaults"):
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"repo_path": "C:/work/app"}))
            elif path.endswith("/capabilities"):
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"gradium_api_key_present": True, "container_mode": False}))
            else:
                route.fulfill(status=200, content_type="text/html", body=render_dashboard())

        page.route("http://cloud-cua.test/**", route_request)
        page.goto("http://cloud-cua.test/", wait_until="networkidle")
        assert page.locator("#micButton").inner_text() == "Hold to talk"
        assert page.locator("#voiceTranscript").count() == 1
        assert page.locator("#voiceResponse").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth") is True

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(100)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth") is True
        assert page.locator("#micButton").is_visible()
        browser.close()

    assert errors == []
