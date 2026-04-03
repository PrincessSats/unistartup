-- Migration: Backfill all existing users to PRO plan
-- Date: 2026-04-03
-- Purpose: Give all existing users PRO access retroactively

-- Step 1: Upgrade users who already have an active tariff (likely FREE) to PRO
UPDATE user_tariffs
SET tariff_id = (SELECT id FROM tariff_plans WHERE code = 'PRO' LIMIT 1),
    is_promo = TRUE,
    source = COALESCE(source, 'backfill_retroactive')
WHERE valid_to IS NULL
  AND tariff_id != (SELECT id FROM tariff_plans WHERE code = 'PRO' LIMIT 1);

-- Step 2: Insert PRO tariffs for users who have no active tariff
INSERT INTO user_tariffs (user_id, tariff_id, is_promo, source)
SELECT u.id, tp.id, TRUE, 'backfill_retroactive'
FROM users u
CROSS JOIN tariff_plans tp
WHERE tp.code = 'PRO'
  AND NOT EXISTS (
    SELECT 1 FROM user_tariffs ut
    WHERE ut.user_id = u.id AND ut.valid_to IS NULL
  )
ON CONFLICT DO NOTHING;
