-- Миграция: детальное отслеживание статуса в nvd_sync_log
-- Запуск: psql -d hacknet -f backend/migrations/add_detailed_nvd_sync_status.sql

ALTER TABLE nvd_sync_log
ADD COLUMN IF NOT EXISTS total_to_fetch INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS detailed_status TEXT;

COMMENT ON COLUMN nvd_sync_log.total_to_fetch IS 'Всего записей по данному временному окну согласно NVD';
COMMENT ON COLUMN nvd_sync_log.detailed_status IS 'Человекочитаемый статус для панели администратора';
