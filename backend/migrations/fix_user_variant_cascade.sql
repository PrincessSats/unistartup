-- Миграция: исправление каскадного удаления для запросов вариантов задач
-- Создано: 2026-03-28
-- Описание: добавляет ON DELETE CASCADE на внешний ключ generated_variant_id,
--           чтобы задачи можно было удалять при наличии связанных вариантов

-- Удаляем существующий внешний ключ
ALTER TABLE user_task_variant_requests
    DROP CONSTRAINT IF EXISTS user_task_variant_requests_generated_variant_id_fkey;

-- Пересоздаём с ON DELETE CASCADE
ALTER TABLE user_task_variant_requests
    ADD CONSTRAINT user_task_variant_requests_generated_variant_id_fkey
    FOREIGN KEY (generated_variant_id)
    REFERENCES ai_generation_variants(id)
    ON DELETE CASCADE;

-- Также добавляем ON DELETE CASCADE на variant_id в таблице голосований для единообразия
ALTER TABLE user_task_variant_votes
    DROP CONSTRAINT IF EXISTS user_task_variant_votes_variant_id_fkey;

ALTER TABLE user_task_variant_votes
    ADD CONSTRAINT user_task_variant_votes_variant_id_fkey
    FOREIGN KEY (variant_id)
    REFERENCES ai_generation_variants(id)
    ON DELETE CASCADE;
