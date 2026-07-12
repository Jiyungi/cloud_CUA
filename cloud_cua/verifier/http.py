from __future__ import annotations

from urllib.error import URLError
from urllib.request import Request, urlopen

from .base import VerifierResult


def verify_http_url(url: str) -> VerifierResult:
    try:
        req = Request(url, method="HEAD")
        with urlopen(req, timeout=20) as response:
            return VerifierResult("http_live_url", "passed", f"HEAD {url}", f"HTTP {response.status}")
    except Exception as exc:
        try:
            with urlopen(url, timeout=20) as response:
                return VerifierResult("http_live_url", "passed", f"GET {url}", f"HTTP {response.status}")
        except URLError as url_exc:
            return VerifierResult("http_live_url", "failed", f"HEAD/GET {url}", str(url_exc))
        except Exception as second_exc:
            return VerifierResult("http_live_url", "failed", f"HEAD/GET {url}", f"{exc}; {second_exc}")

