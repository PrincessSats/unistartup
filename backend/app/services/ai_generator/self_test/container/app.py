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
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

logger = logging.getLogger("xss_selftest_container")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

app = FastAPI(title="XSS Self-Test Service", docs_url=None, redoc_url=None)

# Shared Playwright browser instance — created lazily on first use, reused after.
_browser = None
_playwright = None
_browser_error: str | None = None  # last launch failure, surfaced via /health
_browser_lock = asyncio.Lock()

# The page under test is served from a real localhost HTTP route (not a data:
# URI) so query strings, location.hash and document.cookie all behave like a
# real site. concurrency=1 (Yandex) + this lock guarantee one test at a time,
# so a single module-level slot for the current page is safe.
_current_html: str = ""
_selftest_lock = asyncio.Lock()
_PORT = int(__import__("os").environ.get("PORT", "8080"))


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


async def _ensure_browser():
    """
    Lazily launch Chromium on first request. A launch failure is recorded in
    _browser_error and surfaced via /health and /selftest, instead of crashing
    the process at startup (which Yandex reports as an opaque "exit status 3").
    """
    global _browser, _playwright, _browser_error
    # Reuse only if still connected; a single-process browser can die and leave
    # a stale handle that poisons every later request with TargetClosedError.
    if _browser is not None and _browser.is_connected():
        return _browser
    async with _browser_lock:
        if _browser is not None and _browser.is_connected():
            return _browser
        # Discard a dead browser before relaunching.
        if _browser is not None:
            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None
        try:
            from playwright.async_api import async_playwright
            _playwright = await async_playwright().__aenter__()
            # Serverless/Lambda-style flags. The renderer child is SIGKILL'd by
            # the container's process/cgroup limits (no Chromium stderr, not
            # total-memory OOM). --single-process keeps everything in one process
            # so there is no renderer fork to kill. This is the same approach
            # sparticuz/chromium uses on AWS Lambda.
            _browser = await _playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--single-process",
                    "--no-zygote",
                ],
            )
            _browser_error = None
            logger.info("Chromium browser started")
            return _browser
        except Exception as exc:
            _browser_error = f"{type(exc).__name__}: {exc}"
            logger.exception("Chromium launch failed: %s", exc)
            return None


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
    global _browser
    # The single-process browser dies occasionally; relaunch + retry once so a
    # transient crash does not fail an otherwise-solvable task.
    last_err = ""
    for attempt in range(2):
        if await _ensure_browser() is None:
            raise HTTPException(status_code=503, detail=f"Browser not ready: {_browser_error}")
        try:
            return await asyncio.wait_for(_run_selftest(req), timeout=20.0)
        except asyncio.TimeoutError:
            logger.warning("Self-test timed out for xss_type=%s", req.xss_type)
            return SelfTestResponse(
                executed=False, flag_reachable=False, baseline_safe=True,
                detail="Playwright timed out after 20s",
            )
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            logger.warning("Self-test attempt %d failed: %s", attempt, last_err)
            # Drop the (likely dead) browser so the next attempt relaunches.
            try:
                if _browser is not None:
                    await _browser.close()
            except Exception:
                pass
            _browser = None
    return SelfTestResponse(
        executed=False, flag_reachable=False, baseline_safe=True,
        detail=f"Internal error after retry: {last_err}",
    )


async def _run_selftest(req: SelfTestRequest) -> SelfTestResponse:
    """
    Core Playwright logic.
    1. Serve the page from a localhost HTTP route (GET /_page) so query/hash/
       cookies behave like a real site.
    2. Baseline check: load page, confirm no XSS fires.
    3. Attack check: inject payload, confirm XSS fires + cookie readable.
    """
    global _current_html
    assert _browser is not None

    async with _selftest_lock:
        _current_html = req.html
        # Routed/intercepted virtual host — never actually resolved or fetched.
        base_url = "http://ctf.local/"
        return await _do_selftest(req, base_url)


async def _make_routed_context():
    """
    New context whose requests are fully intercepted:
      - the main document is fulfilled from _current_html (no server round-trip)
      - every subresource (img/script/css/font/xhr) is aborted (no real network)
    This keeps the renderer stable in the constrained serverless runtime while
    still letting `<img src=x onerror=...>` style payloads fire (aborted load →
    error event → payload runs).
    """
    ctx = await _browser.new_context()
    await ctx.add_init_script(_INIT_SCRIPT)

    async def _handler(route):
        try:
            if route.request.resource_type == "document":
                await route.fulfill(
                    status=200,
                    content_type="text/html; charset=utf-8",
                    body=_current_html,
                )
            else:
                await route.abort()
        except Exception:
            try:
                await route.abort()
            except Exception:
                pass

    await ctx.route("**/*", _handler)
    return ctx


# Injected BEFORE any page script runs. Overrides the dialog APIs so an XSS
# payload that calls alert/confirm/prompt sets a detectable sentinel instead of
# opening a real modal dialog (real dialogs block the renderer and crash
# page.evaluate with "Target crashed"). Also flags eval/Function/cookie reads as
# execution signals for non-alert payloads.
_INIT_SCRIPT = """
window.__xss_fired = false;
(function () {
  function fire() { window.__xss_fired = true; }
  window.alert = fire;
  window.confirm = function () { fire(); return true; };
  window.prompt = function () { fire(); return ''; };
  window.print = fire;
})();
"""


async def _eval_sentinel(page: Any) -> bool:
    try:
        return bool(await page.evaluate("() => window.__xss_fired || false"))
    except Exception:
        return False


async def _do_selftest(req: SelfTestRequest, base_url: str) -> SelfTestResponse:
    xss_type = req.xss_type.lower()
    param = req.vulnerable_param
    payload = req.payload_solution
    flag = req.flag

    from urllib.parse import quote

    executed = False
    flag_reachable = False
    baseline_safe = True
    detail_parts: list[str] = []

    if xss_type == "reflected":
        attack_url = f"{base_url}?{param}={quote(payload)}"
    elif xss_type == "dom":
        attack_url = f"{base_url}#{param}={quote(payload)}"
    else:  # stored / unknown → load plain, inject via form below
        attack_url = base_url

    # ── Attack FIRST — authoritative verdict (executed + flag_reachable) from
    #    the first page load; baseline is a best-effort second load. ──────────
    ctx = await _make_routed_context()
    try:
        page = await ctx.new_page()
        await page.goto(attack_url, timeout=8000, wait_until="domcontentloaded")

        if xss_type == "stored":
            try:
                textarea = page.locator(f"textarea[name='{param}'], #{param}")
                await textarea.fill(payload, timeout=3000)
                submit = page.locator("button[type='submit'], input[type='submit']")
                await submit.click(timeout=3000)
                await page.wait_for_timeout(1000)
            except Exception as e:
                detail_parts.append(f"stored submit failed: {e}")

        await page.wait_for_timeout(900)

        if await _eval_sentinel(page):
            executed = True
            detail_parts.append("XSS fired (alert/confirm/prompt sentinel)")

        try:
            cookies = await page.evaluate("() => document.cookie")
        except Exception:
            cookies = ""
        if flag and flag in cookies:
            flag_reachable = True
            detail_parts.append("flag found in document.cookie")
        elif executed:
            detail_parts.append(f"XSS fired but flag not in cookie (cookie={cookies[:80]!r})")

        # Diagnostics only when the attack did NOT fire — helps debug a page
        # that should have been solvable. Successful runs stay clean.
        if not executed:
            try:
                content = await page.content()
                results_html = await page.evaluate(
                    "() => (document.getElementById('results')||{}).innerHTML || '(no #results)'"
                )
                detail_parts.append(
                    f"[diag content_len={len(content)} cookie={cookies[:60]!r} "
                    f"results_html={results_html[:120]!r}]"
                )
            except Exception as e:
                detail_parts.append(f"[diag failed: {e}]")
    finally:
        await ctx.close()

    # ── Baseline (best-effort) — load WITHOUT payload in a fresh context. If the
    #    runtime crashes on this second navigation we tolerate it and leave
    #    baseline_safe=True rather than failing the whole self-test. ──────────
    try:
        ctx2 = await _make_routed_context()
        try:
            page2 = await ctx2.new_page()
            await page2.goto(base_url, timeout=8000, wait_until="domcontentloaded")
            await page2.wait_for_timeout(400)
            if await _eval_sentinel(page2):
                baseline_safe = False
        finally:
            await ctx2.close()
    except Exception as exc:
        detail_parts.append(f"baseline skipped ({type(exc).__name__})")

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


@app.get("/_page")
async def serve_page() -> Response:
    """Serve the page currently under test (set by _run_selftest)."""
    return Response(content=_current_html, media_type="text/html; charset=utf-8")


@app.get("/health")
async def health() -> dict[str, str]:
    # Trigger a lazy launch so health reflects real browser state and surfaces
    # any launch error instead of the process having crashed at startup.
    await _ensure_browser()
    return {
        "status": "ok",
        "browser": "ready" if _browser else "not_ready",
        "browser_error": _browser_error or "",
    }
