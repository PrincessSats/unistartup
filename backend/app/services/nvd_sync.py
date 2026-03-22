import argparse
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal


NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
DEFAULT_SLEEP_SECONDS = 6
DEFAULT_HOURS = 24
logger = logging.getLogger(__name__)
SYNC_LOG_COLUMNS = (
    "id, fetched_at, window_start, window_end, fetched_count, inserted_count, "
    "embedding_total, embedding_completed, embedding_failed, "
    "translation_total, translation_completed, translation_failed, "
    "status, error"
)


def sync_log_to_admin_payload(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "log_id": row.get("id"),
        "last_fetch_at": row.get("fetched_at"),
        "window_start": row.get("window_start"),
        "window_end": row.get("window_end"),
        "fetched_count": row.get("fetched_count"),
        "last_inserted": row.get("inserted_count"),
        "embedding_total": row.get("embedding_total") or 0,
        "embedding_completed": row.get("embedding_completed") or 0,
        "embedding_failed": row.get("embedding_failed") or 0,
        "translation_total": row.get("translation_total") or 0,
        "translation_completed": row.get("translation_completed") or 0,
        "translation_failed": row.get("translation_failed") or 0,
        "status": row.get("status"),
        "error": row.get("error"),
    }


def _build_embedding_text(row: Dict[str, Any]) -> str:
    parts = [row.get("cve_id") or "", row.get("raw_en_text") or ""]
    return " ".join(filter(None, parts)).strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_dt(dt: datetime) -> str:
    # NVD expects extended ISO-8601 with UTC offset
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _parse_dt(value: str) -> datetime:
    # Accept ISO-8601 strings with optional "Z"
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _pick_en_description(descriptions: Iterable[Dict[str, Any]]) -> Optional[str]:
    for d in descriptions:
        if d.get("lang") == "en" and d.get("value"):
            return d["value"]
    return None


async def _fetch_page(
    client: httpx.AsyncClient,
    *,
    start: datetime,
    end: datetime,
    start_index: int,
    results_per_page: Optional[int],
    api_key: Optional[str],
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "lastModStartDate": _format_dt(start),
        "lastModEndDate": _format_dt(end),
        "startIndex": start_index,
    }
    if results_per_page is not None:
        params["resultsPerPage"] = results_per_page
    headers = {"User-Agent": "unistartup-nvd-sync/1.0"}
    if api_key:
        headers["apiKey"] = api_key

    resp = await client.get(NVD_BASE_URL, params=params, headers=headers)
    resp.raise_for_status()
    return resp.json()


async def fetch_recent_cves(
    *,
    start: datetime,
    end: datetime,
    api_key: Optional[str],
    results_per_page: Optional[int],
    sleep_seconds: int,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    start_index = 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        while True:
            data = await _fetch_page(
                client,
                start=start,
                end=end,
                start_index=start_index,
                results_per_page=results_per_page,
                api_key=api_key,
            )
            vulns = data.get("vulnerabilities", []) or []
            items.extend(vulns)

            total = data.get("totalResults", 0)
            page_size = data.get("resultsPerPage", len(vulns))
            current_index = data.get("startIndex", start_index)
            next_index = current_index + (page_size or 0)

            if not vulns or next_index >= total:
                break

            start_index = next_index
            if sleep_seconds > 0:
                await asyncio.sleep(sleep_seconds)
    return items


async def store_kb_entries(
    vulns: List[Dict[str, Any]],
    *,
    dry_run: bool,
    embed_new_entries: bool = True,
    translate_new_entries: bool = True,
    include_inserted_rows: bool = False,
) -> Dict[str, Any]:
    to_insert: List[Dict[str, Any]] = []
    for item in vulns:
        cve = item.get("cve", {})
        cve_id = cve.get("id")
        if not cve_id:
            continue
        descriptions = cve.get("descriptions", []) or []
        raw_en_text = _pick_en_description(descriptions)
        to_insert.append(
            {
                "source": "nvd",
                "source_id": cve_id,
                "cve_id": cve_id,
                "raw_en_text": raw_en_text,
                "tags": ["nvd", cve_id.lower()],
            }
        )

    if not to_insert:
        return {"inserted_count": 0, "inserted_rows": []}

    cve_ids = [row["cve_id"] for row in to_insert]
    async with AsyncSessionLocal() as session:
        existing_rows = await session.execute(
            text(
                "SELECT cve_id, raw_en_text FROM kb_entries "
                "WHERE source = :source AND cve_id = ANY(:cve_ids)"
            ),
            {"source": "nvd", "cve_ids": cve_ids},
        )
        existing_map: Dict[str, set] = {}
        for cve_id, raw_en_text in existing_rows:
            existing_map.setdefault(cve_id, set()).add(raw_en_text)

        new_rows = []
        for row in to_insert:
            existing_texts = existing_map.get(row["cve_id"])
            if not existing_texts:
                new_rows.append(row)
                continue
            if row["raw_en_text"] not in existing_texts:
                new_rows.append(row)

        if dry_run or not new_rows:
            return {
                "inserted_count": len(new_rows),
                "inserted_rows": new_rows if include_inserted_rows else [],
            }

        await session.execute(
            text(
                "INSERT INTO kb_entries (source, source_id, cve_id, raw_en_text, tags) "
                "VALUES (:source, :source_id, :cve_id, :raw_en_text, :tags)"
            ),
            new_rows,
        )
        await session.commit()

        inserted_rows: List[Dict[str, Any]] = []
        if include_inserted_rows or embed_new_entries or translate_new_entries:
            inserted_key_map = {
                (row["cve_id"], row.get("raw_en_text")): row
                for row in new_rows
            }
            inserted_result = await session.execute(
                text(
                    "SELECT id, source, cve_id, raw_en_text "
                    "FROM kb_entries "
                    "WHERE source = :source AND cve_id = ANY(:cve_ids)"
                ),
                {"source": "nvd", "cve_ids": list({row["cve_id"] for row in new_rows})},
            )
            for row in inserted_result.mappings().all():
                row_dict = dict(row)
                key = (row_dict.get("cve_id"), row_dict.get("raw_en_text"))
                if key in inserted_key_map:
                    inserted_rows.append(
                        {
                            "id": row_dict.get("id"),
                            "source": row_dict.get("source"),
                            "cve_id": row_dict.get("cve_id"),
                            "raw_en_text": row_dict.get("raw_en_text"),
                        }
                    )

        # Translation hook — translate ru_title, ru_summary, ru_explainer for new entries
        if translate_new_entries:
            try:
                from app.services.ai_generator.translation_service import TranslationService, TranslationError, FullTranslationResult

                svc = TranslationService()
                try:
                    translation_count = 0
                    translation_completed = 0
                    translation_failed = 0

                    for row in inserted_rows:
                        translation_count += 1
                        try:
                            result: FullTranslationResult = await svc.translate_full_cve(
                                row["cve_id"],
                                row["raw_en_text"] or "",
                            )
                            if result.ru_title or result.ru_summary or result.ru_explainer:
                                await session.execute(
                                    text(
                                        "UPDATE kb_entries SET "
                                        "ru_title = :ru_title, "
                                        "ru_summary = :ru_summary, "
                                        "ru_explainer = :ru_explainer "
                                        "WHERE id = :entry_id"
                                    ),
                                    {
                                        "ru_title": result.ru_title or None,
                                        "ru_summary": result.ru_summary or None,
                                        "ru_explainer": result.ru_explainer or None,
                                        "entry_id": row["id"],
                                    },
                                )
                                translation_completed += 1
                            else:
                                translation_failed += 1
                        except Exception as exc:
                            logger.warning("Translation failed for entry %s: %s", row["id"], exc)
                            translation_failed += 1

                    # Update sync log with translation stats
                    await session.execute(
                        text(
                            "UPDATE nvd_sync_log SET "
                            "translation_total = :total, "
                            "translation_completed = :completed, "
                            "translation_failed = :failed "
                            "WHERE id = (SELECT MAX(id) FROM nvd_sync_log)"
                        ),
                        {
                            "total": translation_count,
                            "completed": translation_completed,
                            "failed": translation_failed,
                        },
                    )
                    await session.commit()
                    logger.info(
                        "NVD translation: %d total, %d completed, %d failed",
                        translation_count, translation_completed, translation_failed,
                    )
                finally:
                    await svc.close()

            except Exception as exc:
                logger.warning("NVD translation hook failed: %s", exc)

        # Embeddings are optional here. The admin-triggered sync should not block
        # on external embedding calls because the UI request has a hard timeout.
        if embed_new_entries:
            try:
                from app.services.ai_generator.embedding_service import EmbeddingService, EmbeddingError

                svc = EmbeddingService()
                try:
                    for row in inserted_rows:
                        embed_text = _build_embedding_text(row)
                        if not embed_text:
                            continue
                        try:
                            vector = await svc.embed_document(embed_text)
                            await session.execute(
                                text(
                                    "UPDATE kb_entries SET embedding = CAST(:vec AS vector) "
                                    "WHERE id = :entry_id AND embedding IS NULL"
                                ),
                                {"vec": str(vector), "entry_id": row["id"]},
                            )
                        except EmbeddingError:
                            pass
                    await session.commit()
                finally:
                    await svc.close()
            except Exception as exc:
                logger.warning("NVD embedding hook failed: %s", exc)

        return {
            "inserted_count": len(new_rows),
            "inserted_rows": inserted_rows if include_inserted_rows else [],
        }


async def run_sync(
    *,
    hours: int = DEFAULT_HOURS,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    api_key: Optional[str] = None,
    results_per_page: Optional[int] = None,
    sleep_seconds: int = DEFAULT_SLEEP_SECONDS,
    embed_new_entries: bool = True,
    include_inserted_rows: bool = False,
) -> Dict[str, Any]:
    if start and end:
        window_start = start
        window_end = end
    else:
        window_end = _utc_now()
        window_start = window_end - timedelta(hours=hours)

    api_key_value = api_key or os.getenv("NVD_API_KEY")

    vulns = await fetch_recent_cves(
        start=window_start,
        end=window_end,
        api_key=api_key_value,
        results_per_page=results_per_page,
        sleep_seconds=sleep_seconds,
    )
    store_result = await store_kb_entries(
        vulns,
        dry_run=False,
        embed_new_entries=embed_new_entries,
        include_inserted_rows=include_inserted_rows,
    )

    return {
        "window_start": window_start,
        "window_end": window_end,
        "fetched": len(vulns),
        "inserted": store_result["inserted_count"],
        "inserted_rows": store_result.get("inserted_rows", []),
    }


async def cleanup_stale_sync_logs() -> None:
    """
    Сбрасывает записи nvd_sync_log, зависшие в статусе 'fetching' или 'embedding'
    после перезапуска сервера. Вызывается при старте приложения.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                UPDATE nvd_sync_log
                SET status = 'failed',
                    error = 'Прервано: сервер был перезапущен во время синхронизации'
                WHERE status IN ('fetching', 'embedding', 'translating')
                RETURNING id
                """
            )
        )
        stale = result.fetchall()
        await session.commit()
    if stale:
        logger.warning(
            "Cleaned up %d stale NVD sync log(s) after restart: ids=%s",
            len(stale),
            [r[0] for r in stale],
        )


async def get_latest_sync_log(
    session: AsyncSession,
    *,
    active_only: bool = False,
) -> Optional[Dict[str, Any]]:
    sql = f"SELECT {SYNC_LOG_COLUMNS} FROM nvd_sync_log"
    if active_only:
        sql += " WHERE status IN ('fetching', 'embedding')"
    sql += " ORDER BY fetched_at DESC NULLS LAST LIMIT 1"

    result = await session.execute(text(sql))
    row = result.mappings().first()
    return dict(row) if row else None


async def create_sync_log(session: AsyncSession) -> Dict[str, Any]:
    row = (
        await session.execute(
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
                VALUES (now(), 0, 0, 0, 0, 0, 0, 0, 0, 'fetching', NULL)
                RETURNING id, fetched_at
                """
            )
        )
    ).mappings().one()
    await session.commit()
    return {
        "id": row["id"],
        "fetched_at": row["fetched_at"],
        "window_start": None,
        "window_end": None,
        "fetched_count": 0,
        "inserted_count": 0,
        "embedding_total": 0,
        "embedding_completed": 0,
        "embedding_failed": 0,
        "translation_total": 0,
        "translation_completed": 0,
        "translation_failed": 0,
        "status": "fetching",
        "error": None,
    }


async def _mark_sync_failed(log_id: int, error_text: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                """
                UPDATE nvd_sync_log
                SET status = 'failed',
                    error = :error
                WHERE id = :log_id
                """
            ),
            {"log_id": log_id, "error": error_text[:500]},
        )
        await session.commit()


async def _embed_entries_for_log(log_id: int, entries: List[Dict[str, Any]]) -> Dict[str, int]:
    from app.services.ai_generator.embedding_service import EmbeddingService, EmbeddingError

    done = 0
    failed = 0
    svc = EmbeddingService()
    try:
        async with AsyncSessionLocal() as session:
            for entry in entries:
                try:
                    embed_text = _build_embedding_text(entry)
                    if not embed_text:
                        raise EmbeddingError("Empty text for NVD embedding")

                    vector = await svc.embed_document(embed_text)
                    await session.execute(
                        text(
                            "UPDATE kb_entries SET embedding = CAST(:vec AS vector) "
                            "WHERE id = :entry_id AND embedding IS NULL"
                        ),
                        {"vec": str(vector), "entry_id": entry["id"]},
                    )
                    done += 1
                except EmbeddingError as exc:
                    failed += 1
                    logger.warning(
                        "NVD embedding failed log_id=%s entry_id=%s cve_id=%s: %s",
                        log_id,
                        entry.get("id"),
                        entry.get("cve_id"),
                        exc,
                    )
                except Exception as exc:  # noqa: BLE001 - background progress should continue
                    failed += 1
                    logger.warning(
                        "Unexpected NVD embedding failure log_id=%s entry_id=%s cve_id=%s: %s",
                        log_id,
                        entry.get("id"),
                        entry.get("cve_id"),
                        exc,
                    )

                await session.execute(
                    text(
                        """
                        UPDATE nvd_sync_log
                        SET embedding_completed = :completed,
                            embedding_failed = :failed
                        WHERE id = :log_id
                        """
                    ),
                    {"log_id": log_id, "completed": done, "failed": failed},
                )
                await session.commit()
    finally:
        await svc.close()

    return {"completed": done, "failed": failed}


async def run_sync_background(log_id: int, *, hours: int = DEFAULT_HOURS) -> None:
    try:
        result = await run_sync(
            hours=hours,
            embed_new_entries=False,
            include_inserted_rows=True,
        )
        inserted_rows = result.get("inserted_rows", []) or []
        inserted_count = len(inserted_rows)

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    UPDATE nvd_sync_log
                    SET window_start = :window_start,
                        window_end = :window_end,
                        fetched_count = :fetched_count,
                        inserted_count = :inserted_count,
                        embedding_total = :embedding_total,
                        embedding_completed = 0,
                        embedding_failed = 0,
                        status = :status,
                        error = NULL
                    WHERE id = :log_id
                    """
                ),
                {
                    "log_id": log_id,
                    "window_start": result.get("window_start"),
                    "window_end": result.get("window_end"),
                    "fetched_count": result.get("fetched"),
                    "inserted_count": inserted_count,
                    "embedding_total": inserted_count,
                    "status": "embedding" if inserted_count > 0 else "success",
                },
            )
            await session.commit()

        if inserted_count == 0:
            return

        embedding_result = await _embed_entries_for_log(log_id, inserted_rows)
        if embedding_result["completed"] == 0 and embedding_result["failed"] > 0:
            raise RuntimeError("Failed to compute embeddings for all fetched NVD entries")

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    UPDATE nvd_sync_log
                    SET status = 'success',
                        embedding_completed = :completed,
                        embedding_failed = :failed
                    WHERE id = :log_id
                    """
                ),
                {
                    "log_id": log_id,
                    "completed": embedding_result["completed"],
                    "failed": embedding_result["failed"],
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001 - background task errors must be logged
        logger.exception("NVD background sync failed log_id=%s", log_id)
        await _mark_sync_failed(log_id, str(exc))


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch NVD CVEs modified in the last N hours and store them in kb_entries."
    )
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--end", type=str, default=None)
    parser.add_argument("--results-per-page", type=int, default=None)
    parser.add_argument("--sleep", type=int, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--api-key", type=str, default=None)
    args = parser.parse_args()

    if args.start and args.end:
        start = _parse_dt(args.start)
        end = _parse_dt(args.end)
    else:
        end = _utc_now()
        start = end - timedelta(hours=args.hours)

    api_key = args.api_key or os.getenv("NVD_API_KEY")

    logging.info(
        "Fetching CVEs last modified between %s and %s (UTC)",
        _format_dt(start),
        _format_dt(end),
    )
    vulns = await fetch_recent_cves(
        start=start,
        end=end,
        api_key=api_key,
        results_per_page=args.results_per_page,
        sleep_seconds=args.sleep,
    )
    logging.info("Fetched %d CVE records", len(vulns))

    store_result = await store_kb_entries(vulns, dry_run=args.dry_run)
    inserted = store_result["inserted_count"]
    if args.dry_run:
        logging.info("Dry run: %d new CVE records would be inserted", inserted)
    else:
        logging.info("Inserted %d new CVE records into kb_entries", inserted)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(asyncio.run(main()))
