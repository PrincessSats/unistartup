-- AI Generator Tables Migration
-- Run once: psql $DATABASE_URL -f add_ai_generation_tables.sql

-- ── pgvector extension + embedding columns ────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE kb_entries ADD COLUMN IF NOT EXISTS embedding vector(256);
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS embedding vector(256);

CREATE INDEX IF NOT EXISTS idx_kb_entries_embedding_hnsw
    ON kb_entries USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_tasks_embedding_hnsw
    ON tasks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── Batch: one user request = one batch of N variants
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
    completed_at TIMESTAMPTZ,
    -- RAG context
    rag_context_ids INTEGER[],
    rag_context_summary TEXT,
    rag_query_text TEXT
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

CREATE INDEX IF NOT EXISTS idx_ai_gen_batches_status ON ai_generation_batches(status);
CREATE INDEX IF NOT EXISTS idx_ai_gen_variants_batch ON ai_generation_variants(batch_id);
CREATE INDEX IF NOT EXISTS idx_ai_gen_variants_selected ON ai_generation_variants(is_selected) WHERE is_selected = true;
CREATE INDEX IF NOT EXISTS idx_ai_gen_analytics_lookup ON ai_generation_analytics(task_type, difficulty, period_date);
