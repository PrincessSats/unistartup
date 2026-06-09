-- Миграция: перевод всех существующих пользователей на тариф PRO
-- Дата: 2026-04-03
-- Цель: ретроактивно выдать PRO всем существующим пользователям

-- Шаг 1: обновляем пользователей с активным тарифом (скорее всего FREE) до PRO
UPDATE user_tariffs
SET tariff_id = (SELECT id FROM tariff_plans WHERE code = 'PRO' LIMIT 1),
    is_promo = TRUE,
    source = COALESCE(source, 'backfill_retroactive')
WHERE valid_to IS NULL
  AND tariff_id != (SELECT id FROM tariff_plans WHERE code = 'PRO' LIMIT 1);

-- Шаг 2: вставляем PRO тем, у кого нет активного тарифа
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
