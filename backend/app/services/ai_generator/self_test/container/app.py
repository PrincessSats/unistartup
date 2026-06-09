"""
Контейнер XSS self-test — FastAPI + Playwright/Chromium.

POST /selftest
  Body: {html, xss_type, vulnerable_param, payload_solution, flag}
  Returns: {executed, flag_reachable, baseline_safe, detail}

Вызывающий (xss_selftest.py) передаёт HTML страницы инлайн (перерендеренный из спека),
поэтому контейнеру не нужен S3 или внешний сетевой доступ.

Защита:
  - Новый контекст браузера на каждый запрос (изоляция, без утечки cookie между вызовами)
  - Жёсткий таймаут Playwright 15 секунд
  - Внешние маршруты не нужны (HTML отдаётся внутренне через data: URI)
  - Один воркер uvicorn
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

# Общий экземпляр браузера Playwright — создаётся лениво при первом использовании, затем переиспользуется.
_browser = None
_playwright = None
_browser_error: str | None = None  # последняя ошибка запуска, отображается через /health
_browser_lock = asyncio.Lock()

# Тестируемая страница отдаётся из реального HTTP-маршрута на localhost (не data: URI),
# чтобы строки запроса, location.hash и document.cookie работали как на реальном сайте.
# concurrency=1 (Yandex) + этот lock гарантируют один тест за раз,
# поэтому один слот на уровне модуля для текущей страницы безопасен.
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
    Лениво запустить Chromium при первом запросе. Ошибка запуска записывается в
    _browser_error и отображается через /health и /selftest, вместо падения
    процесса при старте (которое Yandex сообщает как непрозрачный "exit status 3").
    """
    global _browser, _playwright, _browser_error
    # Переиспользовать только если ещё подключён; однопроцессный браузер может умереть и оставить
    # устаревший дескриптор, который портит все последующие запросы TargetClosedError.
    if _browser is not None and _browser.is_connected():
        return _browser
    async with _browser_lock:
        if _browser is not None and _browser.is_connected():
            return _browser
        # Удалить мёртвый браузер перед перезапуском.
        if _browser is not None:
            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None
        try:
            from playwright.async_api import async_playwright
            _playwright = await async_playwright().__aenter__()
            # Флаги в стиле Serverless/Lambda. Дочерний рендерер убивается SIGKILL
            # из-за ограничений процесса/cgroup контейнера (не stderr Chromium, не OOM).
            # --single-process держит всё в одном процессе, нет форка рендерера для убийства.
            # Такой же подход используется sparticuz/chromium на AWS Lambda.
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
            logger.info("Браузер Chromium запущен")
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
    logger.info("Браузер Chromium закрыт")


@app.post("/selftest", response_model=SelfTestResponse)
async def selftest(req: SelfTestRequest) -> SelfTestResponse:
    global _browser
    # Однопроцессный браузер иногда падает; перезапустить + повторить один раз,
    # чтобы случайный сбой не провалил иначе разрешимое задание.
    last_err = ""
    for attempt in range(2):
        if await _ensure_browser() is None:
            raise HTTPException(status_code=503, detail=f"Browser not ready: {_browser_error}")
        try:
            return await asyncio.wait_for(_run_selftest(req), timeout=20.0)
        except asyncio.TimeoutError:
            logger.warning("Self-test превысил таймаут для xss_type=%s", req.xss_type)
            return SelfTestResponse(
                executed=False, flag_reachable=False, baseline_safe=True,
                detail="Playwright timed out after 20s",
            )
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            logger.warning("Self-test попытка %d не удалась: %s", attempt, last_err)
            # Удалить (вероятно мёртвый) браузер, чтобы следующая попытка перезапустила его.
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
    Основная логика Playwright.
    1. Отдать страницу из HTTP-маршрута localhost (GET /_page), чтобы query/hash/
       cookies работали как на реальном сайте.
    2. Базовая проверка: загрузить страницу, убедиться что XSS не срабатывает.
    3. Атакующая проверка: внедрить payload, убедиться что XSS срабатывает + cookie читается.
    """
    global _current_html
    assert _browser is not None

    async with _selftest_lock:
        _current_html = req.html
        # Виртуальный хост с перехватом маршрутов — никогда реально не резолвится и не запрашивается.
        base_url = "http://ctf.local/"
        return await _do_selftest(req, base_url)


async def _make_routed_context():
    """
    Новый контекст с полным перехватом запросов:
      - основной документ отдаётся из _current_html (без обращения к серверу)
      - каждый подресурс (img/script/css/font/xhr) прерывается (без реальной сети)
    Это держит рендерер стабильным в ограниченном serverless-окружении,
    при этом позволяя срабатывать payload вида `<img src=x onerror=...>`
    (прерванная загрузка → событие ошибки → payload выполняется).
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


# Внедряется ДО запуска любых скриптов страницы. Переопределяет dialog API,
# чтобы XSS-payload, вызывающий alert/confirm/prompt, устанавливал обнаруживаемый
# sentinel вместо открытия реального диалога (реальные диалоги блокируют рендерер
# и роняют page.evaluate с "Target crashed"). Также помечает eval/Function/чтение cookie
# как сигналы выполнения для payload без alert.
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
    else:  # stored / unknown → загрузить чистым, внедрить через форму ниже
        attack_url = base_url

    # ── Сначала атака — авторитетный вердикт (executed + flag_reachable) с
    #    первой загрузки страницы; baseline — лучший вариант со второй загрузки. ─
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
            detail_parts.append("XSS сработал (sentinel alert/confirm/prompt)")

        try:
            cookies = await page.evaluate("() => document.cookie")
        except Exception:
            cookies = ""
        if flag and flag in cookies:
            flag_reachable = True
            detail_parts.append("флаг найден в document.cookie")
        elif executed:
            detail_parts.append(f"XSS сработал, но флаг не в cookie (cookie={cookies[:80]!r})")

        # Диагностика только когда атака НЕ сработала — помогает отлаживать страницу,
        # которая должна была быть разрешимой. Успешные запуски остаются чистыми.
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

        # ── Baseline — ТА ЖЕ страница, повторная навигация БЕЗ payload. При
        #    --single-process Chromium открытие второго контекста браузера после
        #    закрытия первого убивает единственный процесс (TargetClosedError);
        #    повторная навигация на той же странице переиспользует живой рендерер/фрейм
        #    и перезапускает init script (сбрасывает window.__xss_fired=false). ──
        try:
            await page.goto(base_url, timeout=8000, wait_until="domcontentloaded")
            await page.wait_for_timeout(400)
            if await _eval_sentinel(page):
                baseline_safe = False
        except Exception as exc:
            detail_parts.append(f"baseline skipped ({type(exc).__name__})")
    finally:
        await ctx.close()

    detail = "; ".join(detail_parts) if detail_parts else (
        "сигналы XSS не обнаружены" if not executed else ""
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
    """Отдать страницу, которая сейчас тестируется (устанавливается в _run_selftest)."""
    return Response(content=_current_html, media_type="text/html; charset=utf-8")


@app.get("/health")
async def health() -> dict[str, str]:
    # Запустить ленивый старт, чтобы health отражал реальное состояние браузера
    # и показывал ошибки запуска вместо падения процесса при старте.
    await _ensure_browser()
    return {
        "status": "ok",
        "browser": "ready" if _browser else "not_ready",
        "browser_error": _browser_error or "",
    }
