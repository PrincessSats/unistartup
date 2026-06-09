-- Миграция: добавляем колонки отслеживания перевода в nvd_sync_log
-- Запуск: psql -d hacknet -f backend/migrations/add_translation_tracking_to_nvd_sync_log.sql

-- Колонки отслеживания перевода (аналогично колонкам эмбеддингов)
ALTER TABLE nvd_sync_log
ADD COLUMN IF NOT EXISTS translation_total INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS translation_completed INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS translation_failed INTEGER NOT NULL DEFAULT 0;

-- Комментарии к колонкам
COMMENT ON COLUMN nvd_sync_log.translation_total IS 'Всего kb_entries, требующих перевода';
COMMENT ON COLUMN nvd_sync_log.translation_completed IS 'Количество успешно переведённых на русский записей';
COMMENT ON COLUMN nvd_sync_log.translation_failed IS 'Количество записей с ошибкой перевода';

-- Индекс для мониторинга прогресса перевода
CREATE INDEX IF NOT EXISTS idx_nvd_sync_log_translation_progress
    ON nvd_sync_log(translation_total, translation_completed, translation_failed)
    WHERE status IN ('translating', 'embedding');

