"""Retry helpers for Yandex Cloud LLM calls (503/429) and REST HTTP calls."""
import asyncio
import logging
import time
from typing import Callable, TypeVar

import httpx
from openai import APIStatusError

logger = logging.getLogger(__name__)

T = TypeVar("T")

_DEFAULT_RETRIES = 3
_BASE_DELAY = 5.0


def llm_call_with_retry(fn: Callable[[], T], max_retries: int = _DEFAULT_RETRIES) -> T:
    delay = _BASE_DELAY
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except APIStatusError as exc:
            if exc.status_code == 503 and attempt < max_retries:
                logger.warning(
                    "Yandex LLM 503 server_overloaded (attempt %d/%d), retry in %.0fs",
                    attempt + 1, max_retries, delay,
                )
                time.sleep(delay)
                delay *= 2
                continue
            raise


async def llm_call_with_retry_async(fn: Callable, max_retries: int = _DEFAULT_RETRIES):
    delay = _BASE_DELAY
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except APIStatusError as exc:
            if exc.status_code == 503 and attempt < max_retries:
                logger.warning(
                    "Yandex LLM 503 server_overloaded (attempt %d/%d), retry in %.0fs",
                    attempt + 1, max_retries, delay,
                )
                await asyncio.sleep(delay)
                delay *= 2
                continue
            raise


_RETRYABLE_HTTP = {429, 500, 502, 503, 504}


async def http_call_with_retry_async(fn: Callable, max_retries: int = _DEFAULT_RETRIES):
    """Retry helper for httpx-based REST calls. Retries on 429/5xx and transport errors."""
    delay = _BASE_DELAY
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in _RETRYABLE_HTTP and attempt < max_retries:
                logger.warning(
                    "HTTP %d (attempt %d/%d), retry in %.0fs",
                    exc.response.status_code, attempt + 1, max_retries, delay,
                )
                await asyncio.sleep(delay)
                delay *= 2
                continue
            raise
        except httpx.TransportError as exc:
            if attempt < max_retries:
                logger.warning(
                    "Transport error (attempt %d/%d), retry in %.0fs: %s",
                    attempt + 1, max_retries, delay, exc,
                )
                await asyncio.sleep(delay)
                delay *= 2
                continue
            raise
