import argparse
import asyncio
import json
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
BATCH_SIZE = 20
CONCURRENCY_LIMIT = 3  # Reduced to avoid hitting 429 ResourceExhausted (quota is 10)

logger = logging.getLogger(__name__)
SYNC_LOG_COLUMNS = (
    "id, fetched_at, window_start, window_end, fetched_count, inserted_count, "
    "embedding_total, embedding_completed, embedding_failed, "
    "translation_total, translation_completed, translation_failed, "
    "status, error, total_to_fetch, detailed_status, event_log"
)


def _chunked(iterable: Iterable[Any], n: int) -> Iterable[List[Any]]:
    """Yield successive n-sized chunks from iterable."""
    it = iter(iterable)
    while True:
        chunk = []
        try:
            for _ in range(n):
                chunk.append(next(it))
        except StopIteration:
            pass
        if not chunk:
            return
        yield chunk


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
        "total_to_fetch": row.get("total_to_fetch") or 0,
        "detailed_status": row.get("detailed_status"),
        "status": row.get("status"),
        "error": row.get("error"),
        "event_log": json.loads(row["event_log"]) if isinstance(row.get("event_log"), str) else row.get("event_log"),
    }


def _build_embedding_text(row: Dict[str, Any]) -> str:
    parts = [
        row.get("cve_id") or "",
        row.get("raw_en_text") or "",
        " ".join(row.get("cwe_ids") or []),
        row.get("attack_vector") or "",
    ]
    return " ".join(filter(None, parts)).strip()


def _extract_cwe_ids(cve: Dict[str, Any]) -> List[str]:
    """Extract CWE IDs from NVD CVE record, e.g. ['CWE-79', 'CWE-80']."""
    cwe_ids: List[str] = []
    for weakness in cve.get("weaknesses") or []:
        for desc in weakness.get("description") or []:
            value = desc.get("value") or ""
            # Skip NVD catch-all placeholders
            if value.startswith("CWE-") and value not in ("CWE-noinfo", "CWE-other"):
                if value not in cwe_ids:
                    cwe_ids.append(value)
    return cwe_ids


def _extract_cvss_data(cve: Dict[str, Any]) -> Dict[str, Any]:
    """Extract CVSS base score, vector string, attack vector and complexity.

    Tries CVSSv3.1, then v3.0, then v2.0.
    """
    metrics = cve.get("metrics") or {}
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key) or []
        for entry in entries:
            data = entry.get("cvssData") or {}
            score = data.get("baseScore")
            if score is not None:
                return {
                    "cvss_base_score": float(score),
                    "cvss_vector": data.get("vectorString"),
                    "attack_vector": data.get("attackVector"),
                    "attack_complexity": data.get("attackComplexity"),
                }
    return {}


def _extract_affected_products(cve: Dict[str, Any]) -> List[str]:
    """Extract vendor:product pairs from CPE match strings (capped at 10)."""
    products: List[str] = []
    seen: set = set()
    for config in cve.get("configurations") or []:
        for node in config.get("nodes") or []:
            for match in node.get("cpeMatch") or []:
                criteria = match.get("criteria") or ""
                # CPE 2.3 format: cpe:2.3:a:vendor:product:version:...
                parts = criteria.split(":")
                if len(parts) >= 5:
                    vendor, product = parts[3], parts[4]
                    if vendor and product and vendor != "*" and product != "*":
                        pair = f"{vendor}:{product}"
                        if pair not in seen:
                            seen.add(pair)
                            products.append(pair)
                            if len(products) >= 10:
                                return products
    return products


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
    log_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    start_index = 0
    
    # Use shorter delay if API key is provided (NVD allows more requests)
    actual_sleep = sleep_seconds
    if api_key and actual_sleep == DEFAULT_SLEEP_SECONDS:
        actual_sleep = 1

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

            if log_id:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        text(
                            "UPDATE nvd_sync_log SET "
                            "fetched_count = :fetched, "
                            "total_to_fetch = :total, "
                            "detailed_status = :status "
                            "WHERE id = :log_id"
                        ),
                        {
                            "fetched": len(items),
                            "total": total,
                            "status": f"Fetching CVEs: {len(items)}/{total}...",
                            "log_id": log_id,
                        },
                    )
                    await session.commit()

            if not vulns or next_index >= total:
                break

            start_index = next_index
            if actual_sleep > 0:
                await asyncio.sleep(actual_sleep)
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

        cwe_ids = _extract_cwe_ids(cve)
        cvss_data = _extract_cvss_data(cve)
        affected_products = _extract_affected_products(cve)

        # Tags include CWE IDs for GIN-indexed filtering
        tags = ["nvd", cve_id.lower()] + [c.lower() for c in cwe_ids]

        to_insert.append(
            {
                "source": "nvd",
                "source_id": cve_id,
                "cve_id": cve_id,
                "raw_en_text": raw_en_text,
                "tags": tags,
                "cwe_ids": cwe_ids,
                "cvss_base_score": cvss_data.get("cvss_base_score"),
                "cvss_vector": cvss_data.get("cvss_vector"),
                "attack_vector": cvss_data.get("attack_vector"),
                "attack_complexity": cvss_data.get("attack_complexity"),
                "affected_products": affected_products,
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
                "INSERT INTO kb_entries "
                "(source, source_id, cve_id, raw_en_text, tags, "
                "cwe_ids, cvss_base_score, cvss_vector, attack_vector, attack_complexity, affected_products) "
                "VALUES "
                "(:source, :source_id, :cve_id, :raw_en_text, :tags, "
                ":cwe_ids, :cvss_base_score, :cvss_vector, :attack_vector, :attack_complexity, :affected_products)"
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
                    "SELECT id, source, cve_id, raw_en_text, cwe_ids, attack_vector "
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
                            "cwe_ids": row_dict.get("cwe_ids") or [],
                            "attack_vector": row_dict.get("attack_vector"),
                        }
                    )

        # Translation hook — translate ru_title, ru_summary, ru_explainer for new entries
        if translate_new_entries:
            try:
                from app.services.ai_generator.translation_service import TranslationService, FullTranslationResult

                svc = TranslationService()
                try:
                    translation_count = len(inserted_rows)
                    translation_completed = 0
                    translation_failed = 0
                    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)

                    async def translate_task(row: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[FullTranslationResult]]:
                        max_attempts = 3
                        base_backoff = 5.0
                        for attempt in range(max_attempts):
                            async with sem:
                                try:
                                    result = await svc.translate_full_cve(
                                        row["cve_id"],
                                        row["raw_en_text"] or "",
                                    )
                                    return row, result
                                except Exception as exc:
                                    # If 429, retry with backoff
                                    if "429" in str(exc) and attempt < max_attempts - 1:
                                        backoff = base_backoff * (2 ** attempt)
                                        logger.warning("Translation rate limited for %s (429), retrying in %.1fs... (attempt %d/%d)", 
                                                       row["cve_id"], backoff, attempt + 1, max_attempts)
                                        await asyncio.sleep(backoff)
                                        continue
                                    
                                    logger.warning("Translation failed for entry %s: %s", row["id"], exc)
                                    return row, None
                        return row, None

                    # Process in batches
                    for chunk in _chunked(inserted_rows, BATCH_SIZE):
                        tasks = [translate_task(row) for row in chunk]
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        updates = []
                        for res in results:
                            if isinstance(res, Exception):
                                translation_failed += 1
                                continue
                            
                            row, translation = res
                            if translation and (translation.ru_title or translation.ru_summary or translation.ru_explainer):
                                updates.append({
                                    "ru_title": translation.ru_title or None,
                                    "ru_summary": translation.ru_summary or None,
                                    "ru_explainer": translation.ru_explainer or None,
                                    "entry_id": row["id"],
                                })
                                translation_completed += 1
                            else:
                                translation_failed += 1

                        if updates:
                            await session.execute(
                                text(
                                    "UPDATE kb_entries SET "
                                    "ru_title = :ru_title, "
                                    "ru_summary = :ru_summary, "
                                    "ru_explainer = :ru_explainer "
                                    "WHERE id = :entry_id"
                                ),
                                updates,
                            )

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
                            "NVD translation progress: %d completed, %d failed (total %d)",
                            translation_completed, translation_failed, translation_count,
                        )
                        # Avoid burst limit
                        await asyncio.sleep(2.0)

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
                    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)

                    async def embed_task(row: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[list[float]]]:
                        max_attempts = 2
                        for attempt in range(max_attempts):
                            async with sem:
                                try:
                                    embed_text = _build_embedding_text(row)
                                    if not embed_text:
                                        return row, None
                                    vector = await svc.embed_document(embed_text)
                                    return row, vector
                                except EmbeddingError as exc:
                                    if "429" in str(exc) and attempt < max_attempts - 1:
                                        await asyncio.sleep(2.0 * (attempt + 1))
                                        continue
                                    return row, None
                                except Exception:
                                    return row, None
                        return row, None

                    for chunk in _chunked(inserted_rows, BATCH_SIZE):
                        tasks = [embed_task(row) for row in chunk]
                        results = await asyncio.gather(*tasks, return_exceptions=True)

                        updates = []
                        for res in results:
                            if isinstance(res, Exception) or not res:
                                continue

                            row, vector = res
                            if vector:
                                updates.append({
                                    "vec": str(vector),
                                    "entry_id": row["id"]
                                })

                        if updates:
                            await session.execute(
                                text(
                                    "UPDATE kb_entries SET embedding = CAST(:vec AS vector) "
                                    "WHERE id = :entry_id AND embedding IS NULL"
                                ),
                                updates,
                            )
                            await session.commit()
                        await asyncio.sleep(1.0)

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
    translate_new_entries: bool = True,
    include_inserted_rows: bool = False,
    log_id: Optional[int] = None,
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
        log_id=log_id,
    )
    store_result = await store_kb_entries(
        vulns,
        dry_run=False,
        embed_new_entries=embed_new_entries,
        translate_new_entries=translate_new_entries,
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
    Сбрасывает записи nvd_sync_log, зависшие в статусе 'fetching', 'embedding' или 'translating'
    после перезапуска сервера. Вызывается при старте приложения.

    Если синхронизация успела завершить фазу fetch/store (inserted_count > 0),
    помечает её как 'partial_success' вместо 'failed', чтобы пользователь видел,
    что данные были сохранены.
    """
    async with AsyncSessionLocal() as session:
        # First, check for syncs that completed fetch/store but failed during translation/embedding
        partial_result = await session.execute(
            text(
                """
                UPDATE nvd_sync_log
                SET status = 'partial_success',
                    error = NULL,
                    detailed_status = COALESCE(detailed_status, 'Синхронизация прервана после сохранения CVE. Данные сохранены.')
                WHERE status IN ('fetching', 'embedding', 'translating')
                  AND COALESCE(inserted_count, 0) > 0
                RETURNING id, inserted_count
                """
            )
        )
        partial = partial_result.fetchall()

        # Then, mark truly failed syncs (no data was saved)
        failed_result = await session.execute(
            text(
                """
                UPDATE nvd_sync_log
                SET status = 'failed',
                    error = 'Прервано: сервер был перезапущен во время синхронизации. Данные не были сохранены.'
                WHERE status IN ('fetching', 'embedding', 'translating')
                  AND COALESCE(inserted_count, 0) = 0
                RETURNING id
                """
            )
        )
        failed = failed_result.fetchall()

        await session.commit()

    if partial:
        logger.warning(
            "Marked %d NVD sync log(s) as 'partial_success' after restart: ids=%s (inserted: %s)",
            len(partial),
            [r[0] for r in partial],
            [r[1] for r in partial],
        )
    if failed:
        logger.warning(
            "Marked %d NVD sync log(s) as 'failed' after restart: ids=%s",
            len(failed),
            [r[0] for r in failed],
        )


async def get_latest_sync_log(
    session: AsyncSession,
    *,
    active_only: bool = False,
) -> Optional[Dict[str, Any]]:
    sql = f"SELECT {SYNC_LOG_COLUMNS} FROM nvd_sync_log"
    if active_only:
        sql += " WHERE status IN ('fetching', 'embedding', 'translating')"
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
                    total_to_fetch,
                    detailed_status,
                    error
                )
                VALUES (now(), 0, 0, 0, 0, 0, 0, 0, 0, 'fetching', 0, 'Starting sync...', NULL)
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
        "total_to_fetch": 0,
        "detailed_status": "Starting sync...",
        "status": "fetching",
        "error": None,
    }


async def _is_cancelled(log_id: int) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT status FROM nvd_sync_log WHERE id = :log_id"),
            {"log_id": log_id},
        )
        val = result.scalar_one_or_none()
        return val == "cancelled"


async def stop_active_sync_log(session: AsyncSession) -> Optional[Dict[str, Any]]:
    await session.execute(
        text(
            """
            UPDATE nvd_sync_log
            SET status = 'cancelled',
                detailed_status = 'Stopped by user.'
            WHERE status IN ('fetching', 'embedding', 'translating')
            """
        )
    )
    await session.commit()
    return await get_latest_sync_log(session)


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


async def _translate_entries_for_log(log_id: int, entries: List[Dict[str, Any]]) -> Dict[str, int]:
    """Generate structured Russian KB articles for backlog entries using article_prompt.txt.

    Uses generate_article_payload (1 LLM call per CVE) which produces a properly structured
    ru_title / ru_summary / ru_explainer via the article prompt, instead of plain translation
    (which required 3 separate LLM calls and produced literal translations with no structure).
    """
    from app.services.article_generation import generate_article_payload, ArticleGenerationError

    done = 0
    failed = 0
    total = len(entries)
    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def generate_task(row: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[dict]]:
        raw_en_text = row.get("raw_en_text") or ""
        max_attempts = 3
        base_backoff = 5.0
        for attempt in range(max_attempts):
            async with sem:
                try:
                    result = await generate_article_payload(raw_en_text)
                    return row, result.get("parsed")
                except Exception as exc:
                    if "429" in str(exc) and attempt < max_attempts - 1:
                        backoff = base_backoff * (2 ** attempt)
                        logger.warning(
                            "Article generation rate limited for %s (429), retrying in %.1fs... (attempt %d/%d)",
                            row["cve_id"], backoff, attempt + 1, max_attempts,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    if attempt == max_attempts - 1:
                        logger.warning(
                            "Article generation exhausted retries for entry %s (cve_id=%s) after %d attempts"
                            " (type=%s): %s",
                            row["id"], row.get("cve_id"), max_attempts, type(exc).__name__, exc,
                        )
                    else:
                        logger.warning(
                            "Article generation failed for entry %s (cve_id=%s, type=%s, attempt=%d/%d): %s",
                            row["id"], row.get("cve_id"), type(exc).__name__, attempt + 1, max_attempts, exc,
                        )
                    return row, None
        return row, None

    async with AsyncSessionLocal() as session:
        for chunk in _chunked(entries, BATCH_SIZE):
            if await _is_cancelled(log_id):
                logger.info("NVD translate cancelled at chunk boundary log_id=%s done=%d", log_id, done)
                break
            tasks = [generate_task(row) for row in chunk]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            updates = []
            chunk_done = 0
            chunk_failed = 0

            for res in results:
                if isinstance(res, Exception):
                    logger.error(
                        "Unexpected exception in generate_task (type=%s): %s",
                        type(res).__name__, res,
                    )
                    chunk_failed += 1
                    continue

                row, parsed = res
                if parsed and (parsed.get("ru_title") or parsed.get("ru_summary") or parsed.get("ru_explainer")):
                    updates.append({
                        "ru_title": parsed.get("ru_title") or None,
                        "ru_summary": parsed.get("ru_summary") or None,
                        "ru_explainer": parsed.get("ru_explainer") or None,
                        "entry_id": row["id"],
                    })
                    chunk_done += 1
                else:
                    logger.warning(
                        "Entry %s (cve_id=%s) produced no usable fields: parsed=%r",
                        row["id"], row.get("cve_id"), parsed,
                    )
                    chunk_failed += 1

            if updates:
                await session.execute(
                    text(
                        "UPDATE kb_entries SET "
                        "ru_title = :ru_title, "
                        "ru_summary = :ru_summary, "
                        "ru_explainer = :ru_explainer "
                        "WHERE id = :entry_id"
                    ),
                    updates,
                )

            done += chunk_done
            failed += chunk_failed

            await session.execute(
                text(
                    """
                    UPDATE nvd_sync_log
                    SET translation_completed = :completed,
                        translation_failed = :failed,
                        detailed_status = :status
                    WHERE id = :log_id
                    """
                ),
                {
                    "log_id": log_id,
                    "completed": done,
                    "failed": failed,
                    "status": f"Generating KB articles: {done + failed}/{total}...",
                },
            )
            await session.commit()
            await asyncio.sleep(2.0)

    return {"completed": done, "failed": failed}


async def _embed_entries_for_log(log_id: int, entries: List[Dict[str, Any]]) -> Dict[str, int]:
    from app.services.ai_generator.embedding_service import EmbeddingService, EmbeddingError

    done = 0
    failed = 0
    total = len(entries)
    svc = EmbeddingService()
    try:
        sem = asyncio.Semaphore(CONCURRENCY_LIMIT)

        async def embed_task(row: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[list[float]]]:
            max_attempts = 2
            for attempt in range(max_attempts):
                async with sem:
                    try:
                        embed_text = _build_embedding_text(row)
                        if not embed_text:
                            # Empty text is considered a "failure" to embed, or just skip?
                            # Original code raised EmbeddingError for empty text.
                            raise EmbeddingError("Empty text for NVD embedding")

                        vector = await svc.embed_document(embed_text)
                        return row, vector
                    except EmbeddingError as exc:
                        if "429" in str(exc) and attempt < max_attempts - 1:
                            await asyncio.sleep(2.0 * (attempt + 1))
                            continue
                        logger.warning(
                            "NVD embedding failed log_id=%s entry_id=%s cve_id=%s: %s",
                            log_id,
                            row.get("id"),
                            row.get("cve_id"),
                            exc,
                        )
                        return row, None
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Unexpected NVD embedding failure log_id=%s entry_id=%s cve_id=%s: %s",
                            log_id,
                            row.get("id"),
                            row.get("cve_id"),
                            exc,
                        )
                        return row, None
            return row, None

        async with AsyncSessionLocal() as session:
            for chunk in _chunked(entries, BATCH_SIZE):
                if await _is_cancelled(log_id):
                    logger.info("NVD embed cancelled at chunk boundary log_id=%s done=%d", log_id, done)
                    break
                tasks = [embed_task(row) for row in chunk]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                updates = []
                chunk_done = 0
                chunk_failed = 0

                for res in results:
                    if isinstance(res, Exception):
                        chunk_failed += 1
                        continue

                    # unpack tuple
                    if not res:
                        chunk_failed += 1
                        continue
                    
                    row, vector = res
                    if vector:
                        updates.append({
                            "vec": str(vector),
                            "entry_id": row["id"]
                        })
                        chunk_done += 1
                    else:
                        chunk_failed += 1

                if updates:
                    await session.execute(
                        text(
                            "UPDATE kb_entries SET embedding = CAST(:vec AS vector) "
                            "WHERE id = :entry_id AND embedding IS NULL"
                        ),
                        updates,
                    )

                done += chunk_done
                failed += chunk_failed

                await session.execute(
                    text(
                        """
                        UPDATE nvd_sync_log
                        SET embedding_completed = :completed,
                            embedding_failed = :failed,
                            detailed_status = :status
                        WHERE id = :log_id
                        """
                    ),
                    {
                        "log_id": log_id, 
                        "completed": done, 
                        "failed": failed,
                        "status": f"Computing embeddings: {done + failed}/{total}...",
                    },
                )
                await session.commit()
                await asyncio.sleep(1.0)
    finally:
        await svc.close()

    return {"completed": done, "failed": failed}


async def run_sync_background(log_id: int, *, hours: int = DEFAULT_HOURS) -> None:
    event_log: List[Dict[str, str]] = []

    def add_event(stage: str, message: str) -> None:
        """Add event to log with timestamp."""
        event_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "message": message,
        })

    try:
        add_event("INIT", "Starting NVD sync...")

        # Step 1: Fetch and Store (without automatic translation/embedding)
        add_event("FETCHING", "Connecting to NVD API")
        result = await run_sync(
            hours=hours,
            embed_new_entries=False,
            translate_new_entries=False,
            include_inserted_rows=True,
            log_id=log_id,
        )
        inserted_rows = result.get("inserted_rows", []) or []
        inserted_count = len(inserted_rows)
        fetched_count = result.get("fetched", 0)

        add_event("FETCHING", f"Completed: {fetched_count} CVEs fetched")
        add_event("FETCHING", f"Storing {inserted_count} new entries to database")

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    UPDATE nvd_sync_log
                    SET window_start = :window_start,
                        window_end = :window_end,
                        fetched_count = :fetched_count,
                        inserted_count = :inserted_count,
                        translation_total = :translation_total,
                        embedding_total = :embedding_total,
                        status = :status,
                        detailed_status = :detailed_status,
                        error = NULL,
                        event_log = :event_log
                    WHERE id = :log_id
                    """
                ),
                {
                    "log_id": log_id,
                    "window_start": result.get("window_start"),
                    "window_end": result.get("window_end"),
                    "fetched_count": result.get("fetched"),
                    "inserted_count": inserted_count,
                    "translation_total": inserted_count,
                    "embedding_total": inserted_count,
                    "status": "translating" if inserted_count > 0 else "success",
                    "detailed_status": f"Stored {inserted_count} new entries. Starting translation..." if inserted_count > 0 else "Finished. No new entries found.",
                    "event_log": json.dumps(event_log),
                },
            )
            await session.commit()

        if inserted_count == 0:
            add_event("SUCCESS", "No new entries found")
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("UPDATE nvd_sync_log SET event_log = :event_log WHERE id = :log_id"),
                    {"log_id": log_id, "event_log": json.dumps(event_log)},
                )
                await session.commit()
            return

        # Step 2: Translation
        add_event("TRANSLATING", f"Starting article generation for {inserted_count} entries...")
        await _translate_entries_for_log(log_id, inserted_rows)
        add_event("TRANSLATING", f"Completed: Articles generated for {inserted_count} entries")

        # Update status before embedding
        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    "UPDATE nvd_sync_log SET status = 'embedding', detailed_status = 'Starting embeddings...', event_log = :event_log WHERE id = :log_id"
                ),
                {"log_id": log_id, "event_log": json.dumps(event_log)},
            )
            await session.commit()

        # Step 3: Embedding
        add_event("EMBEDDING", f"Starting embeddings for {inserted_count} entries...")
        embedding_result = await _embed_entries_for_log(log_id, inserted_rows)
        # We don't fail the whole sync if some embeddings fail, but we log it
        add_event("EMBEDDING", f"Completed: {embedding_result['completed']} successful, {embedding_result['failed']} failed")

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    UPDATE nvd_sync_log
                    SET status = 'success',
                        detailed_status = :detailed_status,
                        embedding_completed = :completed,
                        embedding_failed = :failed,
                        event_log = :event_log
                    WHERE id = :log_id
                    """
                ),
                {
                    "log_id": log_id,
                    "completed": embedding_result["completed"],
                    "failed": embedding_result["failed"],
                    "detailed_status": f"Sync completed. Processed {inserted_count} entries.",
                    "event_log": json.dumps(event_log),
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001 - background task errors must be logged
        add_event("ERROR", str(exc))
        logger.exception("NVD background sync failed log_id=%s", log_id)
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE nvd_sync_log SET event_log = :event_log WHERE id = :log_id"),
                {"log_id": log_id, "event_log": json.dumps(event_log)},
            )
            await session.commit()
        await _mark_sync_failed(log_id, str(exc))


async def _create_standalone_log(session: AsyncSession, initial_status: str, initial_detailed: str) -> Dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO nvd_sync_log (
                    fetched_at, fetched_count, inserted_count,
                    embedding_total, embedding_completed, embedding_failed,
                    translation_total, translation_completed, translation_failed,
                    status, total_to_fetch, detailed_status, error
                )
                VALUES (now(), NULL, 0, 0, 0, 0, 0, 0, 0, :status, 0, :detailed, NULL)
                RETURNING id, fetched_at
                """
            ),
            {"status": initial_status, "detailed": initial_detailed},
        )
    ).mappings().one()
    await session.commit()
    return {
        "id": row["id"],
        "fetched_at": row["fetched_at"],
        "window_start": None, "window_end": None,
        "fetched_count": None, "inserted_count": 0,
        "embedding_total": 0, "embedding_completed": 0, "embedding_failed": 0,
        "translation_total": 0, "translation_completed": 0, "translation_failed": 0,
        "total_to_fetch": 0,
        "detailed_status": initial_detailed,
        "status": initial_status,
        "error": None,
        "event_log": None,
    }


async def create_translate_log(session: AsyncSession) -> Dict[str, Any]:
    return await _create_standalone_log(session, "translating", "Querying untranslated entries...")


async def create_embed_log(session: AsyncSession) -> Dict[str, Any]:
    return await _create_standalone_log(session, "embedding", "Querying unembedded entries...")


async def run_fetch_only_background(log_id: int, *, hours: int = DEFAULT_HOURS) -> None:
    event_log: List[Dict[str, str]] = []

    def add_event(stage: str, message: str) -> None:
        event_log.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": stage, "message": message})

    try:
        add_event("INIT", "Starting NVD fetch...")
        add_event("FETCHING", "Connecting to NVD API")
        result = await run_sync(
            hours=hours,
            embed_new_entries=False,
            translate_new_entries=False,
            include_inserted_rows=False,
            log_id=log_id,
        )
        fetched_count = result.get("fetched", 0)
        inserted_count = result.get("inserted", 0)
        add_event("FETCHING", f"Completed: {fetched_count} CVEs fetched, {inserted_count} new entries stored")
        add_event("SUCCESS", "Fetch complete")

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    UPDATE nvd_sync_log
                    SET window_start = :window_start, window_end = :window_end,
                        fetched_count = :fetched_count, inserted_count = :inserted_count,
                        status = 'success', detailed_status = :detailed_status,
                        error = NULL, event_log = :event_log
                    WHERE id = :log_id
                    """
                ),
                {
                    "log_id": log_id,
                    "window_start": result.get("window_start"),
                    "window_end": result.get("window_end"),
                    "fetched_count": fetched_count,
                    "inserted_count": inserted_count,
                    "detailed_status": f"Fetched {fetched_count} CVEs, stored {inserted_count} new entries.",
                    "event_log": json.dumps(event_log),
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        add_event("ERROR", str(exc))
        logger.exception("NVD fetch-only sync failed log_id=%s", log_id)
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE nvd_sync_log SET event_log = :event_log WHERE id = :log_id"),
                {"log_id": log_id, "event_log": json.dumps(event_log)},
            )
            await session.commit()
        await _mark_sync_failed(log_id, str(exc))


async def run_translate_standalone_background(log_id: int, *, limit: Optional[int] = None) -> None:
    event_log: List[Dict[str, str]] = []

    def add_event(stage: str, message: str) -> None:
        event_log.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": stage, "message": message})

    try:
        add_event("INIT", "Starting standalone translation...")

        row_limit = limit if limit and limit > 0 else 50000
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(
                text(
                    "SELECT id, cve_id, raw_en_text, cwe_ids, attack_vector "
                    "FROM kb_entries WHERE source = 'nvd' AND ru_summary IS NULL "
                    f"ORDER BY id DESC LIMIT {row_limit}"
                )
            )).mappings().all()
            entries = [dict(r) for r in rows]

        total = len(entries)
        add_event("TRANSLATING", f"Found {total} untranslated entries")

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    "UPDATE nvd_sync_log SET translation_total = :total, "
                    "detailed_status = :status, event_log = :event_log WHERE id = :log_id"
                ),
                {"log_id": log_id, "total": total, "status": f"Translating {total} entries...", "event_log": json.dumps(event_log)},
            )
            await session.commit()

        if total == 0:
            add_event("SUCCESS", "No untranslated entries found")
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text(
                        "UPDATE nvd_sync_log SET status = 'success', "
                        "detailed_status = 'All entries already translated.', event_log = :event_log WHERE id = :log_id"
                    ),
                    {"log_id": log_id, "event_log": json.dumps(event_log)},
                )
                await session.commit()
            return

        res = await _translate_entries_for_log(log_id, entries)

        if await _is_cancelled(log_id):
            add_event("TRANSLATING", f"Stopped by user after {res['completed']} translations")
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("UPDATE nvd_sync_log SET event_log = :event_log WHERE id = :log_id"),
                    {"log_id": log_id, "event_log": json.dumps(event_log)},
                )
                await session.commit()
            return

        add_event("TRANSLATING", f"Completed: {res['completed']} ok, {res['failed']} failed")

        if res["completed"] == 0 and res["failed"] > 0:
            add_event("ERROR", f"All {res['failed']} entries failed to translate")
            logger.error(
                "NVD translate log_id=%s: all %d entries failed (0 completed)",
                log_id, res["failed"],
            )
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("UPDATE nvd_sync_log SET event_log = :event_log WHERE id = :log_id"),
                    {"log_id": log_id, "event_log": json.dumps(event_log)},
                )
                await session.commit()
            await _mark_sync_failed(log_id, f"All {res['failed']} entries failed to translate")
            return

        if res["failed"] > 0:
            logger.warning(
                "NVD translate log_id=%s: partial failure — %d ok, %d failed",
                log_id, res["completed"], res["failed"],
            )

        add_event("SUCCESS", "Translation complete")

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    UPDATE nvd_sync_log SET status = 'success',
                        translation_completed = :completed, translation_failed = :failed,
                        detailed_status = :detailed, event_log = :event_log
                    WHERE id = :log_id
                    """
                ),
                {
                    "log_id": log_id,
                    "completed": res["completed"], "failed": res["failed"],
                    "detailed": f"Translated {res['completed']}/{total} entries.",
                    "event_log": json.dumps(event_log),
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        add_event("ERROR", str(exc))
        logger.exception("NVD standalone translate failed log_id=%s", log_id)
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE nvd_sync_log SET event_log = :event_log WHERE id = :log_id"),
                {"log_id": log_id, "event_log": json.dumps(event_log)},
            )
            await session.commit()
        await _mark_sync_failed(log_id, str(exc))


async def run_embed_standalone_background(log_id: int) -> None:
    event_log: List[Dict[str, str]] = []

    def add_event(stage: str, message: str) -> None:
        event_log.append({"timestamp": datetime.now(timezone.utc).isoformat(), "stage": stage, "message": message})

    try:
        add_event("INIT", "Starting standalone embedding...")

        async with AsyncSessionLocal() as session:
            rows = (await session.execute(
                text(
                    "SELECT id, cve_id, raw_en_text, cwe_ids, attack_vector "
                    "FROM kb_entries WHERE source = 'nvd' AND embedding IS NULL "
                    "ORDER BY id DESC LIMIT 2000"
                )
            )).mappings().all()
            entries = [dict(r) for r in rows]

        total = len(entries)
        add_event("EMBEDDING", f"Found {total} entries without embeddings")

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    "UPDATE nvd_sync_log SET embedding_total = :total, "
                    "detailed_status = :status, event_log = :event_log WHERE id = :log_id"
                ),
                {"log_id": log_id, "total": total, "status": f"Embedding {total} entries...", "event_log": json.dumps(event_log)},
            )
            await session.commit()

        if total == 0:
            add_event("SUCCESS", "No entries need embedding")
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text(
                        "UPDATE nvd_sync_log SET status = 'success', "
                        "detailed_status = 'All entries already have embeddings.', event_log = :event_log WHERE id = :log_id"
                    ),
                    {"log_id": log_id, "event_log": json.dumps(event_log)},
                )
                await session.commit()
            return

        res = await _embed_entries_for_log(log_id, entries)

        if await _is_cancelled(log_id):
            add_event("EMBEDDING", f"Stopped by user after {res['completed']} embeddings")
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("UPDATE nvd_sync_log SET event_log = :event_log WHERE id = :log_id"),
                    {"log_id": log_id, "event_log": json.dumps(event_log)},
                )
                await session.commit()
            return

        add_event("EMBEDDING", f"Completed: {res['completed']} ok, {res['failed']} failed")
        add_event("SUCCESS", "Embedding complete")

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    UPDATE nvd_sync_log SET status = 'success',
                        embedding_completed = :completed, embedding_failed = :failed,
                        detailed_status = :detailed, event_log = :event_log
                    WHERE id = :log_id
                    """
                ),
                {
                    "log_id": log_id,
                    "completed": res["completed"], "failed": res["failed"],
                    "detailed": f"Embedded {res['completed']}/{total} entries.",
                    "event_log": json.dumps(event_log),
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        add_event("ERROR", str(exc))
        logger.exception("NVD standalone embed failed log_id=%s", log_id)
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE nvd_sync_log SET event_log = :event_log WHERE id = :log_id"),
                {"log_id": log_id, "event_log": json.dumps(event_log)},
            )
            await session.commit()
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
