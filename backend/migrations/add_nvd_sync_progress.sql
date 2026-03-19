-- Add progress-tracking columns for background NVD sync + embeddings.
-- Run: psql $DATABASE_URL -f backend/migrations/add_nvd_sync_progress.sql

CREATE TABLE IF NOT EXISTS nvd_sync_log (
    id BIGSERIAL PRIMARY KEY,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    fetched_count INTEGER,
    inserted_count INTEGER,
    embedding_total INTEGER NOT NULL DEFAULT 0,
    embedding_completed INTEGER NOT NULL DEFAULT 0,
    embedding_failed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'success',
    error TEXT
);

ALTER TABLE nvd_sync_log ADD COLUMN IF NOT EXISTS fetched_count INTEGER;
ALTER TABLE nvd_sync_log ADD COLUMN IF NOT EXISTS embedding_total INTEGER NOT NULL DEFAULT 0;
ALTER TABLE nvd_sync_log ADD COLUMN IF NOT EXISTS embedding_completed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE nvd_sync_log ADD COLUMN IF NOT EXISTS embedding_failed INTEGER NOT NULL DEFAULT 0;

UPDATE nvd_sync_log
SET fetched_count = COALESCE(fetched_count, inserted_count, 0)
WHERE fetched_count IS NULL;

UPDATE nvd_sync_log
SET embedding_total = COALESCE(embedding_total, inserted_count, 0)
WHERE embedding_total IS NULL;

UPDATE nvd_sync_log
SET embedding_completed = COALESCE(embedding_completed, embedding_total, 0)
WHERE embedding_completed IS NULL;

UPDATE nvd_sync_log
SET embedding_failed = COALESCE(embedding_failed, 0)
WHERE embedding_failed IS NULL;

CREATE INDEX IF NOT EXISTS idx_nvd_sync_log_fetched_at ON nvd_sync_log(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_nvd_sync_log_status_fetched_at ON nvd_sync_log(status, fetched_at DESC);
