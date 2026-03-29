-- Add parent_id to tasks table for UGC (User-Generated Content) relationship
ALTER TABLE tasks
    ADD COLUMN IF NOT EXISTS parent_id BIGINT REFERENCES tasks(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_parent_id ON tasks(parent_id);
