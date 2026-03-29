-- Migration: Add detailed status tracking to nvd_sync_log
-- Run: psql -d hacknet -f backend/migrations/add_detailed_nvd_sync_status.sql

ALTER TABLE nvd_sync_log
ADD COLUMN IF NOT EXISTS total_to_fetch INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS detailed_status TEXT;

COMMENT ON COLUMN nvd_sync_log.total_to_fetch IS 'Total records reported by NVD for the time window';
COMMENT ON COLUMN nvd_sync_log.detailed_status IS 'Human-readable status for the admin panel';
