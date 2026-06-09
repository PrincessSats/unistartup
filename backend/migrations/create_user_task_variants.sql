-- Миграция: таблицы запросов и голосований по вариантам задач
-- Создано: 2026-03-24
-- Описание: добавляет поддержку пользовательских вариантов задач с голосованием

-- Таблица запросов вариантов задач от пользователей
CREATE TABLE user_task_variant_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_request TEXT NOT NULL,
    sanitized_request TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    generated_variant_id UUID REFERENCES ai_generation_variants(id),
    failure_reason TEXT,
    rejection_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Индексы для user_task_variant_requests
CREATE INDEX idx_user_variant_requests_parent ON user_task_variant_requests(parent_task_id);
CREATE INDEX idx_user_variant_requests_user ON user_task_variant_requests(user_id);
CREATE INDEX idx_user_variant_requests_status ON user_task_variant_requests(status);
CREATE INDEX idx_user_variant_requests_created ON user_task_variant_requests(created_at DESC);

-- Таблица голосований за варианты задач
CREATE TABLE user_task_variant_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id UUID NOT NULL REFERENCES ai_generation_variants(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vote_type TEXT NOT NULL CHECK (vote_type IN ('upvote', 'downvote')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_variant_user_vote UNIQUE (variant_id, user_id)
);

-- Индексы для user_task_variant_votes
CREATE INDEX idx_variant_votes_variant ON user_task_variant_votes(variant_id);
CREATE INDEX idx_variant_votes_user ON user_task_variant_votes(user_id);

-- Комментарии к таблицам
COMMENT ON TABLE user_task_variant_requests IS 'Запросы пользователей на генерацию вариантов задач';
COMMENT ON TABLE user_task_variant_votes IS 'Голоса сообщества за пользовательские варианты задач';

-- Комментарии к колонкам
COMMENT ON COLUMN user_task_variant_requests.status IS 'pending, generating, completed, failed';
COMMENT ON COLUMN user_task_variant_votes.vote_type IS 'upvote или downvote';
