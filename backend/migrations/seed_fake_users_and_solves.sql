-- =============================================================
-- Seed: 1218 fake users + practice solve counts on published tasks
-- Rollback: DELETE FROM users WHERE email LIKE '%@seed.local';
-- =============================================================

BEGIN;

WITH

w1(v) AS (VALUES
    ('zero'),('null'),('void'),('dark'),('neo'),('cyber'),('ghost'),('toxic'),
    ('byte'),('hex'),('dead'),('raw'),('liquid'),('frozen'),('static'),('wild'),
    ('mad'),('sly'),('blind'),('lazy'),('broken'),('cold'),('deep'),('gray'),
    ('neon'),('rogue'),('sigma'),('silent'),('sharp'),('pure'),('rapid'),('evil'),
    ('1337'),('0x'),('r00t'),('l33t'),('xX'),('d34d'),('b4d'),('sudo')
),
w2(v) AS (VALUES
    ('hacker'),('coder'),('loader'),('runner'),('hunter'),('wizard'),('ninja'),
    ('dragon'),('wolf'),('fox'),('shark'),('cobra'),('monkey'),('snake'),('hawk'),
    ('crow'),('rat'),('bug'),('node'),('stack'),('shell'),('packet'),('kernel'),
    ('daemon'),('vector'),('proxy'),('nexus'),('matrix'),('signal'),('forge'),
    ('flux'),('nova'),('cipher'),('phantom'),('noob')
),

-- pseudo-random ordering of 40×35=1400 unique combos, take first 1218
combos AS (
    SELECT
        w1.v || '_' || w2.v                             AS uname,
        row_number() OVER (ORDER BY md5(w1.v || w2.v)) AS rn
    FROM w1 CROSS JOIN w2
),

name_grid AS (
    SELECT gs, c.uname
    FROM generate_series(1, 1218) AS gs
    JOIN combos c ON c.rn = gs
),

inserted_users AS (
    INSERT INTO users (email, password_hash, email_verified_at, is_active)
    SELECT
        uname || '@seed.local',
        '$2b$12$KFI6.U7cYiUP1xFT098n8u6T36S6fa9ZKcBcW9MarWkly.wrRbDHq',
        now(),
        FALSE
    FROM name_grid
    RETURNING id
),

id_grid AS (
    SELECT id, row_number() OVER (ORDER BY id) AS rn FROM inserted_users
),

merged AS (
    SELECT g.id, n.uname
    FROM id_grid g JOIN name_grid n ON g.rn = n.gs
),

inserted_profiles AS (
    INSERT INTO user_profiles (user_id, username)
    SELECT id, uname FROM merged
    RETURNING user_id
),

inserted_ratings AS (
    INSERT INTO user_ratings (user_id, practice_rating, contest_rating, first_blood)
    SELECT id, (100 + floor(random() * 401)::int) * 5, 0, 0
    FROM inserted_users
    RETURNING user_id
)

SELECT count(*) AS seeded_users FROM inserted_ratings;

-- Seed practice submissions on published tasks (10–35 per task)
WITH published_tasks AS (
    SELECT
        t.id                             AS task_id,
        t.points,
        tf.flag_id,
        (10 + floor(random() * 26)::int) AS target_solves
    FROM tasks t
    JOIN task_flags tf ON tf.task_id = t.id AND tf.flag_id = 'main'
    WHERE t.state = 'published'
),
seed_users AS (
    SELECT id FROM users WHERE email LIKE '%@seed.local'
)
INSERT INTO submissions (
    contest_id, task_id, user_id, flag_id,
    submitted_value, is_correct, awarded_points
)
SELECT NULL, pt.task_id, picked.id, pt.flag_id, 'seed-solve', TRUE, pt.points
FROM published_tasks pt
CROSS JOIN LATERAL (
    SELECT id FROM seed_users ORDER BY random() LIMIT pt.target_solves
) picked;

COMMIT;
