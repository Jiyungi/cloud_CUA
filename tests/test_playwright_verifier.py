from __future__ import annotations

from urllib.parse import quote

from cloud_cua.verifier.playwright_check import verify_playwright_url


def _data_url(html: str) -> str:
    return "data:text/html," + quote(html)


def test_playwright_verifier_accepts_rendered_body_without_errors() -> None:
    result = verify_playwright_url(_data_url("<title>OK</title><main>Rendered application</main>"))
    assert result.status == "passed"


def test_playwright_verifier_rejects_javascript_console_errors() -> None:
    result = verify_playwright_url(_data_url("<main>Visible fallback</main><script>console.error('asset MIME mismatch')</script>"))
    assert result.status == "failed"
    assert "asset MIME mismatch" in result.summary
