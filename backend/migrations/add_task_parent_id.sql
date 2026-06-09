-- Добавляем parent_id в таблицу tasks для связи с пользовательским контентом (UGC)
ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS parent_id BIGINT REFERENCES tasks(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_parent_id ON tasks(parent_id);
