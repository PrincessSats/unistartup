"""
Скрипт бэкфила: переводит существующие kb_entries, у которых нет ru_title/ru_summary/ru_explainer.

Запуск из директории backend:
    cd backend
    python -m app.scripts.translate_kb_entries

Или напрямую:
    cd backend
    python app/scripts/translate_kb_entries.py

Примеры:
    # Посчитать записи без перевода (пробный запуск)
    python -m app.scripts.translate_kb_entries --dry-run

    # Протестировать на 5 записях
    python -m app.scripts.translate_kb_entries --limit 5

    # Перевести всё с задержкой 0.5с между записями
    python -m app.scripts.translate_kb_entries

    # Перевести без задержки (быстрее, но риск получить rate limit)
    python -m app.scripts.translate_kb_entries --delay 0

Оценка стоимости (deepseek-v4-flash @ 0.5 руб/1К токенов вход + 0.5 руб/1К токенов выход):
- ~100 токенов вход (заголовок) + ~50 выход = 150 токенов на заголовок
- ~600 токенов вход (summary 3000 символов) + ~300 выход = 900 токенов на summary
- ~2000 токенов вход (explainer 8000 символов) + ~1000 выход = 3000 токенов на explainer
- Итого на CVE: ~4050 токенов × 0.5 руб/1000 = ~2 руб за CVE
- 1000 записей: ~2000 руб
- 3863 записи: ~7700 руб (разовая стоимость полной русской KB)

Прогресс отображается прогресс-баром и логируется в таблицу nvd_sync_log для мониторинга.
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

from app.database import AsyncSessionLocal
from app.services.ai_generator.translation_service import TranslationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Подавляем многословные логи HTTP-клиента
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BATCH_SIZE = 20  # переводим по 20 записей за батч, чтобы не получить rate limit
DELAY_SECONDS = 0.5  # пауза между батчами


async def create_translation_log(session: AsyncSession) -> int:
    """Создаёт запись лога для текущего запуска перевода."""
    result = await session.execute(
        text(
            """
            INSERT INTO nvd_sync_log (
                fetched_at,
                fetched_count,
                inserted_count,
                embedding_total,
                embedding_completed,
                embedding_failed,
                translation_total,
                translation_completed,
                translation_failed,
                status,
                error
            )
            VALUES (
                now(), 0, 0, 0, 0, 0, 0, 0, 0, 'translating', NULL
            )
            RETURNING id
            """
        )
    )
    row = result.fetchone()
    await session.commit()
    return row[0] if row else 0


async def update_translation_progress(
    session: AsyncSession,
    log_id: int,
    completed: int,
    failed: int,
) -> None:
    """Обновляет прогресс перевода в логе."""
    await session.execute(
        text(
            """
            UPDATE nvd_sync_log
            SET translation_completed = :completed,
                translation_failed = :failed
            WHERE id = :log_id
            """
        ),
        {"log_id": log_id, "completed": completed, "failed": failed},
    )
    await session.commit()


async def mark_translation_complete(session: AsyncSession, log_id: int, error: Optional[str]) -> None:
    """Помечает запуск перевода как завершённый или упавший."""
    status = "failed" if error else "success"
    await session.execute(
        text(
            """
            UPDATE nvd_sync_log
            SET status = :status,
                error = :error
            WHERE id = :log_id
            """
        ),
        {"log_id": log_id, "status": status, "error": error[:500] if error else None},
    )
    await session.commit()


async def translate_existing_entries(
    *,
    dry_run: bool = False,
    limit: Optional[int] = None,
    delay_seconds: float = 0.5,
) -> None:
    """
    Переводит все kb_entries, где ru_title IS NULL OR ru_summary IS NULL OR ru_explainer IS NULL.

    Переводит ПОЛНЫЙ контент: ru_title + ru_summary + ru_explainer через deepseek-v4-flash.

    Args:
        dry_run: Если True, только считает записи без перевода
        limit: Максимальное количество записей для перевода (для тестирования)
        delay_seconds: Пауза между записями (секунды), 0 — отключить
    """
    async with AsyncSessionLocal() as session:
        # Считаем записи, которым нужен перевод
        result = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM kb_entries
                WHERE raw_en_text IS NOT NULL
                  AND LENGTH(TRIM(raw_en_text)) > 0
                  AND (
                    ru_title IS NULL OR 
                    ru_summary IS NULL OR 
                    ru_explainer IS NULL
                  )
                """
            )
        )
        total_count = result.scalar() or 0
        logger.info("Found %d entries needing full translation", total_count)

        if total_count == 0:
            logger.info("All entries already have full Russian translation")
            return

        if dry_run:
            logger.info("DRY RUN: Would translate %d entries (full: title+summary+explainer)", total_count)
            return

        # Создаём запись лога
        log_id = await create_translation_log(session)
        logger.info("Created translation log entry: id=%d", log_id)

    translation_svc = TranslationService()
    translated = 0
    failed = 0

    try:
        async with AsyncSessionLocal() as session:
            # Загружаем записи, требующие перевода
            query = text(
                """
                SELECT id, cve_id, raw_en_text
                FROM kb_entries
                WHERE raw_en_text IS NOT NULL
                  AND LENGTH(TRIM(raw_en_text)) > 0
                  AND (
                    ru_title IS NULL OR
                    ru_summary IS NULL OR
                    ru_explainer IS NULL
                  )
                ORDER BY created_at DESC
                """ + (f"LIMIT {limit}" if limit else "")
            )
            result = await session.execute(query)
            entries = result.fetchall()

        total_entries = len(entries)
        logger.info("Translating %d entries (FULL: title + summary + explainer)...", total_entries)

        # Вспомогательная функция для перевода одной записи
        async def translate_single_entry(entry):
            """Переводит одну запись и обновляет прогресс."""
            nonlocal translated, failed
            entry_id, cve_id, raw_en_text = entry

            try:
                result = await translation_svc.translate_full_cve(
                    cve_id or f"entry_{entry_id}",
                    raw_en_text or "",
                )

                if result.ru_title or result.ru_summary or result.ru_explainer:
                    async with AsyncSessionLocal() as session:
                        await session.execute(
                            text(
                                """
                                UPDATE kb_entries
                                SET ru_title = :ru_title,
                                    ru_summary = :ru_summary,
                                    ru_explainer = :ru_explainer
                                WHERE id = :entry_id
                                """
                            ),
                            {
                                "ru_title": result.ru_title or None,
                                "ru_summary": result.ru_summary or None,
                                "ru_explainer": result.ru_explainer or None,
                                "entry_id": entry_id,
                            },
                        )
                        await session.commit()
                    translated += 1
                else:
                    failed += 1
                    logger.warning("Translation returned empty for entry %d", entry_id)

            except Exception as exc:
                failed += 1
                logger.error("Translation failed for entry %d (%s): %s", entry_id, cve_id, exc)

            # Обновляем прогресс в БД каждые 10 записей, чтобы снизить нагрузку
            if (translated + failed) % 10 == 0:
                async with AsyncSessionLocal() as session:
                    await update_translation_progress(session, log_id, translated, failed)

        # Обрабатываем с прогресс-баром (временно отключаем логи, чтобы не ломать одну строку)
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        root_logger.handlers = []  # Временно удаляем все обработчики

        # Открываем /dev/tty для чистого вывода прогресс-бара
        tty_file = None
        try:
            tty_file = open("/dev/tty", "w")
        except OSError:
            pass

        try:
            with tqdm(
                total=total_entries,
                desc="Translating",
                unit="entry",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
                file=tty_file or sys.stdout,
                dynamic_ncols=True,
                mininterval=0.1,
                leave=True,
            ) as progress_bar:
                for entry in entries:
                    await translate_single_entry(entry)
                    progress_bar.update(1)
                    # Задержка между записями (для обхода rate limit)
                    if delay_seconds > 0:
                        await asyncio.sleep(delay_seconds)
        finally:
            if tty_file:
                tty_file.close()
            # Восстанавливаем обработчики логирования
            root_logger.handlers = original_handlers

        # Финальное обновление прогресса в БД
        async with AsyncSessionLocal() as session:
            await update_translation_progress(session, log_id, translated, failed)

        logger.info(
            "Translation complete: %d translated, %d failed out of %d total",
            translated, failed, total_entries,
        )

        await mark_translation_complete(session, log_id, None)

    except Exception as exc:
        logger.error("Translation backfill failed: %s", exc)
        async with AsyncSessionLocal() as session:
            await mark_translation_complete(session, log_id, str(exc))
        raise

    finally:
        await translation_svc.close()


def main():
    parser = argparse.ArgumentParser(description="Translate existing kb_entries to Russian")
    parser.add_argument("--dry-run", action="store_true", help="Count entries without translating")
    parser.add_argument("--limit", type=int, help="Limit number of entries to translate (for testing)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between entries (seconds), set to 0 to disable")
    args = parser.parse_args()

    logger.info("Starting translation backfill (dry_run=%s, limit=%s)", args.dry_run, args.limit)

    asyncio.run(translate_existing_entries(
        dry_run=args.dry_run,
        limit=args.limit,
        delay_seconds=args.delay,
    ))

    logger.info("Done!")


if __name__ == "__main__":
    main()
