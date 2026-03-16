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

    async def _embed(self, text: str, model_type: str) -> list[float]:
        payload = {
            "modelUri": self._model_uri(model_type),
            "text": text,
        }
        client = self._get_client()
        try:
            resp = await client.post(_EMBEDDING_URL, headers=self._headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding", [])
            if not embedding:
                raise EmbeddingError(f"Empty embedding returned for model_type={model_type!r}")
            return embedding
        except httpx.HTTPStatusError as exc:
            raise EmbeddingError(f"Yandex embedding API error {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise EmbeddingError(f"Yandex embedding request failed: {exc}") from exc

    async def embed_document(self, text: str) -> list[float]:
        """Embed a document (kb_entry body, task description) for indexing."""
        return await self._embed(text, "text-search-doc")

    async def embed_query(self, query: str) -> list[float]:
        """Embed a retrieval query for semantic search."""
        return await self._embed(query, "text-search-query")

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
