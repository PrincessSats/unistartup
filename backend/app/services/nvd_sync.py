import argparse
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import httpx
from sqlalchemy import text

from app.database import AsyncSessionLocal


NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
DEFAULT_SLEEP_SECONDS = 6
DEFAULT_HOURS = 24


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


async def store_kb_entries(vulns: List[Dict[str, Any]], *, dry_run: bool) -> int:
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
        return 0

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
            return len(new_rows)

        await session.execute(
            text(
                "INSERT INTO kb_entries (source, source_id, cve_id, raw_en_text, tags) "
                "VALUES (:source, :source_id, :cve_id, :raw_en_text, :tags)"
            ),
            new_rows,
        )
        await session.commit()
        return len(new_rows)


async def run_sync(
    *,
    hours: int = DEFAULT_HOURS,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    api_key: Optional[str] = None,
    results_per_page: Optional[int] = None,
    sleep_seconds: int = DEFAULT_SLEEP_SECONDS,
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
    inserted = await store_kb_entries(vulns, dry_run=False)

    return {
        "window_start": window_start,
        "window_end": window_end,
        "fetched": len(vulns),
        "inserted": inserted,
    }


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

    inserted = await store_kb_entries(vulns, dry_run=args.dry_run)
    if args.dry_run:
        logging.info("Dry run: %d new CVE records would be inserted", inserted)
    else:
        logging.info("Inserted %d new CVE records into kb_entries", inserted)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(asyncio.run(main()))
