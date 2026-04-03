-- Migration: Seed tariff_plans and create/fix promo trigger
-- Date: 2026-04-03
-- Purpose: Initialize FREE/PRO/CORP tariff plans and ensure first 1000 email-verified users get PRO forever

-- Step 1: Seed tariff_plans table with FREE, PRO, CORP
INSERT INTO tariff_plans (code, name, monthly_price_rub, description, limits, is_active)
VALUES
  ('FREE', 'Free', 0,       'Базовый бесплатный доступ', '{}'::jsonb, true),
  ('PRO',  'Pro',  499.00,  'Расширенный доступ',        '{}'::jsonb, true),
  ('CORP', 'Corp', 1999.00, 'Корпоративный доступ',      '{}'::jsonb, true)
ON CONFLICT (code) DO NOTHING;

-- Step 2: Create or replace the trigger function
-- When a user verifies their email, grant them PRO for life if they're in the first 1000
CREATE OR REPLACE FUNCTION grant_early_promo_on_email_verified()
RETURNS trigger AS $$
DECLARE
    promo_count BIGINT;
    pro_plan_id BIGINT;
BEGIN
    -- Only fire on first email verification (NEW has value, OLD didn't)
    IF NEW.email_verified_at IS NULL OR OLD.email_verified_at IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Serialize to prevent race conditions on the first 1000 check
    PERFORM pg_advisory_xact_lock(431001);

    -- If user already has a promo tariff, skip
    IF EXISTS (
        SELECT 1 FROM user_tariffs
        WHERE user_id = NEW.id AND is_promo = TRUE
    ) THEN
        RETURN NEW;
    END IF;

    -- Count existing promo users
    SELECT COUNT(*) INTO promo_count FROM user_tariffs WHERE is_promo = TRUE;
    IF promo_count >= 1000 THEN
        -- Already granted 1000 promos, no more
        RETURN NEW;
    END IF;

    -- Get the PRO plan ID
    SELECT id INTO pro_plan_id FROM tariff_plans WHERE code = 'PRO' LIMIT 1;
    IF pro_plan_id IS NULL THEN
        -- tariff_plans not seeded yet, bail safely
        RETURN NEW;
    END IF;

    -- Upgrade existing active tariff to PRO, or insert PRO if none exists
    UPDATE user_tariffs
    SET tariff_id = pro_plan_id,
        is_promo  = TRUE,
        source    = COALESCE(source, 'early_1000')
    WHERE user_id = NEW.id AND valid_to IS NULL;

    -- If no active tariff was found/updated, insert a new PRO row
    IF NOT FOUND THEN
        INSERT INTO user_tariffs (user_id, tariff_id, is_promo, source)
        VALUES (NEW.id, pro_plan_id, TRUE, 'early_1000');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Step 3: Create trigger if it doesn't exist
-- The trigger fires AFTER email_verified_at is set on the users table
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_users_email_verified_promo'
    ) THEN
        CREATE TRIGGER trg_users_email_verified_promo
        AFTER UPDATE OF email_verified_at ON users
        FOR EACH ROW
        EXECUTE FUNCTION grant_early_promo_on_email_verified();
    END IF;
END $$;
