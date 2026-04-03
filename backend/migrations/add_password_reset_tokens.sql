-- Migration: Add password reset tokens table
-- Date: 2026-04-03
-- Issue: auth_password_reset_tokens table missing from local/dev database

CREATE TABLE IF NOT EXISTS auth_password_reset_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    CONSTRAINT no_reuse CHECK (used_at IS NULL OR used_at <= expires_at)
);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON auth_password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_expires_at ON auth_password_reset_tokens(expires_at);
