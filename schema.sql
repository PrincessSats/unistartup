-- ============================================================
-- HackNet Platform — Full Database Schema
-- Reflects current production state. Apply to a fresh DB.
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Functions
-- ============================================================

CREATE OR REPLACE FUNCTION cleanup_old_audit_logs(retention_days integer DEFAULT 365)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM audit_logs
    WHERE created_at < (now() - (retention_days || ' days')::interval)
    AND action NOT IN (
        'auth.login.failed',
        'security.rate_limit_exceeded',
        'security.xss_attempt',
        'security.sql_injection_attempt'
    );
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

CREATE OR REPLACE FUNCTION grant_early_promo_on_email_verified()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    promo_count BIGINT;
    pro_plan_id BIGINT;
BEGIN
    -- Only fire on first email verification
    IF NEW.email_verified_at IS NULL OR OLD.email_verified_at IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Serialize to prevent race conditions on the first 1000 check
    PERFORM pg_advisory_xact_lock(431001);

    IF EXISTS (
        SELECT 1 FROM user_tariffs
        WHERE user_id = NEW.id AND is_promo = TRUE
    ) THEN
        RETURN NEW;
    END IF;

    SELECT COUNT(*) INTO promo_count FROM user_tariffs WHERE is_promo = TRUE;
    IF promo_count >= 1000 THEN
        RETURN NEW;
    END IF;

    SELECT id INTO pro_plan_id FROM tariff_plans WHERE code = 'PRO' LIMIT 1;
    IF pro_plan_id IS NULL THEN
        RETURN NEW;
    END IF;

    UPDATE user_tariffs
    SET tariff_id = pro_plan_id,
        is_promo  = TRUE,
        source    = COALESCE(source, 'early_1000')
    WHERE user_id = NEW.id AND valid_to IS NULL;

    IF NOT FOUND THEN
        INSERT INTO user_tariffs (user_id, tariff_id, is_promo, source)
        VALUES (NEW.id, pro_plan_id, TRUE, 'early_1000');
    END IF;

    RETURN NEW;
END;
$$;

-- ============================================================
-- 1. Users (auth)
-- ============================================================

CREATE TABLE users (
    id                      BIGSERIAL PRIMARY KEY,
    email                   TEXT NOT NULL UNIQUE,
    password_hash           TEXT NOT NULL,
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    email_verified_at       TIMESTAMPTZ,
    password_changed_at     TIMESTAMPTZ,
    failed_login_attempts   INTEGER NOT NULL DEFAULT 0,
    last_failed_login_at    TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_failed_login ON users(failed_login_attempts) WHERE failed_login_attempts > 0;
CREATE INDEX idx_users_password_changed ON users(password_changed_at);

-- ============================================================
-- 2. User profiles and roles
-- ============================================================

CREATE TABLE user_profiles (
    user_id         BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    username        TEXT NOT NULL UNIQUE,
    role            TEXT NOT NULL DEFAULT 'participant',  -- 'admin' | 'author' | 'participant'
    bio             TEXT,
    avatar_url      TEXT,
    locale          TEXT DEFAULT 'ru-RU',
    timezone        TEXT DEFAULT 'Europe/Moscow',
    last_login      TIMESTAMPTZ,
    onboarding_status TEXT                               -- NULL | pending | dismissed | completed
);

CREATE INDEX idx_user_profiles_username ON user_profiles(username);
CREATE INDEX idx_user_profiles_username_lower ON user_profiles(lower(username));

-- ============================================================
-- 3. Ratings
-- ============================================================

CREATE TABLE user_ratings (
    user_id             BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    contest_rating      INTEGER NOT NULL DEFAULT 0,
    practice_rating     INTEGER NOT NULL DEFAULT 0,
    first_blood         INTEGER NOT NULL DEFAULT 0 CHECK (first_blood >= 0),
    last_updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_user_ratings_contest_order ON user_ratings(contest_rating DESC, first_blood DESC, user_id);
CREATE INDEX idx_user_ratings_practice_order ON user_ratings(practice_rating DESC, first_blood DESC, user_id);

-- ============================================================
-- 3.1 Feedback
-- ============================================================

CREATE TABLE feedback (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic       TEXT NOT NULL,
    message     TEXT NOT NULL,
    resolved    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_feedback_id ON feedback(id);

-- ============================================================
-- 3.2 Auth — rotating refresh tokens
-- ============================================================

CREATE TABLE auth_refresh_tokens (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    rotated_to_id   BIGINT REFERENCES auth_refresh_tokens(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at    TIMESTAMPTZ,
    user_agent      TEXT,
    ip_address      TEXT,
    user_agent_hash VARCHAR(64)
);

CREATE UNIQUE INDEX idx_auth_refresh_tokens_hash ON auth_refresh_tokens(token_hash);
CREATE INDEX idx_auth_refresh_tokens_active_user ON auth_refresh_tokens(user_id, revoked_at, expires_at);
CREATE INDEX idx_auth_refresh_tokens_expires_at ON auth_refresh_tokens(expires_at);
CREATE INDEX idx_auth_refresh_tokens_user_agent_hash ON auth_refresh_tokens(user_agent_hash);

-- ============================================================
-- 3.3 Auth — password reset tokens
-- ============================================================

CREATE TABLE auth_password_reset_tokens (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    used_at     TIMESTAMPTZ,
    CONSTRAINT no_reuse CHECK (used_at IS NULL OR used_at <= expires_at)
);

CREATE INDEX idx_password_reset_tokens_user_id ON auth_password_reset_tokens(user_id);
CREATE INDEX idx_password_reset_tokens_expires_at ON auth_password_reset_tokens(expires_at);

-- ============================================================
-- 3.4 Auth — OAuth identity bindings
-- ============================================================

CREATE TABLE user_auth_identities (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider            TEXT NOT NULL,
    provider_user_id    TEXT NOT NULL,
    provider_email      TEXT,
    provider_login      TEXT,
    provider_avatar_url TEXT,
    raw_profile_json    JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at       TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_user_auth_identities_provider_subject ON user_auth_identities(provider, provider_user_id);
CREATE UNIQUE INDEX idx_user_auth_identities_user_provider ON user_auth_identities(user_id, provider);
CREATE INDEX idx_user_auth_identities_email ON user_auth_identities(provider_email);

-- ============================================================
-- 3.5 Auth — registration flows (magic-link / OAuth)
-- ============================================================

CREATE TABLE auth_registration_flows (
    id                        BIGSERIAL PRIMARY KEY,
    intent                    TEXT NOT NULL DEFAULT 'register',
    source                    TEXT NOT NULL,
    email                     TEXT,
    email_verified_at         TIMESTAMPTZ,
    terms_accepted_at         TIMESTAMPTZ,
    marketing_opt_in          BOOLEAN NOT NULL DEFAULT FALSE,
    marketing_opt_in_at       TIMESTAMPTZ,
    provider                  TEXT,
    provider_user_id          TEXT,
    provider_email            TEXT,
    provider_login            TEXT,
    provider_avatar_url       TEXT,
    provider_raw_profile_json JSONB,
    oauth_state_hash          TEXT,
    oauth_code_verifier       TEXT,
    magic_link_token_hash     TEXT,
    magic_link_expires_at     TIMESTAMPTZ,
    magic_link_sent_count     INTEGER NOT NULL DEFAULT 0,
    last_magic_link_sent_at   TIMESTAMPTZ,
    magic_link_consumed_at    TIMESTAMPTZ,
    expires_at                TIMESTAMPTZ NOT NULL,
    completed_user_id         BIGINT REFERENCES users(id) ON DELETE SET NULL,
    consumed_at               TIMESTAMPTZ,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_auth_registration_flows_state_hash ON auth_registration_flows(oauth_state_hash);
CREATE UNIQUE INDEX idx_auth_registration_flows_magic_link_hash ON auth_registration_flows(magic_link_token_hash);
CREATE INDEX idx_auth_registration_flows_email ON auth_registration_flows(email);
CREATE INDEX idx_auth_registration_flows_expires_at ON auth_registration_flows(expires_at);

-- ============================================================
-- 3.6 Registration questionnaire answers
-- ============================================================

CREATE TABLE user_registration_data (
    user_id                      BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    registration_source          TEXT NOT NULL,
    terms_accepted_at            TIMESTAMPTZ NOT NULL,
    marketing_opt_in             BOOLEAN NOT NULL DEFAULT FALSE,
    marketing_opt_in_at          TIMESTAMPTZ,
    profession_tags              TEXT[] NOT NULL DEFAULT '{}',
    grade                        TEXT,
    interest_tags                TEXT[] NOT NULL DEFAULT '{}',
    questionnaire_completed_at   TIMESTAMPTZ,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_user_registration_data_source ON user_registration_data(registration_source);

-- ============================================================
-- 3.7 Audit logs (security events)
-- ============================================================

CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(128) NOT NULL,
    resource_type   VARCHAR(64),
    resource_id     BIGINT,
    details         JSONB DEFAULT '{}',
    ip_address      VARCHAR(64),
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_action_created ON audit_logs(action, created_at DESC);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_user_created ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_logs_created_desc ON audit_logs(created_at DESC);

-- ============================================================
-- 4. Tariff plans
-- ============================================================

CREATE TABLE tariff_plans (
    id                  BIGSERIAL PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,       -- 'FREE' | 'PRO' | 'CORP'
    name                TEXT NOT NULL,
    monthly_price_rub   NUMERIC(10,2) NOT NULL DEFAULT 0,
    description         TEXT,
    limits              JSONB DEFAULT '{}',
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 5. User tariffs
-- ============================================================

CREATE TABLE user_tariffs (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tariff_id   BIGINT NOT NULL REFERENCES tariff_plans(id),
    is_promo    BOOLEAN NOT NULL DEFAULT FALSE,
    source      TEXT,                               -- 'early_1000' | 'manual' | 'corp_contract'
    valid_from  TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to    TIMESTAMPTZ,                        -- NULL = currently active
    CONSTRAINT user_tariffs_one_active
        EXCLUDE USING gist (
            user_id WITH =,
            tstzrange(valid_from, COALESCE(valid_to, 'infinity'::timestamptz)) WITH &&
        )
);

CREATE INDEX idx_user_tariffs_is_promo ON user_tariffs(is_promo) WHERE is_promo = TRUE;

-- Trigger: grant PRO to first 1000 email-verified users
CREATE TRIGGER trg_users_email_verified_promo
AFTER UPDATE OF email_verified_at ON users
FOR EACH ROW EXECUTE FUNCTION grant_early_promo_on_email_verified();

-- ============================================================
-- 5.1 Promo codes (landing hunt rewards)
-- ============================================================

CREATE TABLE landing_hunt_sessions (
    id              BIGSERIAL PRIMARY KEY,
    session_token   TEXT NOT NULL UNIQUE,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_landing_hunt_sessions_token ON landing_hunt_sessions(session_token);

CREATE TABLE landing_hunt_session_items (
    session_id  BIGINT NOT NULL REFERENCES landing_hunt_sessions(id) ON DELETE CASCADE,
    bug_key     TEXT NOT NULL,
    found_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, bug_key)
);

CREATE INDEX idx_landing_hunt_session_items_found_at ON landing_hunt_session_items(found_at DESC);

CREATE TABLE promo_codes (
    id                      BIGSERIAL PRIMARY KEY,
    code                    TEXT NOT NULL UNIQUE,
    source                  TEXT NOT NULL,
    reward_points           INTEGER NOT NULL DEFAULT 0,
    expires_at              TIMESTAMPTZ NOT NULL,
    issued_hunt_session_id  BIGINT UNIQUE REFERENCES landing_hunt_sessions(id),
    redeemed_by_user_id     BIGINT REFERENCES users(id),
    redeemed_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_promo_codes_code ON promo_codes(code);
CREATE UNIQUE INDEX idx_promo_codes_issued_hunt_session_id ON promo_codes(issued_hunt_session_id);
CREATE UNIQUE INDEX idx_promo_codes_landing_redeemed_user_unique
    ON promo_codes(redeemed_by_user_id)
    WHERE source = 'landing_hunt' AND redeemed_by_user_id IS NOT NULL;
CREATE INDEX idx_promo_codes_redeemed_by_user_id ON promo_codes(redeemed_by_user_id);
CREATE INDEX idx_promo_codes_source_expires_at ON promo_codes(source, expires_at);

-- ============================================================
-- 6. Knowledge base (CVE / vulnerabilities)
-- ============================================================

CREATE TABLE kb_entries (
    id                  BIGSERIAL PRIMARY KEY,
    source              TEXT NOT NULL,          -- 'nvd' | 'cve' | 'blog' | 'internal'
    source_id           TEXT,
    cve_id              TEXT,
    raw_en_text         TEXT,
    ru_title            TEXT,
    ru_summary          TEXT,
    ru_explainer        TEXT,
    tags                TEXT[] DEFAULT '{}',
    difficulty          INTEGER,
    embedding           vector(256),
    cwe_ids             TEXT[] DEFAULT '{}',
    cvss_base_score     REAL,
    cvss_vector         TEXT,
    attack_vector       TEXT,
    attack_complexity   TEXT,
    affected_products   TEXT[] DEFAULT '{}',
    cve_metadata        JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_kb_entries_cve_id ON kb_entries(cve_id);
CREATE INDEX idx_kb_entries_tags_gin ON kb_entries USING gin(tags);
CREATE INDEX idx_kb_entries_cwe_ids_gin ON kb_entries USING gin(cwe_ids);
CREATE INDEX idx_kb_entries_cvss_score ON kb_entries(cvss_base_score) WHERE cvss_base_score IS NOT NULL;
CREATE INDEX idx_kb_entries_attack_vector ON kb_entries(attack_vector) WHERE attack_vector IS NOT NULL;
CREATE INDEX idx_kb_entries_updated_created_desc ON kb_entries(COALESCE(updated_at, created_at) DESC);
CREATE INDEX idx_kb_entries_embedding_hnsw ON kb_entries USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);

-- ============================================================
-- 6.1 Knowledge base comments
-- ============================================================

CREATE TABLE kb_comments (
    id              BIGSERIAL PRIMARY KEY,
    kb_entry_id     BIGINT NOT NULL REFERENCES kb_entries(id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id       BIGINT REFERENCES kb_comments(id) ON DELETE CASCADE,
    body            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'published', -- published | hidden | deleted | pending
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_kb_comments_entry_created ON kb_comments(kb_entry_id, created_at DESC);
CREATE INDEX idx_kb_comments_user_created ON kb_comments(user_id, created_at DESC);
CREATE INDEX idx_kb_comments_parent ON kb_comments(parent_id);

-- ============================================================
-- 6.2 NVD sync log
-- ============================================================

CREATE TABLE nvd_sync_log (
    id                      BIGSERIAL PRIMARY KEY,
    fetched_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    window_start            TIMESTAMPTZ,
    window_end              TIMESTAMPTZ,
    fetched_count           INTEGER,
    inserted_count          INTEGER,
    embedding_total         INTEGER NOT NULL DEFAULT 0,
    embedding_completed     INTEGER NOT NULL DEFAULT 0,
    embedding_failed        INTEGER NOT NULL DEFAULT 0,
    translation_total       INTEGER NOT NULL DEFAULT 0,
    translation_completed   INTEGER NOT NULL DEFAULT 0,
    translation_failed      INTEGER NOT NULL DEFAULT 0,
    total_to_fetch          INTEGER NOT NULL DEFAULT 0,
    detailed_status         TEXT,
    status                  TEXT NOT NULL DEFAULT 'success', -- fetching | embedding | translating | success | failed
    error                   TEXT,
    event_log               TEXT  -- JSON array: [{"timestamp":"...", "stage":"...", "message":"..."}]
);

CREATE INDEX idx_nvd_sync_log_fetched_at ON nvd_sync_log(fetched_at DESC);
CREATE INDEX idx_nvd_sync_log_status_fetched_at ON nvd_sync_log(status, fetched_at DESC);
CREATE INDEX idx_nvd_sync_log_translation_progress
    ON nvd_sync_log(translation_total, translation_completed, translation_failed)
    WHERE status IN ('translating', 'embedding');

-- ============================================================
-- 7. Tasks (CTF challenges)
-- ============================================================

CREATE TABLE tasks (
    id                          BIGSERIAL PRIMARY KEY,
    title                       TEXT NOT NULL,
    category                    TEXT NOT NULL,
    difficulty                  INTEGER NOT NULL,   -- 1-10
    points                      INTEGER NOT NULL DEFAULT 100,
    tags                        TEXT[] DEFAULT '{}',
    task_kind                   TEXT NOT NULL DEFAULT 'contest',    -- 'contest' | 'practice'
    access_type                 TEXT NOT NULL DEFAULT 'just_flag',  -- 'vpn' | 'vm' | 'link' | 'file' | 'chat' | 'just_flag'
    language                    TEXT NOT NULL DEFAULT 'ru',
    story                       TEXT,
    participant_description     TEXT,
    chat_system_prompt_template TEXT,
    chat_user_message_max_chars INTEGER NOT NULL DEFAULT 150,
    chat_model_max_output_tokens INTEGER NOT NULL DEFAULT 256,
    chat_session_ttl_minutes    INTEGER NOT NULL DEFAULT 180,
    state                       TEXT NOT NULL DEFAULT 'draft',      -- draft | ready | published | archived
    kb_entry_id                 BIGINT REFERENCES kb_entries(id),
    llm_raw_response            JSONB,
    created_by                  BIGINT REFERENCES users(id),
    embedding                   vector(256),
    parent_id                   BIGINT REFERENCES tasks(id),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT tasks_access_type_check
        CHECK (access_type IN ('vpn', 'vm', 'link', 'file', 'chat', 'just_flag')),
    CONSTRAINT tasks_chat_user_message_max_chars_check
        CHECK (chat_user_message_max_chars BETWEEN 20 AND 500),
    CONSTRAINT tasks_chat_model_max_output_tokens_check
        CHECK (chat_model_max_output_tokens BETWEEN 32 AND 1024),
    CONSTRAINT tasks_chat_session_ttl_minutes_check
        CHECK (chat_session_ttl_minutes BETWEEN 15 AND 720),
    CONSTRAINT tasks_chat_prompt_template_required_check
        CHECK (
            access_type <> 'chat'
            OR (
                chat_system_prompt_template IS NOT NULL
                AND POSITION('{{FLAG}}' IN chat_system_prompt_template) > 0
            )
        )
);

CREATE INDEX idx_tasks_tags_gin ON tasks USING gin(tags);
CREATE INDEX idx_tasks_embedding_hnsw ON tasks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
CREATE INDEX idx_tasks_parent_id ON tasks(parent_id);
CREATE INDEX idx_tasks_practice_ready_created ON tasks(task_kind, state, created_at DESC, id DESC);
CREATE INDEX idx_tasks_practice_ready_category_created ON tasks(task_kind, state, lower(category), created_at DESC, id DESC);
CREATE INDEX idx_tasks_practice_ready_difficulty_created ON tasks(task_kind, state, difficulty, created_at DESC, id DESC);

-- ============================================================
-- 7.1 Task flags
-- ============================================================

CREATE TABLE task_flags (
    id              BIGSERIAL PRIMARY KEY,
    task_id         BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    flag_id         TEXT NOT NULL,      -- 'main' | 'stage1' | 'bonus'
    format          TEXT NOT NULL,
    expected_value  TEXT,
    description     TEXT,
    UNIQUE (task_id, flag_id)
);

CREATE INDEX idx_task_flags_task_id ON task_flags(task_id, id);

-- ============================================================
-- 7.2 Task materials (files, links, VPN configs, etc.)
-- ============================================================

CREATE TABLE task_materials (
    id          BIGSERIAL PRIMARY KEY,
    task_id     BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    type        TEXT NOT NULL,  -- 'vpn' | 'vm' | 'link' | 'file' | 'credentials' | 'service' | 'other'
    name        TEXT NOT NULL,
    description TEXT,
    url         TEXT,
    storage_key TEXT,
    meta        JSONB DEFAULT '{}'
);

CREATE INDEX idx_task_materials_task_id ON task_materials(task_id, id);

-- ============================================================
-- 7.3 Author solutions
-- ============================================================

CREATE TABLE task_author_solutions (
    task_id                 BIGINT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    summary                 TEXT,
    creation_solution       TEXT,
    steps                   JSONB,
    difficulty_rationale    TEXT,
    implementation_notes    TEXT
);

-- ============================================================
-- 7.4 AI task generation pipeline
-- ============================================================

CREATE TABLE ai_base_images (
    id          SERIAL PRIMARY KEY,
    category    VARCHAR(50) NOT NULL,
    s3_key      VARCHAR(500) NOT NULL,
    format      VARCHAR(10) NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE ai_xss_templates (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    difficulty      VARCHAR(20) NOT NULL,
    xss_type        VARCHAR(50) NOT NULL,
    html_template   TEXT NOT NULL,
    payload_example TEXT,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE ai_generation_batches (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requested_by            INTEGER REFERENCES users(id),
    task_type               VARCHAR(50) NOT NULL,
    difficulty              VARCHAR(20) NOT NULL,
    num_variants            INTEGER NOT NULL DEFAULT 5,
    attempt                 INTEGER NOT NULL DEFAULT 1,
    status                  VARCHAR(20) NOT NULL DEFAULT 'pending',
    group_mean_reward       DOUBLE PRECISION,
    group_std_reward        DOUBLE PRECISION,
    pass_rate               DOUBLE PRECISION,
    selected_variant_id     UUID,
    failure_reasons_summary JSONB,
    rag_context_ids         INTEGER[],
    rag_context_summary     TEXT,
    rag_query_text          TEXT,
    current_stage           VARCHAR(50) DEFAULT 'pending',
    stage_started_at        TIMESTAMPTZ,
    stage_meta              JSONB,
    created_at              TIMESTAMPTZ DEFAULT now(),
    completed_at            TIMESTAMPTZ
);

CREATE INDEX idx_ai_gen_batches_status ON ai_generation_batches(status);

CREATE TABLE ai_generation_variants (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID NOT NULL REFERENCES ai_generation_batches(id) ON DELETE CASCADE,
    variant_number      INTEGER NOT NULL,
    model_used          VARCHAR(100),
    temperature         DOUBLE PRECISION,
    tokens_input        INTEGER,
    tokens_output       INTEGER,
    generation_time_ms  INTEGER,
    generated_spec      JSONB,
    artifact_result     JSONB,
    reward_checks       JSONB,
    reward_total        DOUBLE PRECISION,
    reward_binary       DOUBLE PRECISION,
    passed_all_binary   BOOLEAN DEFAULT FALSE,
    quality_score       DOUBLE PRECISION,
    quality_details     JSONB,
    advantage           DOUBLE PRECISION,
    rank_in_group       INTEGER,
    is_selected         BOOLEAN DEFAULT FALSE,
    published_task_id   INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
    failure_reason      TEXT,
    embedding           vector(256),
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_ai_gen_variants_batch ON ai_generation_variants(batch_id);
CREATE INDEX idx_ai_gen_variants_selected ON ai_generation_variants(is_selected) WHERE is_selected = TRUE;
CREATE INDEX idx_ai_gen_variants_embedding
    ON ai_generation_variants USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)
    WHERE embedding IS NOT NULL;

CREATE TABLE ai_generation_analytics (
    id                  SERIAL PRIMARY KEY,
    task_type           VARCHAR(50) NOT NULL,
    difficulty          VARCHAR(20) NOT NULL,
    period_date         DATE NOT NULL,
    total_variants      INTEGER DEFAULT 0,
    passed_variants     INTEGER DEFAULT 0,
    avg_reward          DOUBLE PRECISION,
    avg_quality_score   DOUBLE PRECISION,
    common_failures     JSONB,
    best_temperature    DOUBLE PRECISION,
    updated_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (task_type, difficulty, period_date)
);

CREATE INDEX idx_ai_gen_analytics_lookup ON ai_generation_analytics(task_type, difficulty, period_date);

-- ============================================================
-- 7.5 User-requested task variants
-- ============================================================

CREATE TABLE user_task_variant_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_task_id      BIGINT NOT NULL REFERENCES tasks(id),
    user_id             BIGINT NOT NULL REFERENCES users(id),
    user_request        TEXT NOT NULL,
    sanitized_request   TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',  -- pending | processing | completed | failed | rejected
    generated_variant_id UUID,
    failure_reason      TEXT,
    rejection_reason    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ
);

CREATE INDEX idx_user_variant_requests_parent ON user_task_variant_requests(parent_task_id);
CREATE INDEX idx_user_variant_requests_user ON user_task_variant_requests(user_id);
CREATE INDEX idx_user_variant_requests_status ON user_task_variant_requests(status);
CREATE INDEX idx_user_variant_requests_created ON user_task_variant_requests(created_at DESC);

CREATE TABLE user_task_variant_votes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id  UUID NOT NULL,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    vote_type   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_task_variant_votes_vote_type_check CHECK (vote_type IN ('upvote', 'downvote')),
    CONSTRAINT uq_variant_user_vote UNIQUE (variant_id, user_id)
);

CREATE INDEX idx_variant_votes_variant ON user_task_variant_votes(variant_id);
CREATE INDEX idx_variant_votes_user ON user_task_variant_votes(user_id);

-- ============================================================
-- 8. Contests (championships)
-- ============================================================

CREATE TABLE contests (
    id                  BIGSERIAL PRIMARY KEY,
    title               TEXT NOT NULL,
    description         TEXT,
    start_at            TIMESTAMPTZ NOT NULL,
    end_at              TIMESTAMPTZ NOT NULL,
    is_public           BOOLEAN NOT NULL DEFAULT FALSE,
    leaderboard_visible BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 8.1 Contest participants
-- ============================================================

CREATE TABLE contest_participants (
    contest_id      BIGINT NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at  TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    PRIMARY KEY (contest_id, user_id)
);

CREATE INDEX idx_contest_participants_contest_joined ON contest_participants(contest_id, joined_at);

-- ============================================================
-- 8.2 Chat task sessions (dynamic flags via LLM)
-- ============================================================

CREATE TABLE task_chat_sessions (
    id              BIGSERIAL PRIMARY KEY,
    task_id         BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contest_id      BIGINT REFERENCES contests(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'active',    -- active | solved
    flag_seed       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    solved_at       TIMESTAMPTZ,
    CONSTRAINT task_chat_sessions_status_check CHECK (status IN ('active', 'solved'))
);

CREATE INDEX idx_task_chat_sessions_task_user_context ON task_chat_sessions(task_id, user_id, contest_id);
CREATE INDEX idx_task_chat_sessions_expiry_unsolved ON task_chat_sessions(expires_at) WHERE status = 'active';
CREATE UNIQUE INDEX idx_task_chat_sessions_active_unique
    ON task_chat_sessions(task_id, user_id, COALESCE(contest_id, 0))
    WHERE status = 'active';

-- ============================================================
-- 8.3 Chat messages within a session
-- ============================================================

CREATE TABLE task_chat_messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  BIGINT NOT NULL REFERENCES task_chat_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,      -- 'user' | 'assistant'
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT task_chat_messages_role_check CHECK (role IN ('user', 'assistant'))
);

CREATE INDEX idx_task_chat_messages_session_created ON task_chat_messages(session_id, created_at ASC, id ASC);

-- ============================================================
-- 9. Contest ↔ Task links
-- ============================================================

CREATE TABLE contest_tasks (
    contest_id                      BIGINT NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
    task_id                         BIGINT NOT NULL REFERENCES tasks(id),
    order_index                     INTEGER NOT NULL DEFAULT 0,
    points_override                 INTEGER,
    override_title                  TEXT,
    override_participant_description TEXT,
    override_tags                   TEXT[],
    override_category               TEXT,
    override_difficulty             INTEGER,
    PRIMARY KEY (contest_id, task_id)
);

CREATE UNIQUE INDEX idx_contest_tasks_order_unique ON contest_tasks(contest_id, order_index);

-- ============================================================
-- 10. Submissions (flag submissions)
-- ============================================================

CREATE TABLE submissions (
    id              BIGSERIAL PRIMARY KEY,
    contest_id      BIGINT REFERENCES contests(id) ON DELETE CASCADE,
    task_id         BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    flag_id         TEXT NOT NULL,
    submitted_value TEXT NOT NULL,
    is_correct      BOOLEAN NOT NULL,
    awarded_points  INTEGER NOT NULL DEFAULT 0,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_submissions_user_contest ON submissions(user_id, contest_id);
CREATE INDEX idx_submissions_contest_correct_submitted ON submissions(contest_id, is_correct, submitted_at, id);
CREATE INDEX idx_submissions_contest_user_correct ON submissions(contest_id, user_id, is_correct, submitted_at DESC);
CREATE INDEX idx_submissions_correct_contest_user_task ON submissions(contest_id, is_correct, user_id, task_id);
CREATE INDEX idx_submissions_correct_user_task_practice ON submissions(user_id, task_id)
    WHERE contest_id IS NULL AND is_correct = TRUE;
CREATE INDEX idx_submissions_practice_task_user_flag_correct ON submissions(task_id, user_id, flag_id)
    WHERE contest_id IS NULL AND is_correct = TRUE;
CREATE INDEX idx_submissions_practice_user_task_all ON submissions(user_id, task_id)
    WHERE contest_id IS NULL;

-- ============================================================
-- 10.1 Practice task starts
-- ============================================================

CREATE TABLE practice_task_starts (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id     BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_practice_task_starts_user_task UNIQUE (user_id, task_id)
);

-- ============================================================
-- 11. Contest task ratings (user votes on tasks)
-- ============================================================

CREATE TABLE contest_task_ratings (
    id          BIGSERIAL PRIMARY KEY,
    contest_id  BIGINT NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
    task_id     BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating      SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    rated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (contest_id, task_id, user_id)
);

-- ============================================================
-- 12. Courses and lessons
-- ============================================================

CREATE TABLE courses (
    id          BIGSERIAL PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    description TEXT,
    level       TEXT,               -- 'beginner' | 'intermediate' | 'advanced'
    is_public   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE course_modules (
    id          BIGSERIAL PRIMARY KEY,
    course_id   BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    order_index INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE lessons (
    id                  BIGSERIAL PRIMARY KEY,
    course_id           BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    module_id           BIGINT REFERENCES course_modules(id),
    title               TEXT NOT NULL,
    slug                TEXT,
    content             TEXT,
    difficulty          INTEGER,
    estimated_minutes   INTEGER
);

CREATE TABLE lesson_tasks (
    lesson_id   BIGINT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    task_id     BIGINT NOT NULL REFERENCES tasks(id),
    order_index INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (lesson_id, task_id)
);

-- ============================================================
-- 13. LLM audit log
-- ============================================================

CREATE TABLE llm_generations (
    id              BIGSERIAL PRIMARY KEY,
    model           TEXT NOT NULL,
    purpose         TEXT NOT NULL,          -- 'task_generation' | 'kb_explainer' | 'feedback'
    input_payload   JSONB NOT NULL,
    output_payload  JSONB,
    kb_entry_id     BIGINT REFERENCES kb_entries(id),
    task_id         BIGINT REFERENCES tasks(id),
    created_by      BIGINT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_llm_generations_purpose ON llm_generations(purpose);

-- ============================================================
-- 14. Prompt templates (editable via admin)
-- ============================================================

CREATE TABLE prompt_templates (
    code        TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT,
    content     TEXT NOT NULL,
    updated_by  BIGINT REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 15. Activity log (contest management events)
-- ============================================================

CREATE TABLE activity_log (
    id          SERIAL PRIMARY KEY,
    admin_id    BIGINT REFERENCES users(id) ON DELETE SET NULL,
    contest_id  BIGINT REFERENCES contests(id) ON DELETE SET NULL,
    event_type  VARCHAR(64) NOT NULL,   -- see EventType enum in models/activity.py
    source      VARCHAR(32) NOT NULL DEFAULT 'admin_action',  -- 'admin_action' | 'system_event' | 'participant_action'
    action      VARCHAR(255) NOT NULL,
    details     JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_activity_log_admin_id ON activity_log(admin_id);
CREATE INDEX idx_activity_log_contest_id ON activity_log(contest_id);
CREATE INDEX idx_activity_log_event_type ON activity_log(event_type);
CREATE INDEX idx_activity_log_source ON activity_log(source);
CREATE INDEX idx_activity_log_created_at ON activity_log(created_at);
CREATE INDEX idx_activity_log_contest_created ON activity_log(contest_id, created_at);
CREATE INDEX idx_activity_log_event_created ON activity_log(event_type, created_at);

-- ============================================================
-- Views
-- ============================================================

CREATE OR REPLACE VIEW v_security_audit AS
SELECT
    id,
    action,
    user_id,
    resource_type,
    resource_id,
    ip_address,
    date_trunc('hour', created_at) AS hour,
    count(*) OVER (
        PARTITION BY action, ip_address, date_trunc('hour', created_at)
    ) AS occurrences_in_hour
FROM audit_logs
WHERE action LIKE 'auth.%' OR action LIKE 'security.%'
ORDER BY created_at DESC;
