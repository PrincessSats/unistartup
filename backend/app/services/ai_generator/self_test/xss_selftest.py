"""
XSS self-test client — calls the Yandex Serverless Container that runs
headless Chromium (Playwright) to verify a generated XSS task is genuinely
solvable before it passes the SOLVABILITY binary gate.

Three signals returned by the container:
  executed        — injecting payload_solution fires JS (alert / sentinel)
  flag_reachable  — attacker JS can read document.cookie and get the flag
  baseline_safe   — loading the page without payload does NOT fire XSS

Only active when settings.AI_GEN_ENABLE_SELFTEST is True and
settings.AI_GEN_SELFTEST_URL is set.  On any container error/timeout the
function falls back to static heuristic (fail-open) and records the
degradation in the detail field.
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
    # True when the result came from the container (not a fallback/disabled path)
    is_live: bool = False


async def run_xss_self_test(html: str, spec: dict[str, Any]) -> XssSelfTestResult:
    """
    Send the rendered HTML + spec to the self-test Serverless Container.
    Returns XssSelfTestResult.

    Falls back to static heuristic (is_live=False) when:
      - AI_GEN_ENABLE_SELFTEST is False
      - AI_GEN_SELFTEST_URL is not set
      - Container request times out or returns a non-200
      - Any other network/parse error
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
    # Yandex Serverless Container IAM auth — attach SA token from env if available
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
    Return IAM bearer token for Yandex Serverless Container invocation.
    Tries metadata-server approach (instance running in Yandex Cloud) first,
    then falls back to static YANDEX_IAM_TOKEN env var if present.
    """
    import os
    static = os.environ.get("YANDEX_IAM_TOKEN", "").strip()
    if static:
        return static
    # Production: fetch from instance metadata service (169.254.169.254)
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
