"""
Translation service for CVE descriptions using Yandex Cloud LLM (deepseek-v32).

Provides async translation of English text to Russian for kb_entries.
Uses deepseek-v32 model for high-quality full translation (title + summary + explainer).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

TRANSLATION_SYSTEM_PROMPT = """Ты — профессиональный технический переводчик в области кибербезопасности. Переведи текст уязвимости CVE с английского на русский.

Требования:
- Оставляй CVE ID, технические термины и акронимы на английском (например, "CVE-2024-1234", "XSS", "SQL injection", "API", "HTTP")
- Переводи только описательный текст
- Делай перевод точным, полным и профессиональным
- Сохраняй структуру оригинала (абзацы, списки)
- Выводи ТОЛЬКО перевод, без дополнительных комментариев
"""

TRANSLATION_MODEL_ID = "deepseek-v32"
TRANSLATION_MODEL_VERSION = "latest"


@dataclass
class FullTranslationResult:
    """Complete translation result for a CVE entry."""
    ru_title: str
    ru_summary: str
    ru_explainer: str


class TranslationError(Exception):
    """Translation service error."""
    pass


class TranslationService:
    """Async translation service using deepseek-v32 via Yandex Cloud OpenAI-compatible API."""

    def __init__(self):
        self.api_key = settings.YANDEX_CLOUD_API_KEY
        self.folder_id = settings.YANDEX_CLOUD_FOLDER
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Lazy client initialization."""
        if self._client is None:
            if not self.api_key:
                raise TranslationError("YANDEX_CLOUD_API_KEY not configured")
            if not self.folder_id:
                raise TranslationError("YANDEX_CLOUD_FOLDER not configured")
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://llm.api.cloud.yandex.net/v1",
                project=self.folder_id,
            )
        return self._client

    async def translate_text(self, text: str, max_chars: int = 8000) -> str:
        """
        Translate text to Russian using deepseek-v32.

        Args:
            text: Text to translate (English)
            max_chars: Maximum characters to translate (default: 8000)

        Returns:
            Translated text (Russian)

        Raises:
            TranslationError: If translation fails
        """
        if not text or not text.strip():
            return ""

        client = self._get_client()
        folder = self.folder_id.strip()
        model = f"gpt://{folder}/{TRANSLATION_MODEL_ID}/{TRANSLATION_MODEL_VERSION}"

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Переведи на русский:\n\n{text[:max_chars]}"},
                ],
                temperature=0.1,  # Low temperature for consistent translation
            )
            translated = (response.choices[0].message.content or "").strip()
            
            # Remove any prefix that the model might add
            if translated.lower().startswith("перевод:"):
                translated = translated[8:].strip()
            if translated.lower().startswith("translation:"):
                translated = translated[12:].strip()
            # Remove leading/trailing quotes
            translated = translated.strip('"').strip("'")
            
            logger.debug("Translated %d chars → %d chars", len(text), len(translated))
            return translated
            
        except Exception as exc:
            raise TranslationError(f"Translation failed: {exc}")

    async def translate_cve_fields(
        self,
        cve_id: str,
        raw_en_text: str,
    ) -> tuple[str, str]:
        """
        Translate CVE title and summary (legacy method for backward compatibility).

        Returns:
            Tuple of (ru_title, ru_summary)
        """
        if not raw_en_text:
            return "", ""

        # Extract title (first sentence or first 150 chars)
        title_text = raw_en_text[:150].split(".")[0].strip()
        if not title_text:
            title_text = raw_en_text[:100]

        try:
            # Translate title and summary in parallel
            ru_title_task = self.translate_text(title_text)
            ru_summary_task = self.translate_text(raw_en_text[:3000])

            ru_title, ru_summary = await asyncio.gather(
                ru_title_task,
                ru_summary_task,
                return_exceptions=False,
            )

            logger.info("Translated CVE %s: title=%d chars, summary=%d chars",
                       cve_id, len(ru_title), len(ru_summary))
            return ru_title.strip(), ru_summary.strip()

        except Exception as exc:
            logger.warning("Translation failed for CVE %s: %s", cve_id, exc)
            return "", ""

    async def translate_full_cve(
        self,
        cve_id: str,
        raw_en_text: str,
    ) -> FullTranslationResult:
        """
        Translate full CVE entry: title + summary + explainer (full content).

        Strategy:
        - Title: First sentence (short, ~150 chars)
        - Summary: First 3000 chars of description
        - Explainer: Full remaining content (up to 8000 chars)

        Returns:
            FullTranslationResult with ru_title, ru_summary, ru_explainer
        """
        if not raw_en_text:
            return FullTranslationResult(ru_title="", ru_summary="", ru_explainer="")

        # Extract title (first sentence)
        title_text = raw_en_text[:150].split(".")[0].strip()
        if not title_text:
            title_text = raw_en_text[:100]

        # Summary: first 3000 chars
        summary_text = raw_en_text[:3000]

        # Explainer: full text (for detailed technical explanation)
        explainer_text = raw_en_text[:8000]

        try:
            # Translate all three fields in parallel
            ru_title_task = self.translate_text(title_text)
            ru_summary_task = self.translate_text(summary_text)
            ru_explainer_task = self.translate_text(explainer_text, max_chars=8000)

            ru_title, ru_summary, ru_explainer = await asyncio.gather(
                ru_title_task,
                ru_summary_task,
                ru_explainer_task,
                return_exceptions=False,
            )

            logger.info(
                "Translated full CVE %s: title=%d, summary=%d, explainer=%d chars",
                cve_id, len(ru_title), len(ru_summary), len(ru_explainer),
            )
            return FullTranslationResult(
                ru_title=ru_title.strip(),
                ru_summary=ru_summary.strip(),
                ru_explainer=ru_explainer.strip(),
            )

        except Exception as exc:
            logger.warning("Full translation failed for CVE %s: %s", cve_id, exc)
            return FullTranslationResult(ru_title="", ru_summary="", ru_explainer="")

    async def close(self):
        if self._client:
            await self._client.close()
