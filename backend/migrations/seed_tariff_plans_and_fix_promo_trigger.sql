-- Миграция: заполнить tariff_plans и создать/исправить promo-триггер
-- Дата: 2026-04-03
-- Цель: создать тарифы FREE/PRO/CORP и выдать первым 1000 подтверждённым пользователям PRO навсегда

-- Шаг 1: заполняем таблицу tariff_plans тарифами FREE, PRO, CORP
INSERT INTO tariff_plans (code, name, monthly_price_rub, description, limits, is_active)
VALUES
  ('FREE', 'Free', 0,       'Базовый бесплатный доступ', '{}'::jsonb, true),
  ('PRO',  'Pro',  499.00,  'Расширенный доступ',        '{}'::jsonb, true),
  ('CORP', 'Corp', 1999.00, 'Корпоративный доступ',      '{}'::jsonb, true)
ON CONFLICT (code) DO NOTHING;

-- Шаг 2: создаём/заменяем функцию триггера
-- При верификации email выдаём PRO навсегда, если пользователь среди первых 1000
CREATE OR REPLACE FUNCTION grant_early_promo_on_email_verified()
RETURNS trigger AS $$
DECLARE
    promo_count BIGINT;
    pro_plan_id BIGINT;
BEGIN
    -- Срабатываем только при первой верификации email (NEW заполнен, OLD был NULL)
    IF NEW.email_verified_at IS NULL OR OLD.email_verified_at IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Сериализуем, чтобы избежать гонки при проверке первой 1000
    PERFORM pg_advisory_xact_lock(431001);

    -- Если у пользователя уже есть промо-тариф, пропускаем
    IF EXISTS (
        SELECT 1 FROM user_tariffs
        WHERE user_id = NEW.id AND is_promo = TRUE
    ) THEN
        RETURN NEW;
    END IF;

    -- Считаем текущих промо-пользователей
    SELECT COUNT(*) INTO promo_count FROM user_tariffs WHERE is_promo = TRUE;
    IF promo_count >= 1000 THEN
        -- Уже выдано 1000 промо, больше не выдаём
        RETURN NEW;
    END IF;

    -- Получаем ID тарифа PRO
    SELECT id INTO pro_plan_id FROM tariff_plans WHERE code = 'PRO' LIMIT 1;
    IF pro_plan_id IS NULL THEN
        -- tariff_plans ещё не заполнена, выходим безопасно
        RETURN NEW;
    END IF;

    -- Обновляем активный тариф до PRO или вставляем PRO, если тарифа нет
    UPDATE user_tariffs
    SET tariff_id = pro_plan_id,
        is_promo  = TRUE,
        source    = COALESCE(source, 'early_1000')
    WHERE user_id = NEW.id AND valid_to IS NULL;

    -- Если активный тариф не найден/не обновлён, вставляем новый PRO
    IF NOT FOUND THEN
        INSERT INTO user_tariffs (user_id, tariff_id, is_promo, source)
        VALUES (NEW.id, pro_plan_id, TRUE, 'early_1000');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Шаг 3: создаём триггер, если его ещё нет
-- Триггер срабатывает AFTER UPDATE email_verified_at в таблице users
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
