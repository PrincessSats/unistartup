"""
Binary reward check validator for AI-generated CTF challenges.

Each check returns a RewardCheck with score 0.0 (fail) or 1.0 (pass).
"""
from __future__ import annotations

import base64
import io
import math
import re
import logging
from typing import Any, Optional

from app.services.ai_generator.artifact_creator import ArtifactResult
from app.services.ai_generator.crypto_utils import apply_chain, reverse_chain, CryptoError
from app.services.ai_generator.reward import RewardCheck, RewardType, REWARD_WEIGHTS

logger = logging.getLogger(__name__)

_FLAG_PATTERN = re.compile(r"^CTF\{[^}]+\}$")


def cosine_distance(a: list[float], b: list[float]) -> float:
    """Cosine distance (0=identical, 1=orthogonal, 2=opposite)."""
    if not a or not b or len(a) != len(b):
        return 1.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a < 1e-12 or mag_b < 1e-12:
        return 1.0
    return 1.0 - dot / (mag_a * mag_b)


async def check_rag_grounding(
    spec: dict[str, Any],
    rag_context: Any,  # RAGContext — avoid circular import
    weight: float,
) -> RewardCheck:
    """
    Compute semantic similarity between generated spec and RAG context entries.

    Uses pre-computed embeddings from kb_entries.embedding column when available,
    falling back to on-the-fly embedding only for entries without stored vectors.
    """
    from app.services.ai_generator.embedding_service import EmbeddingService, EmbeddingError
    from app.services.ai_generator.rag_context import RAGContext

    if not isinstance(rag_context, RAGContext) or rag_context.is_empty:
        return RewardCheck(
            type=RewardType.RAG_GROUNDING,
            score=0.5,
            weight=weight,
            detail="No RAG context available — neutral score",
        )

    spec_text = " ".join(filter(None, [
        spec.get("title", ""),
        spec.get("description", ""),
    ]))
    if not spec_text.strip():
        return RewardCheck(
            type=RewardType.RAG_GROUNDING,
            score=0.5,
            weight=weight,
            detail="Spec has no title/description to embed",
        )

    svc = EmbeddingService()
    try:
        spec_vec = await svc.embed_document(spec_text)
    except EmbeddingError as exc:
        return RewardCheck(
            type=RewardType.RAG_GROUNDING,
            score=0.5,
            weight=weight,
            detail=f"Embedding error: {exc}",
            error=str(exc),
        )

    # Use pre-computed embeddings from RAG context entries
    # CVEEntry now includes the embedding vector from the database
    similarities: list[float] = []
    for entry in rag_context.cve_entries:
        # Prefer pre-computed embedding if available
        entry_vec = getattr(entry, 'stored_embedding', None)
        if entry_vec is None:
            # Fallback: embed on the fly (shouldn't happen for kb_entries with embeddings)
            entry_text = " ".join(filter(None, [
                entry.cve_id or "",
                entry.ru_title or "",
                entry.ru_summary or "",
                (entry.raw_en_text or "")[:200],
            ]))
            if not entry_text.strip():
                continue
            try:
                entry_vec = await svc.embed_document(entry_text)
            except EmbeddingError:
                continue

        dist = cosine_distance(spec_vec, entry_vec)
        similarity = 1.0 - dist
        similarities.append(similarity)

    await svc.close()

    if not similarities:
        return RewardCheck(
            type=RewardType.RAG_GROUNDING,
            score=0.5,
            weight=weight,
            detail="Could not compute similarity — neutral score",
        )

    best_similarity = max(similarities)
    # Adjusted thresholds for spec-to-CVE similarity
    # Note: spec is a creative scenario, CVE is technical description
    # So we expect lower similarity than document-to-document comparison
    if best_similarity >= 0.7:
        score = 1.0
    elif best_similarity >= 0.5:
        score = 0.7
    elif best_similarity >= 0.3:
        score = 0.4
    else:
        score = 0.1

    return RewardCheck(
        type=RewardType.RAG_GROUNDING,
        score=score,
        weight=weight,
        detail=f"Best cosine similarity to RAG context: {best_similarity:.3f}",
    )


def check_cve_relevance(
    spec: dict[str, Any],
    rag_context: Any,  # RAGContext — avoid circular import
    task_type: str,
    weight: float,
) -> RewardCheck:
    """Soft reward (0.0-1.0) checking whether the generated spec is technically
    connected to the CVE context, not just name-dropping the CVE ID.

    Scoring:
    - 1.0: spec description contains CWE-specific technical keywords from the CVE
    - 0.7: spec references CVE ID and mentions relevant domain terms
    - 0.4: spec mentions CVE ID but no technical connection evident
    - 0.1: no CVE reference found in spec
    """
    from app.services.ai_generator.rag_context import RAGContext

    if not isinstance(rag_context, RAGContext) or rag_context.is_empty:
        return RewardCheck(
            type=RewardType.CVE_RELEVANCE,
            score=0.5,
            weight=weight,
            detail="No RAG context — neutral score",
        )

    # Keywords that indicate genuine technical CVE integration per task type
    _TECHNICAL_KEYWORDS: dict[str, list[str]] = {
        "crypto_text_web": [
            "шифр", "алгоритм", "ключ", "xor", "caesar", "aes", "vigenere", "rot13",
            "base64", "hex", "шифрование", "слабый", "уязвимость", "перехват", "токен",
        ],
        "forensics_image_metadata": [
            "метаданные", "exif", "jpeg", "xmp", "изображение", "файл", "скрыт",
            "утечка", "данные", "криминалистика", "расследование", "следы",
        ],
        "web_static_xss": [
            "xss", "скрипт", "script", "инъекция", "payload", "javascript", "cookie",
            "фильтр", "bypass", "innerHTML", "onerror", "reflect", "stored",
        ],
        "chat_llm": [
            "промпт", "prompt", "инъекция", "jailbreak", "системный промпт", "модель",
            "llm", "роль", "инструкции", "bypass", "игнорируй", "забудь",
        ],
    }

    description = (spec.get("description") or "").lower()
    title = (spec.get("title") or "").lower()
    spec_text = description + " " + title

    # Collect CWE IDs from RAG context entries
    all_cwe_ids: list[str] = []
    cve_ids: list[str] = []
    for entry in rag_context.cve_entries:
        all_cwe_ids.extend(entry.cwe_ids or [])
        if entry.cve_id:
            cve_ids.append(entry.cve_id.lower())

    # Check if spec mentions CVE ID
    mentions_cve = any(cve_id in spec_text for cve_id in cve_ids)

    # Check for technical keywords relevant to task type
    tech_keywords = _TECHNICAL_KEYWORDS.get(task_type, [])
    matched_keywords = [kw for kw in tech_keywords if kw in spec_text]

    # Check if CWE descriptions appear in text
    from app.services.ai_generator.cwe_mapping import CWE_DESCRIPTIONS
    cwe_mentioned = any(
        cwe.lower() in spec_text or
        (CWE_DESCRIPTIONS.get(cwe, "").lower()[:20] in spec_text)
        for cwe in all_cwe_ids
    )

    if len(matched_keywords) >= 3 and (mentions_cve or cwe_mentioned):
        score = 1.0
        detail = f"Strong CVE integration: {len(matched_keywords)} technical keywords, CVE referenced"
    elif len(matched_keywords) >= 2 and mentions_cve:
        score = 0.7
        detail = f"Good CVE integration: {len(matched_keywords)} keywords + CVE ID present"
    elif mentions_cve or len(matched_keywords) >= 2:
        score = 0.4
        detail = f"Weak CVE integration: CVE={'yes' if mentions_cve else 'no'}, keywords={len(matched_keywords)}"
    else:
        score = 0.1
        detail = "No CVE reference or technical connection found in spec"

    return RewardCheck(
        type=RewardType.CVE_RELEVANCE,
        score=score,
        weight=weight,
        detail=detail,
    )


async def validate(
    task_type: str,
    spec: dict[str, Any],
    artifact: ArtifactResult,
    rag_context: Optional[Any] = None,
) -> list[RewardCheck]:
    """Dispatch to the appropriate validator for this task_type."""
    weights = REWARD_WEIGHTS.get(task_type, {})

    if task_type == "crypto_text_web":
        checks = _validate_crypto(spec, artifact, weights)
    elif task_type == "forensics_image_metadata":
        checks = await _validate_forensics(spec, artifact, weights)
    elif task_type == "web_static_xss":
        checks = _validate_xss(spec, artifact, weights)
    elif task_type == "chat_llm":
        checks = _validate_chat_llm(spec, artifact, weights)
    else:
        checks = [RewardCheck(
            type=RewardType.FUNCTIONAL,
            score=0.0,
            weight=1.0,
            detail=f"No validator for task_type {task_type!r}",
        )]

    # Append soft rewards if context provided
    if rag_context is not None:
        rag_weight = weights.get(RewardType.RAG_GROUNDING, 1.5)
        grounding_check = await check_rag_grounding(spec, rag_context, rag_weight)
        checks.append(grounding_check)

        cve_weight = weights.get(RewardType.CVE_RELEVANCE, 1.0)
        cve_check = check_cve_relevance(spec, rag_context, task_type, cve_weight)
        checks.append(cve_check)

    return checks


def _w(weights: dict, reward_type: RewardType) -> float:
    return weights.get(reward_type, 1.0)


def _validate_crypto(
    spec: dict[str, Any],
    artifact: ArtifactResult,
    weights: dict,
) -> list[RewardCheck]:
    checks: list[RewardCheck] = []

    # ── FORMAT check ─────────────────────────────────────────────────────────
    required_keys = {"title", "description", "flag", "crypto_chain", "writeup", "hints"}
    missing = required_keys - set(spec.keys())
    flag = (spec.get("flag") or "").strip()
    flag_valid = bool(_FLAG_PATTERN.match(flag))
    crypto_chain = spec.get("crypto_chain") or []
    chain_valid = isinstance(crypto_chain, list) and len(crypto_chain) > 0

    format_ok = (not missing) and flag_valid and chain_valid
    checks.append(RewardCheck(
        type=RewardType.FORMAT,
        score=1.0 if format_ok else 0.0,
        weight=_w(weights, RewardType.FORMAT),
        detail=(
            "All required fields present" if format_ok
            else f"Missing fields: {missing or set()}; "
                 f"flag_valid={flag_valid}, chain_valid={chain_valid}"
        ),
    ))

    # ── FUNCTIONAL check ─────────────────────────────────────────────────────
    if artifact.error:
        checks.append(RewardCheck(
            type=RewardType.FUNCTIONAL,
            score=0.0,
            weight=_w(weights, RewardType.FUNCTIONAL),
            detail="Artifact creation failed",
            error=artifact.error,
        ))
    else:
        checks.append(RewardCheck(
            type=RewardType.FUNCTIONAL,
            score=1.0,
            weight=_w(weights, RewardType.FUNCTIONAL),
            detail="apply_chain ran without error",
        ))

    # ── SOLVABILITY check ────────────────────────────────────────────────────
    ciphertext = artifact.content or ""
    solvable = False
    solve_detail = "No ciphertext to check"
    solve_error = None

    if ciphertext and flag and crypto_chain:
        try:
            recovered = reverse_chain(ciphertext, crypto_chain)
            solvable = flag in recovered
            solve_detail = f"reverse_chain recovered flag: {solvable}"
        except CryptoError as exc:
            solve_detail = "reverse_chain raised CryptoError"
            solve_error = str(exc)
        except Exception as exc:
            solve_detail = "reverse_chain unexpected error"
            solve_error = str(exc)

    checks.append(RewardCheck(
        type=RewardType.SOLVABILITY,
        score=1.0 if solvable else 0.0,
        weight=_w(weights, RewardType.SOLVABILITY),
        detail=solve_detail,
        error=solve_error,
    ))

    # ── NON_TRIVIALITY check ─────────────────────────────────────────────────
    trivial = False
    trivial_reason = ""

    if ciphertext and flag:
        # Check 1: flag not plaintext in ciphertext
        if flag in ciphertext:
            trivial = True
            trivial_reason = "flag appears as plaintext in ciphertext"

        # Check 2: single base64 decode doesn't reveal flag
        if not trivial:
            try:
                decoded = base64.b64decode(ciphertext.encode("ascii", errors="ignore")).decode("utf-8", errors="ignore")
                if flag in decoded:
                    trivial = True
                    trivial_reason = "single base64 decode reveals flag"
            except Exception:
                pass

    checks.append(RewardCheck(
        type=RewardType.NON_TRIVIALITY,
        score=0.0 if trivial else 1.0,
        weight=_w(weights, RewardType.NON_TRIVIALITY),
        detail=trivial_reason if trivial else "Flag not trivially recoverable",
    ))

    return checks


async def _validate_forensics(
    spec: dict[str, Any],
    artifact: ArtifactResult,
    weights: dict,
) -> list[RewardCheck]:
    from app.services.ai_generator.forensics_utils import (
        VALID_HIDE_IN, download_image, extract_metadata_field,
    )
    import asyncio

    checks: list[RewardCheck] = []

    # ── FORMAT check ─────────────────────────────────────────────────────────
    required_keys = {"title", "description", "flag", "hide_in", "decoy_metadata", "writeup", "hints"}
    missing = required_keys - set(spec.keys())
    flag = (spec.get("flag") or "").strip()
    flag_valid = bool(_FLAG_PATTERN.match(flag))
    hide_in = (spec.get("hide_in") or "").strip()
    hide_in_valid = hide_in in VALID_HIDE_IN
    decoy = spec.get("decoy_metadata") or {}
    decoy_valid = isinstance(decoy, dict) and len(decoy) >= 3

    format_ok = (not missing) and flag_valid and hide_in_valid and decoy_valid
    checks.append(RewardCheck(
        type=RewardType.FORMAT,
        score=1.0 if format_ok else 0.0,
        weight=_w(weights, RewardType.FORMAT),
        detail=(
            "All required fields present" if format_ok
            else (
                f"Missing fields: {missing or set()}; "
                f"flag_valid={flag_valid}, hide_in_valid={hide_in_valid} ({hide_in!r}), "
                f"decoy_valid={decoy_valid} ({len(decoy)} entries)"
            )
        ),
    ))

    # ── FUNCTIONAL check ─────────────────────────────────────────────────────
    s3_key = artifact.file_url if artifact else None
    image_bytes: Optional[bytes] = None

    if artifact and artifact.error:
        checks.append(RewardCheck(
            type=RewardType.FUNCTIONAL,
            score=0.0,
            weight=_w(weights, RewardType.FUNCTIONAL),
            detail="Artifact creation failed",
            error=artifact.error,
        ))
    elif not s3_key:
        checks.append(RewardCheck(
            type=RewardType.FUNCTIONAL,
            score=0.0,
            weight=_w(weights, RewardType.FUNCTIONAL),
            detail="No artifact file_url in artifact result",
        ))
    else:
        try:
            image_bytes = await asyncio.to_thread(download_image, s3_key)
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()
            size_kb = len(image_bytes) / 1024
            checks.append(RewardCheck(
                type=RewardType.FUNCTIONAL,
                score=1.0,
                weight=_w(weights, RewardType.FUNCTIONAL),
                detail=f"Valid JPEG image, {size_kb:.1f}KB",
            ))
            # Re-open for further use (verify() closes the file)
            image_bytes = await asyncio.to_thread(download_image, s3_key)
        except Exception as exc:
            checks.append(RewardCheck(
                type=RewardType.FUNCTIONAL,
                score=0.0,
                weight=_w(weights, RewardType.FUNCTIONAL),
                detail=f"Image validation failed: {exc}",
                error=str(exc),
            ))
            image_bytes = None

    # ── SOLVABILITY check ────────────────────────────────────────────────────
    if image_bytes is None or not flag or not hide_in_valid:
        checks.append(RewardCheck(
            type=RewardType.SOLVABILITY,
            score=0.0,
            weight=_w(weights, RewardType.SOLVABILITY),
            detail="No artifact" if image_bytes is None else "Invalid spec — skipping solvability",
        ))
    else:
        try:
            extracted = await asyncio.to_thread(extract_metadata_field, image_bytes, hide_in)
            if extracted is not None and flag in extracted:
                checks.append(RewardCheck(
                    type=RewardType.SOLVABILITY,
                    score=1.0,
                    weight=_w(weights, RewardType.SOLVABILITY),
                    detail=f"Flag found in {hide_in}",
                ))
            else:
                checks.append(RewardCheck(
                    type=RewardType.SOLVABILITY,
                    score=0.0,
                    weight=_w(weights, RewardType.SOLVABILITY),
                    detail=f"Flag NOT found in {hide_in}; extracted={extracted!r}",
                ))
        except Exception as exc:
            checks.append(RewardCheck(
                type=RewardType.SOLVABILITY,
                score=0.0,
                weight=_w(weights, RewardType.SOLVABILITY),
                detail=f"extract_metadata_field error: {exc}",
                error=str(exc),
            ))

    # ── NON_TRIVIALITY check ─────────────────────────────────────────────────
    description = (spec.get("description") or "").lower()
    title = (spec.get("title") or "").lower()
    trivial = False
    trivial_reason = ""

    if flag and flag.lower() in description:
        trivial = True
        trivial_reason = "flag appears in description"
    elif flag and flag.lower() in title:
        trivial = True
        trivial_reason = "flag appears in title"
    elif hide_in and hide_in.replace("_", " ") in description:
        trivial = True
        trivial_reason = f"hide_in field name {hide_in!r} mentioned in description"

    checks.append(RewardCheck(
        type=RewardType.NON_TRIVIALITY,
        score=0.0 if trivial else 1.0,
        weight=_w(weights, RewardType.NON_TRIVIALITY),
        detail=trivial_reason if trivial else "Flag location not disclosed in description",
    ))

    return checks


# ── web_static_xss validator ──────────────────────────────────────────────────

def _validate_xss(
    spec: dict,
    artifact,  # ArtifactResult | None
    weights: dict[RewardType, float],
) -> list[RewardCheck]:
    checks: list[RewardCheck] = []

    # ── FORMAT ────────────────────────────────────────────────────────────────
    required = {"title", "description", "flag", "xss_type", "vulnerable_param",
                "payload_solution", "writeup", "hints"}
    missing = required - spec.keys()
    flag = spec.get("flag", "")
    valid_xss_types = {"reflected", "stored", "dom"}
    xss_type = spec.get("xss_type", "")

    format_ok = (
        not missing
        and bool(re.fullmatch(r"CTF\{[A-Za-z0-9_]+\}", flag))
        and xss_type in valid_xss_types
        and isinstance(spec.get("hints"), list)
        and len(spec.get("hints", [])) >= 1
    )
    checks.append(RewardCheck(
        type=RewardType.FORMAT,
        score=1.0 if format_ok else 0.0,
        weight=_w(weights, RewardType.FORMAT),
        detail="OK" if format_ok else f"missing={missing}, xss_type={xss_type!r}",
    ))

    # ── FUNCTIONAL ────────────────────────────────────────────────────────────
    functional_ok = artifact is not None and bool(getattr(artifact, "file_url", None))
    checks.append(RewardCheck(
        type=RewardType.FUNCTIONAL,
        score=1.0 if functional_ok else 0.0,
        weight=_w(weights, RewardType.FUNCTIONAL),
        detail="HTML page uploaded" if functional_ok else "No artifact / upload failed",
    ))

    # ── SOLVABILITY ───────────────────────────────────────────────────────────
    payload = spec.get("payload_solution", "")
    xss_keywords = {"<script", "onerror", "onload", "alert(", "eval(", "document.", "window."}
    solvable = any(kw in payload.lower() for kw in xss_keywords) and bool(flag)
    checks.append(RewardCheck(
        type=RewardType.SOLVABILITY,
        score=1.0 if solvable else 0.0,
        weight=_w(weights, RewardType.SOLVABILITY),
        detail="Payload contains XSS trigger" if solvable else f"Weak payload: {payload[:80]!r}",
    ))

    # ── NON_TRIVIALITY ────────────────────────────────────────────────────────
    description = (spec.get("description") or "").lower()
    title = (spec.get("title") or "").lower()
    trivial = (flag and flag.lower() in description) or (flag and flag.lower() in title)
    checks.append(RewardCheck(
        type=RewardType.NON_TRIVIALITY,
        score=0.0 if trivial else 1.0,
        weight=_w(weights, RewardType.NON_TRIVIALITY),
        detail="Flag in description/title" if trivial else "Flag not disclosed",
    ))

    return checks


# ── chat_llm validator ────────────────────────────────────────────────────────

def _validate_chat_llm(
    spec: dict,
    artifact,  # ArtifactResult | None
    weights: dict[RewardType, float],
) -> list[RewardCheck]:
    checks: list[RewardCheck] = []

    # ── FORMAT ────────────────────────────────────────────────────────────────
    required = {"title", "description", "flag", "system_prompt_template",
                "defense_type", "writeup", "hints"}
    missing = required - spec.keys()
    flag = spec.get("flag", "")
    valid_defense_types = {"instructions", "role", "context_boundary"}
    defense_type = spec.get("defense_type", "")
    system_prompt = spec.get("system_prompt_template", "")

    format_ok = (
        not missing
        and bool(re.fullmatch(r"CTF\{[A-Za-z0-9_]+\}", flag))
        and defense_type in valid_defense_types
        and "{{FLAG}}" in system_prompt
        and isinstance(spec.get("hints"), list)
        and len(spec.get("hints", [])) >= 1
    )
    checks.append(RewardCheck(
        type=RewardType.FORMAT,
        score=1.0 if format_ok else 0.0,
        weight=_w(weights, RewardType.FORMAT),
        detail="OK" if format_ok else (
            f"missing={missing}" if missing else
            f"defense_type={defense_type!r}" if defense_type not in valid_defense_types else
            "system_prompt_template missing {{FLAG}}"
        ),
    ))

    # ── FUNCTIONAL ────────────────────────────────────────────────────────────
    prompt_len = len(system_prompt)
    functional_ok = 50 <= prompt_len <= 3000 and "{{FLAG}}" in system_prompt
    checks.append(RewardCheck(
        type=RewardType.FUNCTIONAL,
        score=1.0 if functional_ok else 0.0,
        weight=_w(weights, RewardType.FUNCTIONAL),
        detail=f"prompt_len={prompt_len}" if functional_ok else
               f"Invalid system prompt (len={prompt_len}, has_placeholder={'{{FLAG}}' in system_prompt})",
    ))

    # ── SOLVABILITY ───────────────────────────────────────────────────────────
    prompt_lower = system_prompt.lower()
    has_guard = any(kw in prompt_lower for kw in
                    ["не раскрывай", "не говори", "секрет", "secret", "не сообщай",
                     "keep it secret", "do not reveal", "don't reveal", "never reveal"])
    over_restrictive = "отвечай только" in prompt_lower and len(system_prompt) < 100
    solvable = has_guard and not over_restrictive
    checks.append(RewardCheck(
        type=RewardType.SOLVABILITY,
        score=1.0 if solvable else 0.5,
        weight=_w(weights, RewardType.SOLVABILITY),
        detail="Guard found" if solvable else "No guard instructions or over-restrictive prompt",
    ))

    # ── NON_TRIVIALITY ────────────────────────────────────────────────────────
    description = (spec.get("description") or "").lower()
    title = (spec.get("title") or "").lower()
    flag_inner = flag[4:-1].lower() if len(flag) > 5 else flag.lower()
    trivial = (
        (flag and flag.lower() in description)
        or (flag and flag.lower() in title)
        or (flag_inner and flag_inner in prompt_lower)
    )
    checks.append(RewardCheck(
        type=RewardType.NON_TRIVIALITY,
        score=0.0 if trivial else 1.0,
        weight=_w(weights, RewardType.NON_TRIVIALITY),
        detail="Flag exposed in prompt/description" if trivial else "Flag properly guarded",
    ))

    return checks
