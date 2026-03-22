"""
RAG context builder: semantic search over kb_entries via pgvector cosine distance.

RAGContext   — dataclass holding fetched CVE entries + metadata
RAGContextBuilder — builds RAGContext for a given generation request
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.contest import KBEntry, Task
from app.services.ai_generator.embedding_service import EmbeddingService, EmbeddingError

logger = logging.getLogger(__name__)

# Natural-language query templates per task type — expanded with domain context
_QUERY_TEMPLATES: dict[str, str] = {
    "crypto_text_web": (
        "cryptographic cipher encryption decryption weak algorithm key exchange "
        "authentication session token cookie network traffic interception man-in-the-middle "
        "TLS SSL HTTPS certificate RSA AES XOR base64 encoding web application API"
    ),
    "forensics_image_metadata": (
        "image metadata forensics EXIF JPEG PNG file analysis hidden data steganography "
        "digital evidence photo camera GPS location timestamp author copyright "
        "XMP IPTC file carving data recovery investigation crime scene"
    ),
    "web_static_xss": (
        "cross-site scripting XSS injection web vulnerability DOM manipulation "
        "innerHTML document.write eval script tag event handler onerror onclick "
        "reflected stored DOM-based CSP bypass filter evasion input validation "
        "web application form search comment user input sanitization"
    ),
    "chat_llm": (
        "prompt injection LLM manipulation AI security jailbreak system prompt "
        "social engineering token extraction data leakage conversation hijacking "
        "role play bypass instruction override chatbot assistant AI model "
        "natural language processing text generation response manipulation"
    ),
}

# Scenario templates: how to transform a CVE into a CTF challenge scenario per task type
_SCENARIO_TEMPLATES: dict[str, list[str]] = {
    "crypto_text_web": [
        (
            "Злоумышленник перехватил зашифрованное сообщение между двумя серверами. "
            "Используя уязвимость в криптографической реализации (описана в CVE), "
            "расшифруй сообщение и найди секретный флаг."
        ),
        (
            "Веб-приложение использует слабый алгоритм шифрования для сессионных токенов. "
            "CVE описывает эту уязвимость. Проанализируй перехваченные данные и восстанови оригинальный токен."
        ),
        (
            "В системе аутентификации обнаружена уязвимость в реализации ключевого обмена. "
            "Используя описание из CVE, атакуй протокол и получи доступ к защищённым данным."
        ),
        (
            "Злоумышленник внедрил backdoor в криптографическую библиотеку. "
            "CVE описывает механизм компрометации. Расшифруй перехваченное сообщение, используя известную уязвимость."
        ),
    ],
    "forensics_image_metadata": [
        (
            "При расследовании инцидента была найдена фотография, сделанная злоумышленником. "
            "CVE описывает уязвимость в обработке метаданных изображений. "
            "Извлеки скрытую информацию из файла."
        ),
        (
            "В ходе цифровой криминалистики обнаружено изображение с аномальными метаданными. "
            "Используя уязвимость из CVE, найди спрятанный флаг в служебных полях файла."
        ),
        (
            "Фотография с места утечки данных содержит скрытое сообщение в метаданных. "
            "CVE описывает метод сокрытия информации. Проанализируй файл и извлеки флаг."
        ),
        (
            "Подозрительное изображение было загружено на корпоративный портал. "
            "CVE указывает на возможность внедрения данных в метаданные. Исследуй файл."
        ),
    ],
    "web_static_xss": [
        (
            "Веб-приложение содержит уязвимость XSS, описанную в CVE. "
            "Используй её для выполнения JavaScript-кода и получения флага из cookie/localStorage."
        ),
        (
            "На странице поиска обнаружена reflected XSS уязвимость (CVE). "
            "Создай payload для выполнения кода и извлечения секретного токена."
        ),
        (
            "Форма комментариев на сайте уязвима к stored XSS (CVE). "
            "Внедри скрипт, который отправит флаг злоумышленнику."
        ),
        (
            "DOM-based XSS в обработке URL-параметров (CVE). "
            "Обойди фильтр и выполни код для получения флага из document.cookie."
        ),
    ],
    "chat_llm": [
        (
            "Чат-бот использует LLM с уязвимостью к prompt injection (CVE). "
            "Сформулируй запрос так, чтобы модель раскрыла системный промпт или секретный флаг."
        ),
        (
            "AI-ассистент содержит уязвимость jailbreak (CVE). "
            "Используй социальную инженерию для обхода ограничений и получения конфиденциальной информации."
        ),
        (
            "В обработке запросов LLM обнаружена уязвимость (CVE). "
            "Манипулируй входными данными для извлечения флага из контекста модели."
        ),
        (
            "Чат-бот хранит флаг в системном промпте. CVE описывает метод инъекции. "
            "Извлеки секретную информацию через серию запросов."
        ),
    ],
}


@dataclass
class CVEEntry:
    id: int
    cve_id: Optional[str]
    ru_title: Optional[str]
    ru_summary: Optional[str]
    raw_en_text: Optional[str]
    tags: list[str] = field(default_factory=list)
    difficulty: Optional[str] = None
    stored_embedding: Optional[list[float]] = None  # Pre-computed embedding vector from DB


@dataclass
class RAGContext:
    cve_entries: list[CVEEntry] = field(default_factory=list)
    existing_task_titles: list[str] = field(default_factory=list)
    last_nvd_sync: Optional[datetime] = None
    entry_ids: list[int] = field(default_factory=list)
    query_text: str = ""
    task_type: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.cve_entries

    def to_prompt_section(self) -> str:
        if self.is_empty:
            return ""

        lines: list[str] = [
            "## Контекст CVE — используй эти уязвимости как основу для сценария задания",
            "",
            "**ВАЖНО:** Не дублируй описание CVE один в один. Создай УНИКАЛЬНЫЙ сценарий,",
            "вдохновлённый этими уязвимостями. Используй примеры сценариев ниже.",
            "",
        ]

        # Add scenario templates for this task type
        scenario_templates = _SCENARIO_TEMPLATES.get(self.task_type, [])
        if scenario_templates:
            lines.append("### Примеры сценариев (используй как вдохновение)")
            for i, template in enumerate(scenario_templates, 1):
                lines.append(f"{i}. {template}")
            lines.append("")

        lines.append("### Найденные CVE (для технической конкретики)")
        for entry in self.cve_entries:
            title = entry.ru_title or entry.cve_id or "Неизвестно"
            lines.append(f"#### {title}")
            if entry.cve_id:
                lines.append(f"- **CVE ID:** {entry.cve_id}")
            if entry.ru_summary:
                lines.append(f"- **Описание:** {entry.ru_summary}")
            elif entry.raw_en_text:
                snippet = entry.raw_en_text[:300].rstrip()
                lines.append(f"- **Описание (EN):** {snippet}...")
            if entry.tags:
                lines.append(f"- **Теги:** {', '.join(entry.tags)}")
            lines.append("")

        if self.existing_task_titles:
            lines.append("## Уже существующие задания (НЕ дублируй их)")
            for title in self.existing_task_titles[:10]:
                lines.append(f"- {title}")
            lines.append("")

        if self.last_nvd_sync:
            lines.append(f"_Данные NVD последний раз синхронизированы: {self.last_nvd_sync.strftime('%Y-%m-%d %H:%M UTC')}_")
            lines.append("")

        return "\n".join(lines)


class RAGContextBuilder:
    def __init__(self, db: AsyncSession, context_limit: Optional[int] = None) -> None:
        self._db = db
        self._limit = context_limit or settings.AI_GEN_RAG_CONTEXT_LIMIT
        self._svc: Optional[EmbeddingService] = None  # created lazily in build_context

    async def build_context(
        self,
        task_type: str,
        difficulty: str,
        specific_cve: Optional[str] = None,
        specific_topic: Optional[str] = None,
    ) -> RAGContext:
        """Build a RAGContext for the generation request."""
        try:
            self._svc = EmbeddingService()
        except EmbeddingError as exc:
            logger.warning("EmbeddingService unavailable, skipping RAG: %s", exc)
            return RAGContext()

        try:
            if specific_cve:
                cve_entries = await self._fetch_specific_cve(specific_cve)
                query_text = specific_cve
            else:
                query_text = self._build_query(task_type, difficulty, specific_topic)
                try:
                    query_vector = await self._svc.embed_query(query_text)
                    cve_entries = await self._semantic_search_cves(query_vector)
                except EmbeddingError as exc:
                    logger.warning("Embedding failed, RAG context will be empty: %s", exc)
                    cve_entries = []

            existing_titles = await self._fetch_existing_tasks(task_type)
            last_sync = await self._get_last_nvd_sync()

            return RAGContext(
                cve_entries=cve_entries,
                existing_task_titles=existing_titles,
                last_nvd_sync=last_sync,
                entry_ids=[e.id for e in cve_entries],
                query_text=query_text,
                task_type=task_type,
            )
        except Exception as exc:
            logger.warning("RAG context build failed: %s", exc)
            return RAGContext()
        finally:
            await self._svc.close()

    def _build_query(self, task_type: str, difficulty: str, topic: Optional[str]) -> str:
        base = _QUERY_TEMPLATES.get(task_type, task_type.replace("_", " "))
        parts = [base]
        if difficulty:
            parts.append(difficulty)
        if topic:
            parts.append(topic)
        return " ".join(parts)

    async def _semantic_search_cves(self, query_vector: list[float]) -> list[CVEEntry]:
        """Find closest kb_entries by cosine distance (requires pgvector)."""
        try:
            result = await self._db.execute(
                text(
                    "SELECT id, cve_id, ru_title, ru_summary, raw_en_text, tags, difficulty, embedding "
                    "FROM kb_entries "
                    "WHERE embedding IS NOT NULL "
                    "ORDER BY embedding <=> CAST(:vec AS vector) "
                    "LIMIT :lim"
                ),
                {"vec": str(query_vector), "lim": self._limit},
            )
            rows = result.fetchall()
        except Exception as exc:
            logger.warning("pgvector search failed: %s", exc)
            return []

        return [
            CVEEntry(
                id=row.id,
                cve_id=row.cve_id,
                ru_title=row.ru_title,
                ru_summary=row.ru_summary,
                raw_en_text=row.raw_en_text,
                tags=row.tags or [],
                difficulty=row.difficulty,
                stored_embedding=list(row.embedding) if row.embedding else None,
            )
            for row in rows
        ]

    async def _fetch_specific_cve(self, cve_id: str) -> list[CVEEntry]:
        result = await self._db.execute(
            select(KBEntry).where(KBEntry.cve_id == cve_id).limit(1)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            logger.warning("CVE %s not found in kb_entries", cve_id)
            return []
        return [
            CVEEntry(
                id=entry.id,
                cve_id=entry.cve_id,
                ru_title=entry.ru_title,
                ru_summary=entry.ru_summary,
                raw_en_text=entry.raw_en_text,
                tags=entry.tags or [],
                difficulty=entry.difficulty,
                stored_embedding=list(entry.embedding) if entry.embedding else None,
            )
        ]

    async def _fetch_existing_tasks(self, task_type: str) -> list[str]:
        category = task_type.split("_")[0].capitalize()
        result = await self._db.execute(
            select(Task.title)
            .where(Task.category == category, Task.state != "archived")
            .order_by(Task.created_at.desc())
            .limit(20)
        )
        return [row[0] for row in result.fetchall()]

    async def _get_last_nvd_sync(self) -> Optional[datetime]:
        try:
            result = await self._db.execute(
                text("SELECT MAX(fetched_at) FROM nvd_sync_log WHERE status = 'success'")
            )
            row = result.fetchone()
            return row[0] if row and row[0] else None
        except Exception:
            return None
