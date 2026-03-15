CREATE TABLE IF NOT EXISTS landing_hunt_sessions (
    id BIGSERIAL PRIMARY KEY,
    session_token TEXT NOT NULL UNIQUE,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE landing_hunt_sessions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE landing_hunt_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE landing_hunt_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE UNIQUE INDEX IF NOT EXISTS idx_landing_hunt_sessions_token
    ON landing_hunt_sessions(session_token);

CREATE TABLE IF NOT EXISTS landing_hunt_session_items (
    session_id BIGINT NOT NULL REFERENCES landing_hunt_sessions(id) ON DELETE CASCADE,
    bug_key TEXT NOT NULL,
    found_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, bug_key)
);

ALTER TABLE landing_hunt_session_items ADD COLUMN IF NOT EXISTS found_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_landing_hunt_session_items_found_at
    ON landing_hunt_session_items(found_at DESC);

CREATE TABLE IF NOT EXISTS promo_codes (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    reward_points INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMPTZ NOT NULL,
    issued_hunt_session_id BIGINT UNIQUE REFERENCES landing_hunt_sessions(id) ON DELETE SET NULL,
    redeemed_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    redeemed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'landing_hunt';
ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS reward_points INTEGER NOT NULL DEFAULT 0;
ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS issued_hunt_session_id BIGINT;
ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS redeemed_by_user_id BIGINT;
ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS redeemed_at TIMESTAMPTZ;
ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE UNIQUE INDEX IF NOT EXISTS idx_promo_codes_code
    ON promo_codes(code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_promo_codes_issued_hunt_session_id
    ON promo_codes(issued_hunt_session_id);
CREATE INDEX IF NOT EXISTS idx_promo_codes_source_expires_at
    ON promo_codes(source, expires_at);
CREATE INDEX IF NOT EXISTS idx_promo_codes_redeemed_by_user_id
    ON promo_codes(redeemed_by_user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_promo_codes_landing_redeemed_user_unique
    ON promo_codes(redeemed_by_user_id)
    WHERE source = 'landing_hunt' AND redeemed_by_user_id IS NOT NULL;
