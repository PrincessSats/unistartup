# CLAUDE.md — AI Generator Implementation Checklist

## Context

You are implementing an AI-powered CTF challenge generator for the HackNet platform.
The system uses a GRPO-inspired pipeline (adapted from DeepSeek-R1, arXiv:2501.12948):
- Generate N variant specs in parallel with different temperatures
- Create artifacts deterministically from specs
- Score each variant with rule-based binary checks + LLM-as-judge quality
- Compute group-relative advantages: Â_i = (r_i - mean) / std
- Reject variants that fail any binary check
- Select best variant by highest advantage among passed
- Store ALL results (winners AND losers) with failure reasons
- Feed failure patterns back as negative few-shot in future generations

## Existing Infrastructure (DO NOT modify)

```
backend/app/main.py          — FastAPI app, add router registration here
backend/app/config.py        — pydantic-settings, add new env vars here
backend/app/database.py      — async SQLAlchemy engine + session
backend/app/routes/           — existing routes (auth, education, etc.)
backend/app/services/         — existing services (task_generation, chat_task, storage, prompt_loader)
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

---

## Phase 1: Database Schema + Config

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
```

### Step 1.2: Create migration SQL

Create new file: `backend/migrations/add_ai_generation_tables.sql`

```sql
-- Batch: one user request = one batch of N variants
CREATE TABLE IF NOT EXISTS ai_generation_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requested_by INTEGER REFERENCES users(id),
    task_type VARCHAR(50) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    num_variants INTEGER NOT NULL DEFAULT 5,
    attempt INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
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

-- Each variant within a batch (ALL stored, not just winners)
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
    reward_checks JSONB,           -- [{type, score, weight, detail, error}]
    reward_total FLOAT,
    reward_binary FLOAT,
    passed_all_binary BOOLEAN DEFAULT false,
    -- LLM quality assessment (only if passed binary)
    quality_score FLOAT,
    quality_details JSONB,          -- {educational_value, scenario_realism, ...}
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

-- Aggregated analytics for feedback loop
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

-- Pool of base images for forensics tasks
CREATE TABLE IF NOT EXISTS ai_base_images (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    s3_key VARCHAR(500) NOT NULL,
    format VARCHAR(10) NOT NULL,
    is_active BOOLEAN DEFAULT true
);

-- XSS page templates
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

Define ORM classes matching the tables above: `AIGenerationBatch`, `AIGenerationVariant`, `AIGenerationAnalytics`, `AIBaseImage`, `AIXSSTemplate`.

Follow the existing model patterns in `backend/app/models/`.

### Step 1.4: Create Pydantic schemas

Create: `backend/app/schemas/ai_generation.py`

```python
# Request/response schemas:

class GenerateRequest(BaseModel):
    task_type: Literal["forensics_image_metadata", "crypto_text_web", "web_static_xss", "chat_llm"]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    num_variants: int = 5  # 3-7

class GenerateResponse(BaseModel):
    batch_id: str
    status: str  # "generating"

class RewardCheckSchema(BaseModel):
    type: str
    score: float
    weight: float
    detail: str
    error: str

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
    # Do NOT expose generated_spec (contains flag)

class BatchStatusResponse(BaseModel):
    batch_id: str
    status: str
    task_type: str
    difficulty: str
    attempt: int
    group_mean_reward: float | None
    group_std_reward: float | None
    pass_rate: float | None
    variants: list[VariantSchema]
    selected_variant_id: str | None

class AnalyticsResponse(BaseModel):
    task_type: str
    difficulty: str
    total_variants: int
    passed_variants: int
    pass_rate: float
    avg_quality_score: float | None
    common_failures: list[dict]
    best_temperature: float | None
```

---

## Phase 2: Core Pipeline (reward.py + pipeline.py)

### Step 2.1: Create the reward system

Create: `backend/app/services/ai_generator/reward.py`

This file defines:
- `RewardType` enum: FUNCTIONAL, SOLVABILITY, NON_TRIVIALITY, FORMAT, QUALITY
- `RewardCheck` dataclass: one check result (type, score, weight, detail, error)
- `VariantReward` dataclass: all checks for one variant, with computed `total_reward`, `binary_reward`, `passed_all_binary`
- `REWARD_WEIGHTS` dict: per-task-type weights for each reward type
- `compute_group_advantages()` function: takes list[VariantReward], returns list with advantage scores

The group-relative advantage formula:
```python
advantage_i = (reward_i - mean(all_rewards)) / std(all_rewards)
```

### Step 2.2: Create the pipeline orchestrator

Create: `backend/app/services/ai_generator/pipeline.py`

This is the main entry point. The `run()` method:

```
for attempt in 1..max_retries:
    1. Generate N specs in parallel (asyncio.gather)
       - Each with different temperature: base + i * step
       - If retry: inject failure_context as negative few-shot in prompt
    2. For each spec, create artifact (asyncio.gather)
    3. For each artifact, run 4 binary reward checks
    4. For passed variants only, run LLM quality assessment
    5. Compute group-relative advantages across ALL variants
    6. Apply rejection gate: filter to passed_all_binary == True
    7. Select variant with highest advantage among passed
    8. If selected and total_reward >= threshold: return success
    9. If none passed: accumulate failure_context, continue to next attempt
    10. Store ALL variant results in DB (winners AND losers)
```

Important: step 10 happens on EVERY attempt, not just the final one. Every variant ever generated is stored.

### Step 2.3: Create the LLM-as-judge reviewer

Create: `backend/app/services/ai_generator/reviewer.py`

The reviewer calls the LLM with a structured prompt asking it to score 5 quality dimensions (0.0-1.0 each):
- educational_value
- scenario_realism
- hint_quality
- writeup_clarity
- difficulty_calibration

Use `response_format={"type": "json_object"}` to get structured output.
Use `temperature=0.1` for consistent judging.
Return the average of all 5 dimensions as the composite quality_score.

This is ONLY called for variants that passed all binary checks (saves tokens).

---

## Phase 3: Task Type Implementations

### Step 3.1: crypto_text_web (implement FIRST — simplest)

Create: `backend/app/services/ai_generator/crypto_utils.py`

Implement cipher functions (encrypt AND decrypt for validation):
- `caesar_encrypt(text, shift)` / `caesar_decrypt(text, shift)`
- `vigenere_encrypt(text, key)` / `vigenere_decrypt(text, key)`
- `xor_encrypt(text, key)` / `xor_decrypt(text, key)`
- `base64_encode(text)` / `base64_decode(text)`
- `reverse_string(text)`
- `apply_chain(plaintext, chain)` — applies a list of operations in sequence
- `reverse_chain(ciphertext, chain)` — applies inverse operations in reverse order

Create: `backend/app/services/ai_generator/artifact_creator.py`

Method `_create_crypto_text(spec)`:
1. Extract flag and crypto_chain from spec
2. Call `apply_chain(flag_with_wrapper, chain)` to produce ciphertext
3. Return `ArtifactResult(content=ciphertext, verification_data={"chain": chain})`

Validator binary checks for crypto:
- FORMAT: spec has title, description, flag (CTF{...}), crypto_chain, writeup, hints
- FUNCTIONAL: `apply_chain()` runs without error
- SOLVABILITY: `reverse_chain(ciphertext, chain)` contains the flag
- NON_TRIVIALITY: flag not in ciphertext as plaintext; single base64_decode doesn't reveal flag

Generator prompt for crypto: ask LLM to produce JSON with title, description, flag, difficulty-appropriate crypto_chain (beginner: 1-2 steps, intermediate: 2-3, advanced: 3-5), writeup explaining each decryption step, and 3 graduated hints.

### Step 3.2: forensics_image_metadata

Create: `backend/app/services/ai_generator/forensics_utils.py`

Dependencies to add to requirements.txt: `Pillow>=10.0`, `piexif>=1.1.3`

Method `_create_forensics_image(spec)`:
1. Pick random base image from `ai_base_images` table (or S3 pool)
2. Based on spec.hide_in field, inject flag:
   - `exif_comment`: piexif → ImageIFD.ImageDescription
   - `exif_artist`: piexif → ImageIFD.Artist
   - `xmp_description`: write XMP packet into image
   - `file_comment`: append flag as JPEG comment marker
3. Add decoy metadata (fake GPS, dates, camera model)
4. Upload to S3 via existing storage service
5. Return ArtifactResult with file_url

Validator checks:
- FUNCTIONAL: downloaded file is valid JPEG/PNG (Pillow can open it)
- SOLVABILITY: extracting the specified metadata field contains the flag
- NON_TRIVIALITY: flag not in filename, not visible as image content

### Step 3.3: web_static_xss

Create: `backend/app/services/ai_generator/xss_templates.py`

3 parameterized templates (can also be stored in `ai_xss_templates` table):
- Beginner reflected: innerHTML from URL param, flag in document.cookie
- Intermediate DOM-based: location.hash processing, basic filter bypass needed
- Advanced: simple CSP/WAF to bypass, flag in localStorage

Method `_create_xss_page(spec)`:
1. Select template matching difficulty and xss_type
2. Inject flag, page title, scenario details into template
3. Upload complete HTML file to S3 as public object
4. Return ArtifactResult with page_url

Validator checks:
- FUNCTIONAL: HTML is parseable, no syntax errors
- SOLVABILITY: HTML contains a known XSS sink (innerHTML, document.write, eval)
- NON_TRIVIALITY: flag appears only in JS/cookie/comment, not in visible DOM text

### Step 3.4: chat_llm

Create: `backend/app/services/ai_generator/chat_utils.py`

Method `_create_chat_prompt(spec)`:
1. Build system prompt from spec (role, secret flag, defense rules)
2. Return ArtifactResult with content=system_prompt

Validator checks:
- FUNCTIONAL: system prompt is non-empty and contains the flag
- SOLVABILITY: send writeup_payload via LLM → response contains flag
- NON_TRIVIALITY: send 3-5 normal queries → none of them leak the flag

Integration: on publish, create `task_chat_sessions` entry and store system prompt via existing `chat_task.py` patterns.

---

## Phase 4: API Route + Background Tasks

### Step 4.1: Create the route

Create: `backend/app/routes/ai_generate.py`

Endpoints:
- `POST /ai-generate/` — starts generation, returns batch_id. Requires auth (admin or PRO tariff). Launches pipeline as BackgroundTask.
- `GET /ai-generate/batch/{batch_id}` — returns BatchStatusResponse with all variant scores
- `POST /ai-generate/batch/{batch_id}/publish/{variant_id}` — admin only. Creates task + task_flags + task_materials from selected variant.
- `GET /ai-generate/analytics` — admin only. Returns aggregated generation stats.

### Step 4.2: Register in main.py

Add to `backend/app/main.py`:
```python
from app.routes.ai_generate import router as ai_generate_router
app.include_router(ai_generate_router)
```

### Step 4.3: Publish logic

The publish endpoint must:
1. Load variant from `ai_generation_variants`
2. Map task_type to access_type: forensics→"file", crypto→"just_flag", xss→"link", chat→"chat"
3. INSERT into `tasks` (title, description, category, difficulty, points, access_type, access_data)
4. INSERT into `task_flags` (task_id, flag_value, flag_type="static")
5. INSERT into `task_materials` if file/url artifact exists
6. For chat_llm: create prompt_template entry and link to task
7. UPDATE variant: is_selected=true, published_task_id=task.id
8. COMMIT

---

## Phase 5: Feedback Loop

### Step 5.1: Analytics aggregation

Create: `backend/app/services/ai_generator/feedback.py`

Function `compute_feedback_context(task_type, difficulty)` queries:
- Top 3 published variant specs by advantage (positive few-shot)
- Top 5 most common failure reasons (negative few-shot)
- Best performing temperature for this task_type
- Current pass rate

Returns a dict that the Generator injects into its prompt.

### Step 5.2: Wire into pipeline

In `pipeline.py._generate_one_variant()`:
1. Before first attempt of any batch, call `compute_feedback_context()`
2. If positive_examples exist, append 1-2 abbreviated examples to the system prompt as "Here are examples of high-quality challenges that scored well:"
3. If negative_examples exist, append as "Avoid these common mistakes:"
4. On retry within a batch, additionally append the specific failure reasons from the current batch

---

## Phase 6: Frontend Page

Create: `frontend/src/pages/AIGenerator/`

Files:
- `AIGeneratorPage.js` — main page, admin/PRO access check
- `GenerationForm.js` — form with task_type dropdown, difficulty dropdown, num_variants slider (3-7), generate button
- `BatchProgress.js` — polls `GET /ai-generate/batch/{id}` every 2s, shows status, progress bar
- `VariantCard.js` — shows variant: reward_total, advantage, rank, passed/failed checks, quality_score
- `PublishButton.js` — admin button on winning variant card
- `AnalyticsDashboard.js` — charts: pass rate by type, quality trend, common failures

Register route in `frontend/src/App.js`:
```jsx
<Route path="/ai-generator" element={<ProtectedRoute><AIGeneratorPage /></ProtectedRoute>} />
```

---

## Phase 7: Testing + Seed Data

### Step 7.1: Upload base images

Upload 10-20 stock photos to S3 bucket, insert records into `ai_base_images` table.
Categories: office, landscape, screenshot, document.

### Step 7.2: Insert XSS templates

Insert 3 HTML templates into `ai_xss_templates` table (beginner reflected, intermediate DOM, advanced filter bypass).

### Step 7.3: Insert generator prompts

Insert prompts for each task type into existing `prompt_templates` table.

### Step 7.4: End-to-end test

For each of the 4 task types:
1. Call `POST /ai-generate/` with difficulty="beginner"
2. Poll until status="completed" or "failed"
3. Verify: batch has N variants, at least 1 passed, selected_variant exists
4. Call publish endpoint
5. Verify: new task appears in tasks table with correct access_type

### Step 7.5: Generate demo dataset

Generate 20+ challenges (5 per type) at varied difficulties.
Collect metrics: pass_rate, avg_quality, avg_generation_time.

---

## Dependencies

Add to `backend/requirements.txt`:
```
Pillow>=10.0
piexif>=1.1.3
pycryptodome>=3.20
```

---

## Implementation Order (strict)

```
1. config.py changes
2. SQL migration
3. ORM models
4. Pydantic schemas
5. reward.py (RewardType, RewardCheck, VariantReward, compute_group_advantages)
6. crypto_utils.py (all cipher functions + chain apply/reverse)
7. artifact_creator.py (crypto_text only first)
8. validator.py (crypto checks only first)
9. reviewer.py (LLM-as-judge)
10. pipeline.py (full GRPO loop)
11. ai_generate.py route (POST + GET + publish)
12. Register route in main.py
13. E2E test with crypto_text_web
14. forensics_utils.py + forensics artifact + forensics validator
15. xss_templates.py + xss artifact + xss validator
16. chat_utils.py + chat artifact + chat validator
17. feedback.py (analytics + few-shot context)
18. Wire feedback into pipeline
19. Frontend page
20. Seed data (base images, xss templates, prompts)
21. Full E2E test all 4 types
```
