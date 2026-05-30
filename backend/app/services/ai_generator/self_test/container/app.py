"""
XSS self-test container — FastAPI + Playwright/Chromium.

POST /selftest
  Body: {html, xss_type, vulnerable_param, payload_solution, flag}
  Returns: {executed, flag_reachable, baseline_safe, detail}

The caller (xss_selftest.py) passes the page HTML inline (re-rendered from spec),
so this container needs no S3 or outbound network access.

Hardening:
  - New browser context per request (isolation, no cookie leak across calls)
  - Hard 15-second Playwright timeout
  - No outbound routes needed (HTML served internally via data: URI trick)
  - Single uvicorn worker
"""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("xss_selftest_container")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

app = FastAPI(title="XSS Self-Test Service", docs_url=None, redoc_url=None)

# Shared Playwright browser instance — created on startup, reused per request.
_browser = None
_playwright = None


class SelfTestRequest(BaseModel):
    html: str
    xss_type: str = "reflected"
    vulnerable_param: str = "q"
    payload_solution: str = ""
    flag: str = ""


class SelfTestResponse(BaseModel):
    executed: bool
    flag_reachable: bool
    baseline_safe: bool
    detail: str


@app.on_event("startup")
async def startup() -> None:
    global _browser, _playwright
    from playwright.async_api import async_playwright
    _playwright = await async_playwright().__aenter__()
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )
    logger.info("Chromium browser started")


@app.on_event("shutdown")
async def shutdown() -> None:
    global _browser, _playwright
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.__aexit__(None, None, None)
    logger.info("Chromium browser closed")


@app.post("/selftest", response_model=SelfTestResponse)
async def selftest(req: SelfTestRequest) -> SelfTestResponse:
    if _browser is None:
        raise HTTPException(status_code=503, detail="Browser not ready")

    try:
        result = await asyncio.wait_for(
            _run_selftest(req),
            timeout=15.0,
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("Self-test timed out for xss_type=%s", req.xss_type)
        return SelfTestResponse(
            executed=False,
            flag_reachable=False,
            baseline_safe=True,
            detail="Playwright timed out after 15s",
        )
    except Exception as exc:
        logger.exception("Self-test error: %s", exc)
        return SelfTestResponse(
            executed=False,
            flag_reachable=False,
            baseline_safe=True,
            detail=f"Internal error: {type(exc).__name__}: {exc}",
        )


async def _run_selftest(req: SelfTestRequest) -> SelfTestResponse:
    """
    Core Playwright logic.
    1. Serve HTML via data URI (no network needed).
    2. Baseline check: load page, confirm no XSS fires.
    3. Attack check: inject payload, confirm XSS fires + cookie readable.
    """
    assert _browser is not None

    # Encode HTML as data URI for Playwright navigation
    html_b64 = base64.b64encode(req.html.encode("utf-8")).decode("ascii")
    base_url = f"data:text/html;charset=utf-8;base64,{html_b64}"

    xss_type = req.xss_type.lower()
    param = req.vulnerable_param
    payload = req.payload_solution
    flag = req.flag

    # ── Baseline check — no payload ────────────────────────────────────────────
    baseline_safe = True
    ctx = await _browser.new_context()
    try:
        page = await ctx.new_page()
        baseline_fired = False

        def _on_dialog_baseline(dialog: Any) -> None:
            nonlocal baseline_fired
            baseline_fired = True
            asyncio.ensure_future(dialog.dismiss())

        page.on("dialog", _on_dialog_baseline)

        # Also check via window.__xss_fired sentinel
        await page.goto(base_url, timeout=8000, wait_until="domcontentloaded")
        await page.wait_for_timeout(800)

        xss_sentinel = await page.evaluate("() => window.__xss_fired || false")
        if baseline_fired or xss_sentinel:
            baseline_safe = False
    finally:
        await ctx.close()

    # ── Attack check — inject payload ──────────────────────────────────────────
    executed = False
    flag_reachable = False
    detail_parts: list[str] = []

    ctx = await _browser.new_context()
    try:
        page = await ctx.new_page()
        dialog_msgs: list[str] = []

        def _on_dialog_attack(dialog: Any) -> None:
            dialog_msgs.append(dialog.message)
            asyncio.ensure_future(dialog.dismiss())

        page.on("dialog", _on_dialog_attack)

        # Build attack URL based on xss_type
        if xss_type == "reflected":
            from urllib.parse import quote
            attack_url = f"{base_url}&{param}={quote(payload)}"
        elif xss_type == "dom":
            from urllib.parse import quote
            attack_url = f"{base_url}#{param}={quote(payload)}"
        elif xss_type == "stored":
            attack_url = base_url
        else:
            attack_url = base_url

        await page.goto(attack_url, timeout=8000, wait_until="domcontentloaded")

        if xss_type == "stored":
            # Fill textarea and submit to trigger stored XSS
            try:
                textarea = page.locator(f"textarea[name='{param}'], #{param}")
                await textarea.fill(payload, timeout=3000)
                submit = page.locator("button[type='submit'], input[type='submit']")
                await submit.click(timeout=3000)
                await page.wait_for_timeout(1000)
            except Exception as e:
                detail_parts.append(f"stored submit failed: {e}")

        await page.wait_for_timeout(1200)

        # Check execution signals
        xss_sentinel = await page.evaluate("() => window.__xss_fired || false")
        if dialog_msgs or xss_sentinel:
            executed = True
            detail_parts.append(
                f"XSS fired (alert_msgs={dialog_msgs!r}, sentinel={xss_sentinel})"
            )

        # Check flag reachability — does attacker JS see the cookie?
        cookies = await page.evaluate("() => document.cookie")
        if flag and flag in cookies:
            flag_reachable = True
            detail_parts.append("flag found in document.cookie")
        elif executed:
            # Even without flag in cookie, if XSS ran the challenge is exploitable
            # Flag reachability requires the flag to actually be in the cookie
            detail_parts.append(f"XSS fired but flag not in cookie (cookie={cookies[:80]!r})")

    finally:
        await ctx.close()

    detail = "; ".join(detail_parts) if detail_parts else (
        "no XSS signals detected" if not executed else ""
    )

    logger.info(
        "selftest result: xss_type=%s executed=%s flag_reachable=%s baseline_safe=%s",
        xss_type, executed, flag_reachable, baseline_safe,
    )

    return SelfTestResponse(
        executed=executed,
        flag_reachable=flag_reachable,
        baseline_safe=baseline_safe,
        detail=detail,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "browser": "ready" if _browser else "not_ready"}
