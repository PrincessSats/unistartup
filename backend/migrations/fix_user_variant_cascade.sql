-- Migration: Fix cascade delete for user task variant requests
-- Created: 2026-03-28
-- Description: Adds ON DELETE CASCADE to generated_variant_id foreign key
--              so tasks can be deleted when referenced by user variant requests

-- Drop the existing foreign key constraint
ALTER TABLE user_task_variant_requests
    DROP CONSTRAINT IF EXISTS user_task_variant_requests_generated_variant_id_fkey;

-- Recreate with ON DELETE CASCADE
ALTER TABLE user_task_variant_requests
    ADD CONSTRAINT user_task_variant_requests_generated_variant_id_fkey
    FOREIGN KEY (generated_variant_id)
    REFERENCES ai_generation_variants(id)
    ON DELETE CASCADE;

-- Also add ON DELETE CASCADE to variant_id in votes table for consistency
ALTER TABLE user_task_variant_votes
    DROP CONSTRAINT IF EXISTS user_task_variant_votes_variant_id_fkey;

ALTER TABLE user_task_variant_votes
    ADD CONSTRAINT user_task_variant_votes_variant_id_fkey
    FOREIGN KEY (variant_id)
    REFERENCES ai_generation_variants(id)
    ON DELETE CASCADE;
