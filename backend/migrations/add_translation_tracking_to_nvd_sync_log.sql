-- Migration: Add translation tracking columns to nvd_sync_log
-- Run: psql -d hacknet -f backend/migrations/add_translation_tracking_to_nvd_sync_log.sql

-- Add translation tracking columns (parallel to embedding columns)
ALTER TABLE nvd_sync_log
ADD COLUMN IF NOT EXISTS translation_total INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS translation_completed INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS translation_failed INTEGER NOT NULL DEFAULT 0;

-- Add comment for documentation
COMMENT ON COLUMN nvd_sync_log.translation_total IS 'Total number of kb_entries requiring translation';
COMMENT ON COLUMN nvd_sync_log.translation_completed IS 'Number of entries successfully translated to Russian';
COMMENT ON COLUMN nvd_sync_log.translation_failed IS 'Number of entries that failed translation';

-- Create index for monitoring translation progress
CREATE INDEX IF NOT EXISTS idx_nvd_sync_log_translation_progress
    ON nvd_sync_log(translation_total, translation_completed, translation_failed)
    WHERE status IN ('translating', 'embedding');

