"""
Binary reward check validator for AI-generated CTF challenges.

Each check returns a RewardCheck with score 0.0 (fail) or 1.0 (pass).
"""
from __future__ import annotations

import base64
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
    """Compute semantic similarity between generated spec and RAG context entries."""
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
    finally:
        await svc.close()

    # Collect embeddings from RAG entries (they were pre-embedded)
    best_similarity = 0.0
    for entry in rag_context.cve_entries:
        # We don't have the stored vector here — embed the text inline
        pass

    # Simple approach: embed each entry's text and compare
    svc2 = EmbeddingService()
    try:
        similarities: list[float] = []
        for entry in rag_context.cve_entries:
            entry_text = " ".join(filter(None, [
                entry.cve_id or "",
                entry.ru_title or "",
                entry.ru_summary or "",
                (entry.raw_en_text or "")[:200],
            ]))
            if not entry_text.strip():
                continue
            try:
                entry_vec = await svc2.embed_document(entry_text)
                dist = cosine_distance(spec_vec, entry_vec)
                similarity = 1.0 - dist
                similarities.append(similarity)
            except EmbeddingError:
                pass

        if not similarities:
            score = 0.5
            detail = "Could not compute similarity — neutral score"
        else:
            best_similarity = max(similarities)
            if best_similarity >= 0.8:
                score = 1.0
            elif best_similarity >= 0.6:
                score = 0.7
            elif best_similarity >= 0.4:
                score = 0.4
            else:
                score = 0.1
            detail = f"Best cosine similarity to RAG context: {best_similarity:.3f}"
    finally:
        await svc2.close()

    return RewardCheck(
        type=RewardType.RAG_GROUNDING,
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
    else:
        checks = [RewardCheck(
            type=RewardType.FUNCTIONAL,
            score=0.0,
            weight=1.0,
            detail=f"No validator for task_type {task_type!r}",
        )]

    # Append RAG grounding check if context provided
    if rag_context is not None:
        rag_weight = weights.get(RewardType.RAG_GROUNDING, 1.5)
        grounding_check = await check_rag_grounding(spec, rag_context, rag_weight)
        checks.append(grounding_check)

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
