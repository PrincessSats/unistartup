-- Migration: add pipeline stage tracking columns to ai_generation_batches
ALTER TABLE ai_generation_batches ADD COLUMN IF NOT EXISTS current_stage VARCHAR(50) DEFAULT 'pending';
ALTER TABLE ai_generation_batches ADD COLUMN IF NOT EXISTS stage_started_at TIMESTAMPTZ;
ALTER TABLE ai_generation_batches ADD COLUMN IF NOT EXISTS stage_meta JSONB;
