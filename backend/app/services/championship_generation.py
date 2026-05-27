import asyncio
import json
from typing import Any, Literal, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contest import KBEntry
from app.services.task_generation import (
    _build_client,
    _strip_code_fence,
    TASK_MODEL_REGISTRY,
    DEFAULT_TASK_MODEL_KEY,
    TaskGenerationError,
)


class ChampionshipGenerationError(RuntimeError):
    pass


def _format_kb_entries_for_prompt(kb_entries: list[KBEntry]) -> str:
    lines = []
    for i, entry in enumerate(kb_entries, 1):
        lines.append(f"CVE #{i}:")
        if entry.cve_id:
            lines.append(f"  ID: {entry.cve_id}")
        if entry.ru_title:
            lines.append(f"  Title: {entry.ru_title}")
        if entry.ru_summary:
            lines.append(f"  Summary: {entry.ru_summary}")
        if entry.cwe_ids:
            lines.append(f"  CWE: {', '.join(entry.cwe_ids)}")
        if entry.cvss_base_score is not None:
            lines.append(f"  CVSS: {entry.cvss_base_score}")
        if entry.attack_vector:
            lines.append(f"  Attack Vector: {entry.attack_vector}")
        if entry.attack_complexity:
            lines.append(f"  Complexity: {entry.attack_complexity}")
        if entry.affected_products:
            lines.append(f"  Affected: {', '.join((entry.affected_products or [])[:3])}")
        if entry.ru_explainer:
            lines.append(f"  Explainer: {entry.ru_explainer[:600]}")
        lines.append("")
    return "\n".join(lines)


def _validate_championship_json(parsed: dict) -> None:
    stages = parsed.get("stages")
    if not isinstance(stages, list) or len(stages) < 2:
        raise ChampionshipGenerationError(
            "Model response missing valid 'stages' array (minimum 2 stages required)"
        )
    seen_flag_ids: set[str] = set()
    for stage in stages:
        if not isinstance(stage, dict):
            raise ChampionshipGenerationError("Each stage must be a JSON object")
        idx = stage.get("index", "?")
        flag_id = stage.get("flag_id", "")
        if not flag_id:
            raise ChampionshipGenerationError(f"Stage {idx} missing flag_id")
        if flag_id in seen_flag_ids:
            raise ChampionshipGenerationError(f"Duplicate flag_id '{flag_id}' in stages")
        seen_flag_ids.add(flag_id)
        access = (stage.get("access_type") or "just_flag").lower()
        if access == "chat":
            if not (stage.get("chat_system_prompt_template") or "").strip():
                raise ChampionshipGenerationError(
                    f"Stage {idx} has access_type='chat' but missing chat_system_prompt_template"
                )
        else:
            if not (stage.get("expected_value") or "").strip():
                raise ChampionshipGenerationError(
                    f"Stage {idx} ({access}) missing expected_value"
                )


def _run_championship_generation(
    kb_entries: list[KBEntry],
    base_difficulty: int,
    system_prompt: str,
    model_uri: str,
) -> dict[str, Any]:
    from app.config import settings

    client = _build_client()
    reasoning_effort = settings.YANDEX_REASONING_EFFORT or "high"

    kb_text = _format_kb_entries_for_prompt(kb_entries)
    stage_count = min(3, max(2, len(kb_entries)))
    user_payload = {
        "base_difficulty": base_difficulty,
        "stage_count": stage_count,
        "kb_entries": kb_text,
    }

    try:
        response = client.chat.completions.create(
            model=model_uri,
            reasoning_effort=reasoning_effort,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        )
    except Exception as exc:
        raise ChampionshipGenerationError(f"Yandex model request failed: {exc}") from exc

    raw_text = (response.choices[0].message.content or "").strip()
    cleaned = _strip_code_fence(raw_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ChampionshipGenerationError(f"Model returned invalid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ChampionshipGenerationError(
            f"Expected JSON object root, got {type(parsed).__name__}"
        )

    _validate_championship_json(parsed)
    parsed["kind"] = "championship"

    return {
        "model": model_uri,
        "reasoning_effort": reasoning_effort,
        "raw_text": raw_text,
        "parsed": parsed,
        "kb_entry_ids": [e.id for e in kb_entries],
    }


async def generate_championship_task(
    *,
    kb_entries: list[KBEntry],
    base_difficulty: int,
    system_prompt: str,
    model_uri: str,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _run_championship_generation,
        kb_entries,
        base_difficulty,
        system_prompt,
        model_uri,
    )


async def select_kb_entry_clusters(
    db: AsyncSession,
    *,
    mode: Literal["explicit", "filter"],
    kb_entry_ids: Optional[list[int]],
    filters: Optional[dict],
    count: int,
    k_per_task: int = 3,
) -> list[list[KBEntry]]:
    """Return `count` clusters, each containing up to k_per_task related KBEntry rows."""
    if mode == "explicit" and kb_entry_ids:
        rows = (
            await db.execute(select(KBEntry).where(KBEntry.id.in_(kb_entry_ids)))
        ).scalars().all()
        if not rows:
            raise ChampionshipGenerationError("No kb_entries found for provided IDs")
        clusters: list[list[KBEntry]] = []
        for i in range(0, len(rows), k_per_task):
            chunk = list(rows[i : i + k_per_task])
            if chunk:
                clusters.append(chunk)
        if not clusters:
            raise ChampionshipGenerationError("Could not form clusters from provided IDs")
        return [clusters[i % len(clusters)] for i in range(count)]

    # Filter mode
    filters = filters or {}
    conditions = ["visible_in_kb_list = TRUE", "embedding IS NOT NULL"]
    params: dict[str, Any] = {}

    cwe_ids = filters.get("cwe_ids")
    if cwe_ids:
        conditions.append("cwe_ids && :cwe_ids")
        params["cwe_ids"] = cwe_ids

    cvss_min = filters.get("cvss_min")
    if cvss_min is not None:
        conditions.append("cvss_base_score >= :cvss_min")
        params["cvss_min"] = float(cvss_min)

    cvss_max = filters.get("cvss_max")
    if cvss_max is not None:
        conditions.append("cvss_base_score <= :cvss_max")
        params["cvss_max"] = float(cvss_max)

    filter_tags = filters.get("tags")
    if filter_tags:
        conditions.append("tags && :tags")
        params["tags"] = filter_tags

    where_clause = " AND ".join(conditions)
    params["limit"] = max(count * k_per_task * 4, 40)

    seed_rows = (
        await db.execute(
            text(
                f"""
                SELECT id FROM kb_entries
                WHERE {where_clause}
                ORDER BY RANDOM()
                LIMIT :limit
                """
            ),
            params,
        )
    ).fetchall()
    seed_ids = [row[0] for row in seed_rows]

    if not seed_ids:
        # Fall back without the embedding IS NOT NULL constraint
        params2 = {k: v for k, v in params.items()}
        conditions2 = [c for c in conditions if "embedding" not in c]
        where2 = " AND ".join(conditions2)
        seed_rows2 = (
            await db.execute(
                text(
                    f"""
                    SELECT id FROM kb_entries
                    WHERE {where2}
                    ORDER BY RANDOM()
                    LIMIT :limit
                    """
                ),
                params2,
            )
        ).fetchall()
        seed_ids = [row[0] for row in seed_rows2]

    if not seed_ids:
        raise ChampionshipGenerationError("No kb_entries found matching the provided filters")

    all_entries = (
        await db.execute(select(KBEntry).where(KBEntry.id.in_(seed_ids)))
    ).scalars().all()

    used_ids: set[int] = set()
    result_clusters: list[list[KBEntry]] = []

    for seed_entry in all_entries:
        if seed_entry.id in used_ids or len(result_clusters) >= count:
            continue
        cluster: list[KBEntry] = [seed_entry]
        used_ids.add(seed_entry.id)

        seed_cwes = set(seed_entry.cwe_ids or [])
        seed_tags = set(seed_entry.tags or [])

        for candidate in all_entries:
            if candidate.id in used_ids or len(cluster) >= k_per_task:
                continue
            cand_cwes = set(candidate.cwe_ids or [])
            cand_tags = set(candidate.tags or [])
            if seed_cwes & cand_cwes or seed_tags & cand_tags:
                cluster.append(candidate)
                used_ids.add(candidate.id)

        result_clusters.append(cluster)

    if not result_clusters:
        raise ChampionshipGenerationError("Could not form any valid KB entry clusters from filters")

    return [result_clusters[i % len(result_clusters)] for i in range(count)]
