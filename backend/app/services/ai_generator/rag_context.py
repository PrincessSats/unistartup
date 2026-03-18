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

# Natural-language query templates per task type
_QUERY_TEMPLATES: dict[str, str] = {
    "crypto_text_web": "cryptographic cipher encoding decryption challenge web vulnerability",
    "forensics_image_metadata": "image metadata forensics file analysis hidden data steganography",
    "web_static_xss": "cross-site scripting XSS injection web vulnerability DOM HTML",
    "chat_llm": "prompt injection LLM manipulation AI security jailbreak",
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


@dataclass
class RAGContext:
    cve_entries: list[CVEEntry] = field(default_factory=list)
    existing_task_titles: list[str] = field(default_factory=list)
    last_nvd_sync: Optional[datetime] = None
    entry_ids: list[int] = field(default_factory=list)
    query_text: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.cve_entries

    def to_prompt_section(self) -> str:
        if self.is_empty:
            return ""

        lines: list[str] = [
            "## Контекст CVE (используй для обоснования задания)",
            "",
        ]
        for entry in self.cve_entries:
            title = entry.ru_title or entry.cve_id or "Неизвестно"
            lines.append(f"### {title}")
            if entry.cve_id:
                lines.append(f"- CVE: {entry.cve_id}")
            if entry.ru_summary:
                lines.append(f"- Описание: {entry.ru_summary}")
            elif entry.raw_en_text:
                snippet = entry.raw_en_text[:300].rstrip()
                lines.append(f"- Описание (EN): {snippet}...")
            if entry.tags:
                lines.append(f"- Теги: {', '.join(entry.tags)}")
            lines.append("")

        if self.existing_task_titles:
            lines.append("## Уже существующие задания (не дублируй их):")
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
                    "SELECT id, cve_id, ru_title, ru_summary, raw_en_text, tags, difficulty "
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
