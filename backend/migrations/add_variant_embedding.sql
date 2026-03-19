-- Add embedding column to ai_generation_variants for feedback loop similarity search
-- Run: psql $DATABASE_URL -f add_variant_embedding.sql

ALTER TABLE ai_generation_variants ADD COLUMN IF NOT EXISTS embedding vector(256);

CREATE INDEX IF NOT EXISTS idx_ai_gen_variants_embedding
    ON ai_generation_variants USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;
