-- Migration: Create user task variant requests and votes tables
-- Created: 2026-03-24
-- Description: Adds support for user-generated task variants with voting

-- User task variant requests table
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

-- Indexes for user_task_variant_requests
CREATE INDEX idx_user_variant_requests_parent ON user_task_variant_requests(parent_task_id);
CREATE INDEX idx_user_variant_requests_user ON user_task_variant_requests(user_id);
CREATE INDEX idx_user_variant_requests_status ON user_task_variant_requests(status);
CREATE INDEX idx_user_variant_requests_created ON user_task_variant_requests(created_at DESC);

-- User task variant votes table
CREATE TABLE user_task_variant_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id UUID NOT NULL REFERENCES ai_generation_variants(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vote_type TEXT NOT NULL CHECK (vote_type IN ('upvote', 'downvote')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_variant_user_vote UNIQUE (variant_id, user_id)
);

-- Indexes for user_task_variant_votes
CREATE INDEX idx_variant_votes_variant ON user_task_variant_votes(variant_id);
CREATE INDEX idx_variant_votes_user ON user_task_variant_votes(user_id);

-- Comment on tables
COMMENT ON TABLE user_task_variant_requests IS 'User requests for generating task variants';
COMMENT ON TABLE user_task_variant_votes IS 'Community votes on user-generated task variants';

-- Comment on columns
COMMENT ON COLUMN user_task_variant_requests.status IS 'pending, generating, completed, failed';
COMMENT ON COLUMN user_task_variant_votes.vote_type IS 'upvote or downvote';
