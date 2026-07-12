from __future__ import annotations

import json

from .base import VerifierResult, run_command


def verify_playwright_url(url: str) -> VerifierResult:
    safe_url = json.dumps(url)
    script = (
        "const { chromium } = require('playwright');"
        "(async()=>{const b=await chromium.launch({headless:true});"
        "const p=await b.newPage();"
        f"await p.goto({safe_url}, {{waitUntil:'domcontentloaded', timeout:30000}});"
        "const title=await p.title(); const body=await p.textContent('body');"
        "await b.close(); if(!body || body.trim().length===0) process.exit(2);"
        "console.log(JSON.stringify({title, bodyLength: body.length}));})();"
    )
    return run_command("playwright_render", ["node", "-e", script], timeout=45)
