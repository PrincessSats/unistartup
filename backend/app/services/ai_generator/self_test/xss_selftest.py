"""
Клиент XSS self-test — вызывает Yandex Serverless Container с headless Chromium (Playwright),
чтобы убедиться, что сгенерированное XSS-задание реально разрешимо
до того, как оно пройдёт двоичные ворота SOLVABILITY.

Три сигнала, возвращаемых контейнером:
  executed        — внедрение payload_solution запускает JS (alert / sentinel)
  flag_reachable  — JS атакующего может прочитать document.cookie и получить флаг
  baseline_safe   — загрузка страницы без payload НЕ запускает XSS

Активен только при settings.AI_GEN_ENABLE_SELFTEST == True и
settings.AI_GEN_SELFTEST_URL задан. При любой ошибке контейнера/таймауте
функция переходит на статическую эвристику (fail-open) и записывает
деградацию в поле detail.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class XssSelfTestResult:
    executed: bool = False
    flag_reachable: bool = False
    baseline_safe: bool = True
    detail: str = ""
    error: Optional[str] = None
    # True, если результат получен от контейнера (не резервный/отключённый путь)
    is_live: bool = False


async def run_xss_self_test(html: str, spec: dict[str, Any]) -> XssSelfTestResult:
    """
    Отправить отрендеренный HTML + спек в Serverless Container для self-test.
    Возвращает XssSelfTestResult.

    Переходит на статическую эвристику (is_live=False) при:
      - AI_GEN_ENABLE_SELFTEST == False
      - AI_GEN_SELFTEST_URL не задан
      - Запрос к контейнеру превысил таймаут или вернул не-200
      - Любая другая сетевая/парсинговая ошибка
    """
    if not settings.AI_GEN_ENABLE_SELFTEST or not settings.AI_GEN_SELFTEST_URL.strip():
        return XssSelfTestResult(
            is_live=False,
            detail="Self-test disabled (AI_GEN_ENABLE_SELFTEST=False or URL not set)",
        )

    payload = {
        "html": html,
        "xss_type": spec.get("xss_type", "reflected"),
        "vulnerable_param": spec.get("vulnerable_param", "q"),
        "payload_solution": spec.get("payload_solution", ""),
        "flag": spec.get("flag", ""),
    }

    headers: dict[str, str] = {"Content-Type": "application/json"}
    # IAM-аутентификация Yandex Serverless Container — прикрепить SA-токен из env, если доступен
    iam_token = _get_iam_token()
    if iam_token:
        headers["Authorization"] = f"Bearer {iam_token}"

    url = settings.AI_GEN_SELFTEST_URL.rstrip("/") + "/selftest"
    timeout = float(settings.AI_GEN_SELFTEST_TIMEOUT_S)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    except httpx.TimeoutException as exc:
        logger.warning("XSS self-test timeout (%ss): %s", timeout, exc)
        return XssSelfTestResult(
            is_live=False,
            detail=f"Self-test timeout after {timeout}s — fallback to static heuristic",
            error=str(exc),
        )
    except httpx.HTTPStatusError as exc:
        logger.warning("XSS self-test HTTP error %s: %s", exc.response.status_code, exc)
        return XssSelfTestResult(
            is_live=False,
            detail=f"Self-test HTTP {exc.response.status_code} — fallback to static heuristic",
            error=str(exc),
        )
    except Exception as exc:
        logger.warning("XSS self-test unexpected error: %s", exc)
        return XssSelfTestResult(
            is_live=False,
            detail=f"Self-test error ({type(exc).__name__}) — fallback to static heuristic",
            error=str(exc),
        )

    executed = bool(data.get("executed", False))
    flag_reachable = bool(data.get("flag_reachable", False))
    baseline_safe = bool(data.get("baseline_safe", True))
    detail = str(data.get("detail", ""))

    logger.info(
        "XSS self-test: executed=%s flag_reachable=%s baseline_safe=%s detail=%r",
        executed, flag_reachable, baseline_safe, detail,
    )

    return XssSelfTestResult(
        executed=executed,
        flag_reachable=flag_reachable,
        baseline_safe=baseline_safe,
        detail=detail,
        is_live=True,
    )


def _get_iam_token() -> Optional[str]:
    """
    Вернуть IAM bearer-токен для вызова Yandex Serverless Container.
    Сначала пробует подход через metadata-сервер (экземпляр в Yandex Cloud),
    затем переходит на статическую переменную YANDEX_IAM_TOKEN из env.
    """
    import os
    static = os.environ.get("YANDEX_IAM_TOKEN", "").strip()
    if static:
        return static
    # Продакшн: получить из metadata-сервиса экземпляра (169.254.169.254)
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(req, timeout=1) as resp:
            import json as _json
            body = _json.loads(resp.read())
            return body.get("access_token") or body.get("token")
    except Exception:
        return None
