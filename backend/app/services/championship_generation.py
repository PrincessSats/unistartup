import asyncio
import json
from typing import Any, Literal, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contest import (
    KBEntry,
    Task,
    TaskFlag,
    TaskMaterial,
    TaskAuthorSolution,
    LlmGeneration,
)
from app.services.task_generation import (
    _build_client,
    _strip_code_fence,
    TASK_MODEL_REGISTRY,
    DEFAULT_TASK_MODEL_KEY,
    TaskGenerationError,
)


class ChampionshipGenerationError(RuntimeError):
    pass


_VALID_CATEGORIES = {"web", "pwn", "crypto", "re", "forensics", "misc", "osint", "mobile", "hardware", "cloud"}
_VALID_ACCESS_TYPES = {"vpn", "vm", "link", "file", "chat", "just_flag"}


def _coerce_access_type(value: Optional[str]) -> str:
    value = (value or "").strip().lower()
    return value if value in _VALID_ACCESS_TYPES else "just_flag"


def _coerce_category(value: Optional[str]) -> str:
    value = (value or "misc").strip().lower()
    return value if value in _VALID_CATEGORIES else "misc"


def _normalize_tags(raw_tags: Optional[list[str]]) -> list[str]:
    return [tag.strip() for tag in (raw_tags or []) if tag and tag.strip()]


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
    avoid_categories: Optional[list[str]] = None,
    avoid_titles: Optional[list[str]] = None,
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
    if avoid_categories:
        user_payload["avoid_categories"] = sorted(set(avoid_categories))
    if avoid_titles:
        user_payload["avoid_titles"] = avoid_titles

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
    avoid_categories: Optional[list[str]] = None,
    avoid_titles: Optional[list[str]] = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _run_championship_generation,
        kb_entries,
        base_difficulty,
        system_prompt,
        model_uri,
        avoid_categories,
        avoid_titles,
    )


async def materialize_championship_task(
    db: AsyncSession,
    *,
    result: dict[str, Any],
    base_difficulty: int,
    created_by: Optional[int],
) -> Task:
    """Persist a generated championship payload as a draft Task (+ flags/materials/solution).

    Does NOT attach the task to any contest and does NOT commit — the caller decides
    whether to add a ContestTask row and when to commit. Returns the flushed Task.
    """
    payload = result["parsed"]
    stages = payload.get("stages", []) or []
    stage_1 = stages[0] if stages else {}
    stage_1_access = _coerce_access_type(stage_1.get("access_type"))
    stage_1_chat_prompt = (stage_1.get("chat_system_prompt_template") or "").strip() or None

    difficulty = max(7, min(10, base_difficulty))
    points = 100 + (difficulty - 1) * 50

    task = Task(
        title=(payload.get("title") or "Championship Task").strip(),
        category=_coerce_category(payload.get("category")),
        difficulty=difficulty,
        points=points,
        tags=_normalize_tags(payload.get("tags") or []),
        language="ru",
        story=payload.get("narrative") or stage_1.get("story"),
        participant_description=stage_1.get("participant_description"),
        state="draft",
        task_kind="contest",
        access_type=stage_1_access,
        chat_system_prompt_template=stage_1_chat_prompt if stage_1_access == "chat" else None,
        chat_user_message_max_chars=300,
        chat_model_max_output_tokens=512,
        chat_session_ttl_minutes=180,
        llm_raw_response=payload,
        kb_entry_id=(result.get("kb_entry_ids") or [None])[0],
        created_by=created_by,
    )
    db.add(task)
    await db.flush()

    if payload.get("author_solution"):
        db.add(TaskAuthorSolution(
            task_id=task.id,
            creation_solution=payload["author_solution"],
        ))

    for stage in stages:
        flag_id = (stage.get("flag_id") or f"stage_{stage.get('index', 1)}").strip()
        s_access = _coerce_access_type(stage.get("access_type"))
        if s_access == "chat":
            db.add(TaskFlag(
                task_id=task.id,
                flag_id=flag_id,
                format="FLAG{8HEX}",
                expected_value=None,
                description=stage.get("title"),
            ))
        else:
            db.add(TaskFlag(
                task_id=task.id,
                flag_id=flag_id,
                format="FLAG{...}",
                expected_value=(stage.get("expected_value") or "").strip(),
                description=stage.get("title"),
            ))

        for mat in (stage.get("materials") or []):
            mat_name = (mat.get("name") or "").strip()
            if not mat_name:
                continue
            db.add(TaskMaterial(
                task_id=task.id,
                type=(mat.get("type") or "text").strip().lower(),
                name=mat_name,
                description=(mat.get("description") or "").strip() or None,
                url=None,
                storage_key=None,
                meta={
                    "stage_index": stage.get("index", 1),
                    "role": mat.get("role", "primary"),
                },
            ))

    db.add(LlmGeneration(
        model=result.get("model"),
        purpose="championship_task_generation",
        input_payload={"kb_entry_ids": result.get("kb_entry_ids"), "base_difficulty": base_difficulty},
        output_payload=payload,
        created_by=created_by,
    ))

    return task


async def select_kb_entry_clusters(
    db: AsyncSession,
    *,
    mode: Literal["explicit", "filter"],
    kb_entry_ids: Optional[list[int]],
    filters: Optional[dict],
    count: int,
    k_per_task: int = 3,
    diversify: bool = False,
) -> list[list[KBEntry]]:
    """Return up to `count` clusters, each containing up to k_per_task related KBEntry rows.

    When `diversify` is True, clusters are kept thematically distinct (no shared CWE/tag
    between cluster seeds) and the result is NOT padded by cycling — so each generated task
    has a different theme. When False, the legacy behavior pads to exactly `count` by cycling.
    """
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
        if diversify:
            return clusters[:count]
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
    chosen_signatures: list[tuple[set, set]] = []

    for seed_entry in all_entries:
        if seed_entry.id in used_ids or len(result_clusters) >= count:
            continue

        seed_cwes = set(seed_entry.cwe_ids or [])
        seed_tags = set(seed_entry.tags or [])

        # Diversify: skip a seed whose theme (CWE/tag) overlaps an already-chosen cluster,
        # so the N clusters yield N distinct task themes (no crypto+crypto in one batch).
        if diversify and any(
            (seed_cwes & sig_cwes) or (seed_tags & sig_tags)
            for sig_cwes, sig_tags in chosen_signatures
        ):
            continue

        cluster: list[KBEntry] = [seed_entry]
        used_ids.add(seed_entry.id)

        for candidate in all_entries:
            if candidate.id in used_ids or len(cluster) >= k_per_task:
                continue
            cand_cwes = set(candidate.cwe_ids or [])
            cand_tags = set(candidate.tags or [])
            if seed_cwes & cand_cwes or seed_tags & cand_tags:
                cluster.append(candidate)
                used_ids.add(candidate.id)

        result_clusters.append(cluster)
        chosen_signatures.append((seed_cwes, seed_tags))

    if not result_clusters:
        raise ChampionshipGenerationError("Could not form any valid KB entry clusters from filters")

    if diversify:
        return result_clusters[:count]
    return [result_clusters[i % len(result_clusters)] for i in range(count)]
