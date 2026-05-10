"""
Yandex text-search embedding service.

Uses the asymmetric text-search-doc / text-search-query pair:
  - text-search-doc   → for indexing documents (kb_entries, tasks)
  - text-search-query → for retrieval queries (RAG search)

Model URI format: emb://{folder_id}/{model_type}/latest
API: https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_EMBEDDING_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding"
_MIN_RETRY_CHARS = 1000


class EmbeddingError(RuntimeError):
    pass


class EmbeddingService:
    def __init__(self) -> None:
        api_key = (settings.YANDEX_CLOUD_API_KEY or "").strip()
        folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
        if not api_key or not folder:
            raise EmbeddingError(
                "YANDEX_CLOUD_API_KEY and YANDEX_CLOUD_FOLDER must be set for embedding service"
            )
        self._folder = folder
        self._headers = {
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json",
        }
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._client

    def _model_uri(self, model_type: str) -> str:
        return f"emb://{self._folder}/{model_type}/latest"

    @staticmethod
    def _normalize_text(text: str, max_chars: int) -> str:
        normalized = " ".join((text or "").split())
        if len(normalized) <= max_chars:
            return normalized

        clipped = normalized[:max_chars].rsplit(" ", 1)[0].strip()
        return clipped or normalized[:max_chars].strip()

    def _candidate_texts(self, text: str) -> list[str]:
        max_chars = max(_MIN_RETRY_CHARS, int(settings.AI_GEN_EMBEDDING_MAX_CHARS))
        limits = [max_chars, max(_MIN_RETRY_CHARS, max_chars // 2), _MIN_RETRY_CHARS]
        candidates: list[str] = []
        for limit in limits:
            candidate = self._normalize_text(text, limit)
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        return candidates

    async def _embed(self, text: str, model_type: str) -> list[float]:
        candidates = self._candidate_texts(text)
        if not candidates:
            raise EmbeddingError("Empty text for embedding")

        client = self._get_client()
        last_token_limit_error: Optional[httpx.HTTPStatusError] = None
        for index, candidate in enumerate(candidates):
            payload = {
                "modelUri": self._model_uri(model_type),
                "text": candidate,
            }
            try:
                resp = await client.post(_EMBEDDING_URL, headers=self._headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                embedding = data.get("embedding", [])
                if not embedding:
                    raise EmbeddingError(f"Empty embedding returned for model_type={model_type!r}")
                if len(candidate) < len(" ".join((text or "").split())):
                    logger.debug(
                        "Embedding input truncated for model_type=%s to %d chars",
                        model_type,
                        len(candidate),
                    )
                return [float(value) for value in embedding]
            except httpx.HTTPStatusError as exc:
                body = exc.response.text or ""
                if (
                    exc.response.status_code == 400
                    and "number of input tokens" in body
                    and index < len(candidates) - 1
                ):
                    last_token_limit_error = exc
                    continue
                raise EmbeddingError(
                    f"Yandex embedding API error {exc.response.status_code}: {body}"
                ) from exc
            except httpx.RequestError as exc:
                raise EmbeddingError(f"Yandex embedding request failed: {exc}") from exc

        if last_token_limit_error is not None:
            raise EmbeddingError(
                "Yandex embedding API token limit exceeded after truncation: "
                f"{last_token_limit_error.response.text}"
            ) from last_token_limit_error
        raise EmbeddingError("Yandex embedding failed")

    async def embed_document(self, text: str) -> list[float]:
        """Embed a document (kb_entry body, task description) for indexing."""
        return await self._embed(text, "text-search-doc")

    async def embed_query(self, query: str) -> list[float]:
        """Embed a retrieval query for semantic search."""
        return await self._embed(query, "text-search-query")

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
