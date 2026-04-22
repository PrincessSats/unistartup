"""
Translation service for CVE descriptions using Yandex Translate API.

Single-request batch translation: one REST call returns ru_title, ru_summary, ru_explainer.
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from openai import OpenAI

from app.config import settings
from app.services.ai_generator.llm_retry import http_call_with_retry_async, llm_call_with_retry

logger = logging.getLogger(__name__)

_TRANSLATE_ENDPOINT = "https://translate.api.cloud.yandex.net/translate/v2/translate"

_ENRICHMENT_SYSTEM = (
    "You are a technical security analyst. Given a CVE description, produce a JSON object with two keys:\n"
    '  "summary": a concise English summary of the vulnerability (1-3 sentences, 60-200 words).\n'
    '  "explainer": a detailed technical English explainer covering impact, root cause, and context (150-500 words).\n'
    "Respond ONLY with the raw JSON object, no markdown fences."
)

_MODEL_URI_MAP = {
    "deepseek": lambda folder: f"gpt://{folder}/deepseek-v32/latest",
    "qwen": lambda _: "gpt://b1goei423tq1phl6o0av/qwen3.5-35b-a3b-fp8/latest",
}

_LLM_CLIENT: Optional[OpenAI] = None


def _build_llm_client() -> OpenAI:
    global _LLM_CLIENT
    if _LLM_CLIENT is None:
        _LLM_CLIENT = OpenAI(
            api_key=(settings.YANDEX_CLOUD_API_KEY or "").strip(),
            base_url="https://llm.api.cloud.yandex.net/v1",
            timeout=120,
        )
    return _LLM_CLIENT


def _generate_enrichment_sync(raw_en_text: str, model_uri: str) -> tuple[str, str]:
    """Call LLM (sync) to produce (en_summary, en_explainer). Called via asyncio.to_thread."""
    client = _build_llm_client()
    response = llm_call_with_retry(lambda: client.chat.completions.create(
        model=model_uri,
        messages=[
            {"role": "system", "content": _ENRICHMENT_SYSTEM},
            {"role": "user", "content": raw_en_text[:8000]},
        ],
    ))
    content = (response.choices[0].message.content or "").strip()
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if content.rstrip().endswith("```"):
            content = content.rstrip()[:-3].rstrip()
    try:
        parsed = _json.loads(content)
        return str(parsed.get("summary", "")), str(parsed.get("explainer", ""))
    except _json.JSONDecodeError:
        return content[:300], content


@dataclass
class FullTranslationResult:
    """Complete translation result for a CVE entry."""
    ru_title: str
    ru_summary: str
    ru_explainer: str


class TranslationError(Exception):
    """Translation service error."""
    pass


class _YandexTranslateClient:
    """Thin async wrapper around Yandex Translate REST API."""

    def __init__(self, api_key: str, folder_id: str):
        self._api_key = api_key
        self._folder_id = folder_id
        self._http: Optional[httpx.AsyncClient] = None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def translate(self, texts: list[str]) -> list[str]:
        """Translate a batch of texts from EN to RU. Returns translated strings in same order."""
        payload = {
            "folderId": self._folder_id,
            "texts": texts,
            "targetLanguageCode": "ru",
            "sourceLanguageCode": "en",
            "format": "PLAIN_TEXT",
        }
        headers = {
            "Authorization": f"Api-Key {self._api_key}",
            "Content-Type": "application/json",
        }

        async def _post():
            r = await self._client().post(_TRANSLATE_ENDPOINT, json=payload, headers=headers)
            r.raise_for_status()
            return [t["text"] for t in r.json()["translations"]]

        return await http_call_with_retry_async(_post)

    async def close(self):
        if self._http:
            await self._http.aclose()
            self._http = None


class TranslationService:
    """Async translation service via Yandex Translate REST API."""

    def __init__(self):
        self.api_key = settings.YANDEX_CLOUD_API_KEY
        self.folder_id = settings.YANDEX_CLOUD_FOLDER
        self._translator: Optional[_YandexTranslateClient] = None

    def _get_translator(self) -> _YandexTranslateClient:
        if self._translator is None:
            if not self.api_key:
                raise TranslationError("YANDEX_CLOUD_API_KEY not configured")
            if not self.folder_id:
                raise TranslationError("YANDEX_CLOUD_FOLDER not configured")
            self._translator = _YandexTranslateClient(self.api_key, self.folder_id.strip())
        return self._translator

    async def translate_text(self, text: str, max_chars: int = 8000) -> str:
        """Translate a single text to Russian."""
        if not text or not text.strip():
            return ""
        try:
            results = await self._get_translator().translate([text[:max_chars]])
            return results[0].strip()
        except Exception as exc:
            raise TranslationError(f"Translation failed: {exc}")

    async def translate_cve_fields(
        self,
        cve_id: str,
        raw_en_text: str,
    ) -> tuple[str, str]:
        """Translate CVE title and summary (legacy method for backward compatibility)."""
        if not raw_en_text:
            return "", ""

        title_text = raw_en_text[:150].split(".")[0].strip() or raw_en_text[:100]

        try:
            results = await self._get_translator().translate([
                title_text,
                raw_en_text[:3000],
            ])
            ru_title, ru_summary = results[0].strip(), results[1].strip()
            logger.info("Translated CVE %s: title=%d chars, summary=%d chars",
                        cve_id, len(ru_title), len(ru_summary))
            return ru_title, ru_summary
        except Exception as exc:
            logger.warning("Translation failed for CVE %s: %s", cve_id, exc)
            return "", ""

    async def translate_full_cve(
        self,
        cve_id: str,
        raw_en_text: str,
        model: Optional[str] = None,
    ) -> FullTranslationResult:
        """Translate CVE to Russian. If model key given, LLM synthesises EN first, then Yandex Translate."""
        if not raw_en_text:
            return FullTranslationResult(ru_title="", ru_summary="", ru_explainer="")

        title_slice = raw_en_text[:150].split(".")[0].strip() or raw_en_text[:100]

        if model and model in _MODEL_URI_MAP:
            folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
            model_uri = _MODEL_URI_MAP[model](folder)
            try:
                en_summary, en_explainer = await asyncio.to_thread(
                    _generate_enrichment_sync, raw_en_text, model_uri
                )
            except Exception as exc:
                logger.warning(
                    "LLM enrichment failed for CVE %s (model=%s), using raw slices: %s",
                    cve_id, model, exc,
                )
                en_summary = raw_en_text[:3000]
                en_explainer = raw_en_text[:8000]
        else:
            en_summary = raw_en_text[:3000]
            en_explainer = raw_en_text[:8000]

        try:
            results = await self._get_translator().translate([
                title_slice,
                en_summary or raw_en_text[:3000],
                en_explainer or raw_en_text[:8000],
            ])
            result = FullTranslationResult(
                ru_title=results[0].strip(),
                ru_summary=results[1].strip(),
                ru_explainer=results[2].strip(),
            )
            logger.info(
                "Translated CVE %s (model=%s): title=%d, summary=%d, explainer=%d chars",
                cve_id, model or "raw", len(result.ru_title), len(result.ru_summary), len(result.ru_explainer),
            )
            return result
        except Exception as exc:
            logger.warning("Full translation failed for CVE %s: %s", cve_id, exc)
            return FullTranslationResult(ru_title="", ru_summary="", ru_explainer="")

    async def close(self):
        if self._translator:
            await self._translator.close()
