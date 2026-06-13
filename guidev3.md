# CLAUDE.md — AI Generator Implementation Checklist (v3 with pgvector RAG)

## Context

You are implementing an AI-powered CTF challenge generator for the HackNet platform.
The system uses a GRPO-inspired pipeline (adapted from DeepSeek-R1, arXiv:2501.12948):
- **Semantic RAG via pgvector**: Planner embeds the generation query using Yandex text-search API, then pulls the most semantically similar CVEs/vulnerabilities from kb_entries via cosine distance — no keyword matching, no synonym mappings
- Generate N variant specs in parallel with different temperatures
- Create artifacts deterministically from specs
- Score each variant with rule-based binary checks + LLM-as-judge quality
- Compute group-relative advantages: Â_i = (r_i - mean) / std
- Reject variants that fail any binary check
- Select best variant by highest advantage among passed
- Store ALL results (winners AND losers) with failure reasons
- Feed failure patterns back as negative few-shot in future generations

## Existing Infrastructure (DO NOT modify unless noted)

```
backend/app/main.py          — FastAPI app, add router registration here
backend/app/config.py        — pydantic-settings, add new env vars here
backend/app/database.py      — async SQLAlchemy engine + session
backend/app/routes/           — existing routes (auth, education, knowledge, etc.)
backend/app/services/         — existing services (task_generation, chat_task, storage, prompt_loader, nvd_sync)
backend/app/models/           — existing SQLAlchemy ORM models
backend/app/schemas/          — existing Pydantic schemas
backend/app/auth/             — JWT dependencies (get_current_user)
schema.sql                    — existing DB schema
```

Key existing patterns:
- LLM calls use OpenAI SDK (`from openai import AsyncOpenAI`)
- S3 uploads use existing `storage.py` service
- DB sessions via `async_sessionmaker`, dependency injection
- Prompts stored in `prompt_templates` table, loaded via `prompt_loader.py`
- Chat challenges use `task_chat_sessions` + `task_chat_messages` tables

**Existing tables relevant to RAG (already in schema.sql):**
- `kb_entries` — knowledge base articles, many are CVE-related. Has columns: id, title, content, category, tags, cve_id, severity, published_at
- `nvd_sync_log` — log of NVD synchronization runs
- `tasks` — existing challenges (to check for duplicates)

**Existing services relevant to RAG:**
- `nvd_sync.py` — syncs CVE data from NVD API into kb_entries. Runs periodically.

**Yandex Cloud credentials already configured:**
- `YANDEX_CLOUD_API_KEY` — used for YandexGPT, also works for embeddings API
- `YANDEX_CLOUD_FOLDER` — folder ID for Yandex Cloud services

---

## Phase 1: Database Schema + Config + pgvector

### Step 1.1: Add environment variables to config.py

Add to the existing `Settings` class in `backend/app/config.py`:

```python
# AI Generator settings
AI_GEN_MODEL: str = "yandexgpt"              # yandexgpt | vllm_qwen | vllm_deepseek
AI_GEN_VLLM_URL: str = ""                    # http://vllm-server:8000/v1 (when using self-hosted)
AI_GEN_NUM_VARIANTS: int = 5                 # N in best-of-N generation
AI_GEN_MAX_RETRIES: int = 2                  # retry whole batch if all fail
AI_GEN_MIN_REWARD_THRESHOLD: float = 0.6     # minimum total_reward to publish
AI_GEN_BASE_TEMPERATURE: float = 0.7         # lowest temperature in the spread
AI_GEN_TEMPERATURE_STEP: float = 0.1         # increment per variant
AI_GEN_RAG_CONTEXT_LIMIT: int = 5            # max KB entries to pull per generation
AI_GEN_EMBEDDING_DIMENSION: int = 256        # Yandex text-search embedding dimension
```

### Step 1.2: Create migration SQL

Create new file: `backend/migrations/add_ai_generation_tables.sql`

```sql
-- ══════════════════════════════════════════════════
-- pgvector extension + embedding column on kb_entries
-- ══════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to existing kb_entries table.
-- Yandex text-search models produce 256-dimensional vectors.
-- This column will be NULL for entries not yet embedded.
ALTER TABLE kb_entries ADD COLUMN IF NOT EXISTS embedding vector(256);

-- HNSW index for fast cosine similarity search.
-- HNSW is preferred over IVFFlat: no training step, better recall, good enough speed for <100K rows.
-- vector_cosine_ops = cosine distance operator (lower = more similar).
CREATE INDEX IF NOT EXISTS idx_kb_entries_embedding
    ON kb_entries USING hnsw (embedding vector_cosine_ops);

-- Also add embedding to tasks table for duplicate detection via similarity.
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS embedding vector(256);
CREATE INDEX IF NOT EXISTS idx_tasks_embedding
    ON tasks USING hnsw (embedding vector_cosine_ops);

-- ══════════════════════════════════════════════════
-- AI generation tables
-- ══════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ai_generation_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requested_by INTEGER REFERENCES users(id),
    task_type VARCHAR(50) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    num_variants INTEGER NOT NULL DEFAULT 5,
    attempt INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- RAG context: which kb_entries were used + the text sent to LLM
    rag_context_ids INTEGER[],
    rag_context_summary TEXT,
    rag_query_text TEXT,                  -- the semantic query used for embedding search
    -- GRPO group stats
    group_mean_reward FLOAT,
    group_std_reward FLOAT,
    pass_rate FLOAT,
    -- Result
    selected_variant_id UUID,
    failure_reasons_summary JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ai_generation_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES ai_generation_batches(id) ON DELETE CASCADE,
    variant_number INTEGER NOT NULL,
    -- Generation params
    model_used VARCHAR(100),
    temperature FLOAT,
    tokens_input INTEGER,
    tokens_output INTEGER,
    generation_time_ms INTEGER,
    -- LLM output
    generated_spec JSONB,
    -- Artifact result
    artifact_result JSONB,
    -- Reward scoring (GRPO core)
    reward_checks JSONB,
    reward_total FLOAT,
    reward_binary FLOAT,
    passed_all_binary BOOLEAN DEFAULT false,
    -- LLM quality assessment
    quality_score FLOAT,
    quality_details JSONB,
    -- GRPO group-relative
    advantage FLOAT,
    rank_in_group INTEGER,
    -- Selection
    is_selected BOOLEAN DEFAULT false,
    published_task_id INTEGER REFERENCES tasks(id),
    -- Failure tracking
    failure_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_generation_analytics (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    period_date DATE NOT NULL,
    total_variants INTEGER DEFAULT 0,
    passed_variants INTEGER DEFAULT 0,
    avg_reward FLOAT,
    avg_quality_score FLOAT,
    common_failures JSONB,
    best_temperature FLOAT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(task_type, difficulty, period_date)
);

CREATE TABLE IF NOT EXISTS ai_base_images (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    s3_key VARCHAR(500) NOT NULL,
    format VARCHAR(10) NOT NULL,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS ai_xss_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    xss_type VARCHAR(50) NOT NULL,
    html_template TEXT NOT NULL,
    payload_example TEXT,
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_ai_gen_batches_status ON ai_generation_batches(status);
CREATE INDEX idx_ai_gen_variants_batch ON ai_generation_variants(batch_id);
CREATE INDEX idx_ai_gen_variants_selected ON ai_generation_variants(is_selected) WHERE is_selected = true;
CREATE INDEX idx_ai_gen_analytics_lookup ON ai_generation_analytics(task_type, difficulty, period_date);
```

### Step 1.3: Create SQLAlchemy ORM models

Create: `backend/app/models/ai_generation.py`

Define ORM classes: `AIGenerationBatch`, `AIGenerationVariant`, `AIGenerationAnalytics`, `AIBaseImage`, `AIXSSTemplate`.

For the `embedding` column on kb_entries and tasks, use:
```python
from pgvector.sqlalchemy import Vector

# Add to existing KBEntry model (or create a mixin):
embedding = Column(Vector(256), nullable=True)
```

This requires the `pgvector` Python package (added to dependencies below).

### Step 1.4: Create Pydantic schemas

Create: `backend/app/schemas/ai_generation.py`

```python
class GenerateRequest(BaseModel):
    task_type: Literal["forensics_image_metadata", "crypto_text_web", "web_static_xss", "chat_llm"]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    num_variants: int = 5
    cve_id: str | None = None       # specific CVE to base challenge on
    topic: str | None = None        # free-text topic → embedded and searched semantically

class GenerateResponse(BaseModel):
    batch_id: str
    status: str
    rag_context_used: int           # how many KB entries were pulled

class VariantSchema(BaseModel):
    id: str
    variant_number: int
    reward_total: float
    reward_binary: float
    advantage: float
    rank_in_group: int
    passed_all_binary: bool
    quality_score: float | None
    failure_reason: str | None
    based_on_cve: str | None

class BatchStatusResponse(BaseModel):
    batch_id: str
    status: str
    task_type: str
    difficulty: str
    attempt: int
    group_mean_reward: float | None
    group_std_reward: float | None
    pass_rate: float | None
    rag_context_summary: str | None
    variants: list[VariantSchema]
    selected_variant_id: str | None
```

---

## Phase 2: Embedding Service + pgvector RAG

### Step 2.1: Create embedding service

Create: `backend/app/services/ai_generator/embedding_service.py`

```python
"""
Embedding service using Yandex Cloud text-search API.

Yandex provides two embedding models (asymmetric pair):
- text-search-doc:   for documents (kb_entries content) — optimized for indexing
- text-search-query:  for search queries — optimized for retrieval

Asymmetric means: the query "xss vulnerability" and the document
"improper neutralization of input during web page generation" are
projected into the same vector space but encoded differently,
so their cosine similarity is high even though they share zero words.

Uses existing YANDEX_CLOUD_API_KEY and YANDEX_CLOUD_FOLDER from config.
"""

import httpx
from app.config import settings

YANDEX_EMBEDDING_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding"


class EmbeddingService:

    def __init__(self):
        self.api_key = settings.YANDEX_CLOUD_API_KEY
        self.folder_id = settings.YANDEX_CLOUD_FOLDER
        self._client = httpx.AsyncClient(timeout=30.0)

    def _model_uri(self, model_type: str) -> str:
        """
        model_type: 'text-search-doc' or 'text-search-query'
        """
        return f"emb://{self.folder_id}/{model_type}/latest"

    async def embed_document(self, text: str) -> list[float]:
        """
        Embed a document (kb_entry, task description) for indexing.
        Uses text-search-doc model.
        Call this when:
        - nvd_sync adds a new CVE
        - backfilling existing kb_entries
        - publishing a new task (for duplicate detection)
        """
        return await self._embed(text, "text-search-doc")

    async def embed_query(self, query: str) -> list[float]:
        """
        Embed a search query for retrieval.
        Uses text-search-query model.
        Call this when:
        - RAG context builder needs to find relevant CVEs
        - Checking if a generated task is a duplicate of existing ones
        """
        return await self._embed(query, "text-search-query")

    async def _embed(self, text: str, model_type: str) -> list[float]:
        """Call Yandex Embedding API."""
        response = await self._client.post(
            YANDEX_EMBEDDING_URL,
            headers={
                "Authorization": f"Api-Key {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "modelUri": self._model_uri(model_type),
                "text": text[:8000],  # Yandex limit: ~8K chars
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["embedding"]

    async def close(self):
        await self._client.aclose()
```

### Step 2.2: Create backfill script for existing kb_entries

Create: `backend/app/scripts/backfill_embeddings.py`

```python
"""
One-time script: compute embeddings for all kb_entries that don't have one yet.

Run: python -m app.scripts.backfill_embeddings

Cost estimate: ~0.008 RUB per 1000 tokens.
1000 entries × ~200 tokens each = 200K tokens = ~1.6 RUB total.
"""

import asyncio
from sqlalchemy import select, update
from app.database import async_session_factory
from app.models.knowledge import KBEntry       # adjust import to actual model name
from app.services.ai_generator.embedding_service import EmbeddingService

BATCH_SIZE = 50   # embed 50 entries per batch to avoid rate limits
DELAY = 0.5       # seconds between batches


async def backfill():
    embedding_service = EmbeddingService()
    async with async_session_factory() as db:
        # Fetch all entries without embedding
        query = (
            select(KBEntry)
            .where(KBEntry.embedding.is_(None))
            .order_by(KBEntry.id)
        )
        result = await db.execute(query)
        entries = result.scalars().all()
        print(f"Found {len(entries)} entries without embeddings")

        for i in range(0, len(entries), BATCH_SIZE):
            batch = entries[i:i + BATCH_SIZE]
            for entry in batch:
                # Combine title + content preview for richer embedding
                text = f"{entry.title or ''}\n{(entry.content or '')[:2000]}"
                try:
                    vector = await embedding_service.embed_document(text)
                    entry.embedding = vector
                except Exception as e:
                    print(f"  ERROR on entry {entry.id}: {e}")

            await db.commit()
            done = min(i + BATCH_SIZE, len(entries))
            print(f"  Embedded {done}/{len(entries)}")
            await asyncio.sleep(DELAY)

    await embedding_service.close()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(backfill())
```

### Step 2.3: Modify nvd_sync.py to embed new entries on insert

In existing `backend/app/services/nvd_sync.py`, after inserting a new kb_entry, add:

```python
# After creating and flushing the new KBEntry:
from app.services.ai_generator.embedding_service import EmbeddingService

embedding_service = EmbeddingService()
text = f"{new_entry.title}\n{(new_entry.content or '')[:2000]}"
try:
    new_entry.embedding = await embedding_service.embed_document(text)
except Exception:
    pass  # non-critical: backfill script can fix later
```

This ensures every new CVE synced from NVD gets an embedding immediately.

### Step 2.4: Create semantic RAG context builder

Create: `backend/app/services/ai_generator/rag_context.py`

```python
"""
Semantic RAG Context Builder using pgvector.

Instead of keyword ILIKE matching (which misses synonyms and paraphrases),
we embed the generation query and find the closest kb_entries by cosine distance.

Example: query "xss vulnerability in web application" will find:
- "improper neutralization of input during web page generation" (cos=0.87)
- "reflected script injection via URL parameter" (cos=0.91)
even though they share zero keywords with "xss".
"""

from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.services.ai_generator.embedding_service import EmbeddingService

# Natural-language descriptions of each task type for embedding queries.
# These are more expressive than keyword lists.
TASK_TYPE_QUERY_TEMPLATES = {
    "forensics_image_metadata": (
        "digital forensics image metadata analysis EXIF steganography "
        "hidden data in photos file carving forensic investigation"
    ),
    "crypto_text_web": (
        "cryptography cipher encryption decryption vulnerability "
        "weak encryption broken cipher cryptographic attack"
    ),
    "web_static_xss": (
        "cross-site scripting XSS web vulnerability injection "
        "DOM manipulation reflected stored script execution sanitization bypass"
    ),
    "chat_llm": (
        "LLM prompt injection jailbreak AI safety "
        "system prompt extraction social engineering language model attack"
    ),
}


class RAGContext:
    """Structured context passed to the Generator Agent prompt."""

    def __init__(
        self,
        cve_entries: list,
        existing_task_titles: list[str],
        last_nvd_sync: datetime | None,
        entry_ids: list[int],
        query_text: str,
    ):
        self.cve_entries = cve_entries
        self.existing_task_titles = existing_task_titles
        self.last_nvd_sync = last_nvd_sync
        self.entry_ids = entry_ids
        self.query_text = query_text

    def format_for_prompt(self) -> str:
        """Format RAG context as a text block injected into the Generator prompt."""
        sections = []

        if self.cve_entries:
            sections.append("## Real-world vulnerabilities to reference")
            sections.append(
                "Use one or more of these as inspiration for the challenge scenario.\n"
            )
            for entry in self.cve_entries:
                cve_tag = f"[{entry.cve_id}]" if getattr(entry, "cve_id", None) else ""
                severity = f"({entry.severity})" if getattr(entry, "severity", None) else ""
                title = getattr(entry, "title", "Untitled")
                content_preview = (getattr(entry, "content", "") or "")[:300].strip()
                sections.append(f"- {cve_tag} {severity} **{title}**")
                if content_preview:
                    sections.append(f"  {content_preview}...")
                sections.append("")

        if self.existing_task_titles:
            sections.append("## Existing challenges (DO NOT duplicate these)")
            for title in self.existing_task_titles[:10]:
                sections.append(f"- {title}")
            sections.append("")

        if self.last_nvd_sync:
            sections.append(
                f"Knowledge base last updated: {self.last_nvd_sync.strftime('%Y-%m-%d')}"
            )

        return "\n".join(sections)

    @property
    def is_empty(self) -> bool:
        return len(self.cve_entries) == 0


class RAGContextBuilder:
    """
    Builds generation context via pgvector semantic search on kb_entries.

    Flow:
    1. Build a natural-language query from task_type + user topic
    2. Embed the query via Yandex text-search-query model
    3. SELECT closest kb_entries by cosine distance
    4. Also fetch existing tasks (via embedding similarity) for duplicate avoidance
    5. Return structured RAGContext
    """

    def __init__(self, db: AsyncSession, context_limit: int = 5):
        self.db = db
        self.context_limit = context_limit
        self.embedding_service = EmbeddingService()

    async def build_context(
        self,
        task_type: str,
        difficulty: str,
        specific_cve: str | None = None,
        specific_topic: str | None = None,
    ) -> RAGContext:
        """Main entry point."""

        # 1. If specific CVE requested, fetch directly (no embedding needed)
        if specific_cve:
            cve_entries = await self._fetch_specific_cve(specific_cve)
            query_text = specific_cve
        else:
            # 2. Build semantic query
            query_text = self._build_query(task_type, difficulty, specific_topic)

            # 3. Embed the query
            query_vector = await self.embedding_service.embed_query(query_text)

            # 4. Semantic search in kb_entries via pgvector cosine distance
            cve_entries = await self._semantic_search_cves(query_vector)

        # 5. Find existing tasks to avoid duplicates (also via embedding)
        existing_tasks = await self._fetch_existing_tasks(task_type)

        # 6. Last NVD sync time
        last_sync = await self._get_last_nvd_sync()

        return RAGContext(
            cve_entries=cve_entries[: self.context_limit],
            existing_task_titles=[t.title for t in existing_tasks],
            last_nvd_sync=last_sync,
            entry_ids=[e.id for e in cve_entries[: self.context_limit]],
            query_text=query_text,
        )

    def _build_query(
        self, task_type: str, difficulty: str, topic: str | None
    ) -> str:
        """
        Build a natural-language query for embedding.
        Combines the task-type template with user-specified topic.
        """
        base_query = TASK_TYPE_QUERY_TEMPLATES.get(task_type, task_type)

        if topic:
            # User topic goes first (highest weight in embedding)
            return f"{topic} {base_query} {difficulty} level"
        return f"{base_query} {difficulty} level"

    async def _semantic_search_cves(self, query_vector: list[float]) -> list:
        """
        Core pgvector query: find kb_entries closest to query by cosine distance.

        Uses <=> operator (cosine distance) with HNSW index.
        Lower distance = more similar.
        Only searches entries that HAVE an embedding (not NULL).
        """
        from app.models.knowledge import KBEntry  # adjust import

        # pgvector cosine distance: column <=> vector literal
        # SQLAlchemy with pgvector: use .cosine_distance() method
        query = (
            select(KBEntry)
            .where(KBEntry.embedding.isnot(None))
            .order_by(KBEntry.embedding.cosine_distance(query_vector))
            .limit(self.context_limit)
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def _fetch_specific_cve(self, cve_id: str) -> list:
        """Fetch a specific CVE by ID."""
        from app.models.knowledge import KBEntry

        query = select(KBEntry).where(KBEntry.cve_id == cve_id)
        result = await self.db.execute(query)
        entry = result.scalar_one_or_none()
        return [entry] if entry else []

    async def _fetch_existing_tasks(self, task_type: str) -> list:
        """Fetch existing tasks of same category for duplicate avoidance."""
        from app.models.task import Task  # adjust import

        category_map = {
            "forensics_image_metadata": "forensics",
            "crypto_text_web": "crypto",
            "web_static_xss": "web",
            "chat_llm": "misc",
        }

        query = (
            select(Task)
            .where(Task.category == category_map.get(task_type))
            .where(Task.is_active == True)
            .order_by(Task.created_at.desc())
            .limit(10)
        )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def _get_last_nvd_sync(self) -> datetime | None:
        """Last successful NVD sync timestamp."""
        from app.models.knowledge import NVDSyncLog  # adjust import

        query = (
            select(NVDSyncLog.created_at)
            .order_by(NVDSyncLog.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
```

### Step 2.5: Add RAG_GROUNDING reward check using embedding similarity

In `validator.py`, the grounding check uses embedding similarity instead of keyword overlap:

```python
async def check_rag_grounding(self, spec: dict, rag_context: RAGContext) -> dict:
    """
    Verify the generated challenge is semantically grounded in real CVE data.

    Instead of checking keyword overlap (fragile), we:
    1. Embed the generated title + description
    2. Compute cosine similarity against each RAG context entry's embedding
    3. Score based on best match

    score 1.0: cosine similarity >= 0.8 with a context entry
    score 0.7: cosine similarity >= 0.6
    score 0.4: cosine similarity >= 0.4
    score 0.1: below 0.4 (challenge is unrelated to provided context)
    """
    if rag_context.is_empty:
        return {"passed": True, "score": 0.5, "detail": "No RAG context available"}

    # Embed the generated challenge
    challenge_text = f"{spec.get('title', '')} {spec.get('description', '')}"
    challenge_vec = await self.embedding_service.embed_document(challenge_text)

    # Compare against each context entry's embedding
    best_similarity = 0.0
    best_cve = None
    for entry in rag_context.cve_entries:
        entry_vec = getattr(entry, 'embedding', None)
        if entry_vec is None:
            continue
        # Cosine similarity = 1 - cosine distance
        similarity = 1.0 - cosine_distance(challenge_vec, list(entry_vec))
        if similarity > best_similarity:
            best_similarity = similarity
            best_cve = getattr(entry, 'cve_id', None) or getattr(entry, 'title', '')

    if best_similarity >= 0.8:
        return {"passed": True, "score": 1.0,
                "detail": f"Strongly grounded (sim={best_similarity:.2f}, ref={best_cve})"}
    elif best_similarity >= 0.6:
        return {"passed": True, "score": 0.7,
                "detail": f"Well grounded (sim={best_similarity:.2f}, ref={best_cve})"}
    elif best_similarity >= 0.4:
        return {"passed": True, "score": 0.4,
                "detail": f"Loosely grounded (sim={best_similarity:.2f})"}
    else:
        return {"passed": True, "score": 0.1,
                "detail": f"Weak grounding (sim={best_similarity:.2f})"}


def cosine_distance(a: list[float], b: list[float]) -> float:
    """Compute cosine distance between two vectors. 0 = identical, 2 = opposite."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))
```

---

## Phase 3: Core Pipeline (reward.py + pipeline.py)

### Step 3.1: Create the reward system

Create: `backend/app/services/ai_generator/reward.py`

Defines:
- `RewardType` enum: FUNCTIONAL, SOLVABILITY, NON_TRIVIALITY, FORMAT, RAG_GROUNDING, QUALITY
- `RewardCheck`, `VariantReward` dataclasses
- `REWARD_WEIGHTS` per task type (RAG_GROUNDING weight = 1.5)
- `compute_group_advantages()` function

RAG_GROUNDING is a soft score (0.0-1.0), NOT a binary gate.
`passed_all_binary` checks only FORMAT, FUNCTIONAL, SOLVABILITY, NON_TRIVIALITY.

### Step 3.2: Create the pipeline orchestrator

Create: `backend/app/services/ai_generator/pipeline.py`

Flow:
```
1. Build RAG context (embed query → pgvector search → format for prompt)
2. Store RAG entry IDs + query_text in batch record
3. For attempt in 1..max_retries:
   a. Generate N specs in parallel (with RAG context in prompt)
   b. Create artifacts
   c. Run 4 binary reward checks
   d. Run RAG grounding check (embedding similarity, soft score)
   e. For passed variants: run LLM quality assessment
   f. Compute group-relative advantages
   g. Rejection gate (binary only)
   h. Select best by advantage
   i. Store ALL results
4. Return result
```

### Step 3.3: Create the LLM-as-judge reviewer

Create: `backend/app/services/ai_generator/reviewer.py`

5 quality dimensions scored 0.0-1.0: educational_value, scenario_realism, hint_quality, writeup_clarity, difficulty_calibration.

---

## Phase 4: Task Type Implementations

### Step 4.1: crypto_text_web (FIRST)

Create: `backend/app/services/ai_generator/crypto_utils.py`
Create: `backend/app/services/ai_generator/artifact_creator.py` (crypto method)
Create: `backend/app/services/ai_generator/validator.py` (crypto checks + rag_grounding)

### Step 4.2: forensics_image_metadata

Create: `backend/app/services/ai_generator/forensics_utils.py`

### Step 4.3: web_static_xss

Create: `backend/app/services/ai_generator/xss_templates.py`

### Step 4.4: chat_llm

Create: `backend/app/services/ai_generator/chat_utils.py`

---

## Phase 5: API Route + Background Tasks

### Step 5.1: Create the route

Create: `backend/app/routes/ai_generate.py`

Endpoints:
- `POST /ai-generate/` — accepts `GenerateRequest` with optional `cve_id` and `topic` (topic is embedded semantically)
- `GET /ai-generate/batch/{batch_id}` — returns `BatchStatusResponse`
- `POST /ai-generate/batch/{batch_id}/publish/{variant_id}` — admin only. Also embeds the published task for future duplicate detection.
- `GET /ai-generate/analytics` — admin only

### Step 5.2: Register in main.py

### Step 5.3: Publish logic

On publish, ALSO embed the new task:
```python
# After INSERT into tasks:
text = f"{task.title}\n{task.description}"
task.embedding = await embedding_service.embed_document(text)
await db.commit()
```

This enables future duplicate detection: before generating, check if any existing task has cosine_distance < 0.15 to the new one.

---

## Phase 6: Feedback Loop

### Step 6.1: Create feedback.py

Also tracks: which RAG context entries led to highest-quality generations. Stores `rag_context_ids` correlation with `quality_score` to improve future context selection.

### Step 6.2: Wire into pipeline

---

## Phase 7: Frontend Page

Add to GenerationForm: optional CVE ID field, optional topic field (free text, searched semantically).
Show in BatchProgress: "Based on: [CVE list]" from rag_context_summary.

---

## Phase 8: Testing + Seed Data

### Step 8.1: Run backfill script

```bash
cd backend
python -m app.scripts.backfill_embeddings
```

Verify: `SELECT COUNT(*) FROM kb_entries WHERE embedding IS NOT NULL;` should match total count.

### Step 8.2: Test semantic search manually

```sql
-- Find 5 most similar entries to an XSS query embedding
-- (use Python to get the query vector first, then paste it here)
SELECT id, cve_id, title,
       embedding <=> '[0.1, 0.2, ...]'::vector AS distance
FROM kb_entries
WHERE embedding IS NOT NULL
ORDER BY distance
LIMIT 5;
```

### Step 8.3: Upload base images, insert XSS templates, insert prompts

### Step 8.4: E2E test with semantic RAG

1. `POST /ai-generate/` with `topic="buffer overflow"` and `task_type="crypto_text_web"`
2. Verify: batch.rag_context_ids is populated
3. Verify: returned CVEs are semantically related (not just keyword matches)
4. Full pipeline through to publish

### Step 8.5: Test specific CVE generation

### Step 8.6: Generate demo dataset (20+ challenges)

---

## Dependencies

Add to `backend/requirements.txt`:
```
Pillow>=10.0
piexif>=1.1.3
pycryptodome>=3.20
pgvector>=0.3.0
httpx>=0.27.0
```

Note: `pgvector` Python package provides SQLAlchemy integration (`from pgvector.sqlalchemy import Vector`). The PostgreSQL extension itself is installed via `CREATE EXTENSION vector` in the migration.

---

## Implementation Order (strict)

```
 1. config.py changes (embedding dimension, RAG settings)
 2. SQL migration (CREATE EXTENSION vector + embedding columns + HNSW indexes + new tables)
 3. ORM models (add Vector column to KBEntry and Task models + new generation models)
 4. Pydantic schemas
 5. embedding_service.py (Yandex text-search-doc/query API wrapper)
 6. backfill_embeddings.py script (embed all existing kb_entries)
 7. Run backfill: python -m app.scripts.backfill_embeddings
 8. Modify nvd_sync.py: embed new CVEs on insert
 9. rag_context.py (RAGContextBuilder with pgvector semantic search)
10. reward.py (RewardType with RAG_GROUNDING, compute_group_advantages)
11. crypto_utils.py (all cipher functions)
12. artifact_creator.py (crypto_text only first)
13. validator.py (binary checks + embedding-based rag_grounding check)
14. reviewer.py (LLM-as-judge)
15. pipeline.py (full GRPO loop with semantic RAG context injection)
16. ai_generate.py route (POST with cve_id/topic + GET + publish with embedding)
17. Register route in main.py
18. E2E test: crypto_text_web with topic="encryption"
19. forensics_utils.py + forensics artifact + forensics validator
20. xss_templates.py + xss artifact + xss validator
21. chat_utils.py + chat artifact + chat validator
22. feedback.py (analytics + RAG effectiveness tracking)
23. Wire feedback into pipeline
24. Frontend page (with CVE/topic input)
25. Seed data (base images, xss templates, prompts)
26. Full E2E test all 4 types with semantic RAG
27. Test specific CVE-based generation
28. Generate demo dataset, collect metrics
```
