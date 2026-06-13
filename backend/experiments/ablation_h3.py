#!/usr/bin/env python
"""
H₃ Ablation Experiment
=======================
Causally measures how much each pipeline component contributes to CTF-task quality
by running paired conditions over a fixed CVE pool.

Conditions (task-type-aware — see conditions_for())
---------------------------------------------------
full          : full GRPO pipeline (N=AI_GEN_NUM_VARIANTS variants + RAG + self-test)
no_rag        : identical, but RAG context is NOT injected into the LLM prompt
no_bon        : identical, but N=1 (single candidate; no group-relative ranking)
no_self_test  : identical, but the XSS Serverless-Container self-test is disabled
                (enable_self_test=False) so SOLVABILITY falls back to the static
                keyword heuristic. ── web_static_xss ONLY ──

The no_self_test condition is meaningful ONLY for task_type=web_static_xss AND when
AI_GEN_ENABLE_SELFTEST=true with AI_GEN_SELFTEST_URL set. For crypto/forensics/chat
the `enable_self_test` flag is inert (those validators use in-process solvers), so
those task types run only the first 3 conditions — conditions_for() enforces this.

Quality metrics
---------------
"ES" maps to two scalars, both recorded per (CVE, condition):
  total_reward  — weighted mean of ALL reward checks (binary gates + QUALITY + soft rewards)
                  This is the production selection signal (gate: >= AI_GEN_MIN_REWARD_THRESHOLD).
  quality_score — LLM-as-judge mean of 5 dimensions only (0-1 float; 0.0 when variant
                  did not pass binary gates, since judge is skipped in that case).

Cost
----
Computed as: cost_rub = tokens_in * rub_in + tokens_out * rub_out
Default rates: 0.0003 RUB/input-token, 0.0005 RUB/output-token (deepseek-v4-flash; CLI-overridable).
NOTE: These rates are NOT from production — production does not compute RUB costs.
NOTE: Only spec-generation tokens are counted (tokens_input/output from AIGenerationVariant).
      LLM-judge (review_variant) tokens are NOT persisted by the pipeline, so judge
      inference cost is excluded rather than estimated.

Usage
-----
See experiments/README.md for full instructions.

Quick start:
    cd backend/
    # dry-run (2 CVEs x 3 conditions = 6 calls):
    python -m experiments.ablation_h3 --dry-run

    # full run:
    python -m experiments.ablation_h3 --pool-size 80 --seed 1337

    # resume after crash (reads checkpoint from results_raw.csv):
    python -m experiments.ablation_h3 --pool-size 80 --seed 1337
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import math
import random
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Backend bootstrap ─────────────────────────────────────────────────────────
# Must be run from backend/ directory:  python -m experiments.ablation_h3
# OR:  PYTHONPATH=backend python experiments/ablation_h3.py
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.ai_generation import AIGenerationBatch, AIGenerationVariant
from app.models.contest import KBEntry
from app.services.ai_generator.pipeline import (
    run_pipeline,
    GENERATOR_MODEL_ID,
    GENERATOR_MODEL_VERSION,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("ablation_h3")
# Suppress noisy low-level loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# ── Constants ─────────────────────────────────────────────────────────────────

# Canonical condition order (used for printing/summary column order; absent ones skipped).
CONDITIONS: list[str] = ["full", "no_rag", "no_bon", "no_self_test"]

# The XSS self-test target type. `enable_self_test` is read ONLY inside _validate_xss,
# so no_self_test is a real ablation only here; everywhere else full ≡ no_self_test.
SELFTEST_TASK_TYPE = "web_static_xss"


def conditions_for(task_type: str) -> list[str]:
    """
    Conditions to actually RUN for a given task type.

    web_static_xss → all 4 (no_self_test ablates the live browser self-test).
    everything else → first 3 (no_self_test would be a vacuous duplicate of full,
                      wasting ~N pipeline calls and producing a noise-only delta).
    """
    if task_type == SELFTEST_TASK_TYPE:
        return ["full", "no_rag", "no_bon", "no_self_test"]
    return ["full", "no_rag", "no_bon"]


def _solvability_source(detail: str) -> str:
    """
    Classify where an XSS SOLVABILITY verdict came from, by parsing the check detail
    string produced in validator._validate_xss.

    Returns one of: live_pass | live_fail | static | na
      live_*  — authoritative Serverless-Container browser verdict
      static  — static keyword heuristic (self-test disabled, fell back, or errored)
      na      — no recognisable marker (e.g. non-XSS task types)
    """
    d = detail or ""
    if d.startswith("Self-test PASS"):
        return "live_pass"
    if d.startswith("Self-test FAIL"):
        return "live_fail"
    dl = d.lower()
    if "heuristic" in dl or "static" in dl or "weak payload" in dl:
        return "static"
    return "na"

# All columns written to results_raw.csv (one row per CVE × condition).
CSV_FIELDS: list[str] = [
    # --- Identity ---
    "cve_id",
    "condition",
    "batch_id",
    "batch_status",
    # --- Quality metrics (the two "ES" proxies) ---
    "total_reward",       # weighted mean of ALL checks; production selection signal
    "quality_score",      # LLM-judge mean (0 if binary gates failed)
    # --- Binary gate scores (0/1) from best variant ---
    "gate_FORMAT",
    "gate_FUNCTIONAL",
    "gate_SOLVABILITY",
    "gate_NON_TRIVIALITY",
    # --- Soft reward scores (0.0–1.0) from best variant ---
    "soft_RAG_GROUNDING",
    "soft_CVE_RELEVANCE",
    # --- Derived flags ---
    "passed_all_binary",  # 1 if all 4 binary gates passed
    "pub_ge_06",          # 1 if total_reward >= 0.6 (production gate)
    "pub_ge_090",         # 1 if total_reward >= 0.90 (thesis bar)
    "is_selected",        # 1 if pipeline marked this variant as selected
    "selection_status",   # "selected" | "best_unselected" | "none"
    # --- XSS self-test provenance (web_static_xss only; blank otherwise) ---
    "solvability_source", # live_pass | live_fail | static | na  (best variant)
    "xss_selftest_live",  # 1 if best variant SOLVABILITY came from live container
    "n_selftest_live",    # count of batch variants with a live container verdict
    # --- Resources (summed over ALL variants in batch) ---
    "tokens_in",
    "tokens_out",
    "selftest_cost_rub",  # n_selftest_live * rub_per_selftest (0 unless rate given)
    "cost_rub",           # token cost (+ selftest_cost_rub)
    "wall_clock_s",       # wall-clock time for run_pipeline call (seconds)
]


# ═══════════════════════════════════════════════════════════════════════════════
# CVE pool
# ═══════════════════════════════════════════════════════════════════════════════

async def fetch_cve_pool(db: AsyncSession, pool_size: int, seed: int) -> list[str]:
    """
    Sample `pool_size` CVE IDs from kb_entries (source='nvd', has embedding + cve_id).
    Uses a fixed seed for reproducibility.  Results are ordered by kb_entry.id before
    sampling so the pool is stable regardless of DB insertion order.
    """
    result = await db.execute(
        select(KBEntry.cve_id)
        .where(
            KBEntry.source == "nvd",
            KBEntry.cve_id.isnot(None),
            KBEntry.embedding.isnot(None),
        )
        .order_by(KBEntry.id)
    )
    all_ids: list[str] = [row[0] for row in result.fetchall()]

    if len(all_ids) < pool_size:
        logger.warning(
            "Requested pool_size=%d but only %d eligible CVEs found in kb_entries "
            "(source='nvd', embedding NOT NULL, cve_id NOT NULL). "
            "Reducing pool to %d.",
            pool_size, len(all_ids), len(all_ids),
        )
        pool_size = len(all_ids)

    rng = random.Random(seed)
    sample = rng.sample(all_ids, pool_size)
    logger.info("🎲 CVE pool: %d CVEs sampled (seed=%d)", len(sample), seed)
    return sample


# ═══════════════════════════════════════════════════════════════════════════════
# Batch creation & result extraction
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_batch(
    db: AsyncSession,
    *,
    task_type: str,
    difficulty: str,
    num_variants: int,
) -> uuid.UUID:
    """
    Insert an AIGenerationBatch row and commit.  Returns the batch UUID.
    Mirrors the pattern in backend/app/routes/ai_generate.py:start_generation.
    requested_by=None: this is an automated experiment, not a user request.
    """
    batch_id = uuid.uuid4()
    batch = AIGenerationBatch(
        id=batch_id,
        requested_by=None,
        task_type=task_type,
        difficulty=difficulty,
        num_variants=num_variants,
        status="pending",
    )
    db.add(batch)
    await db.commit()
    return batch_id


async def _extract_result(
    db: AsyncSession,
    batch_id: uuid.UUID,
    *,
    cve_id: str,
    condition: str,
    task_type: str,
    wall_clock_s: float,
    rub_in: float,
    rub_out: float,
    rub_per_selftest: float,
    out_dir: Path,
) -> dict[str, Any]:
    """
    Read the completed batch + its variants from DB after run_pipeline returns.

    Best-variant selection:
      1. Use the variant marked is_selected=True (pipeline's own choice).
      2. If none selected, use the variant with the highest total_reward.
         (This ensures we always have a quality measurement even when no variant
          cleared the reward threshold — the row records is_selected=0 so it's
          honest in the CSV.)

    Token/cost accounting:
      Tokens summed over ALL variants (spec-generation only; judge tokens excluded
      because review_variant does not persist its token usage to the DB).
    """
    # ── Fetch batch ───────────────────────────────────────────────────────────
    batch_res = await db.execute(
        select(AIGenerationBatch).where(AIGenerationBatch.id == batch_id)
    )
    batch: Optional[AIGenerationBatch] = batch_res.scalar_one_or_none()
    batch_status = batch.status if batch else "unknown"

    # ── Fetch all variants for this batch ─────────────────────────────────────
    var_res = await db.execute(
        select(AIGenerationVariant)
        .where(AIGenerationVariant.batch_id == batch_id)
    )
    variants: list[AIGenerationVariant] = var_res.scalars().all()

    # ── Pick best variant ─────────────────────────────────────────────────────
    best: Optional[AIGenerationVariant] = None
    for v in variants:
        if v.is_selected:
            best = v
            break
    if best is None and variants:
        best = max(variants, key=lambda v: (v.reward_total or 0.0))

    selection_status = "none"
    if best is not None:
        selection_status = "selected" if best.is_selected else "best_unselected"

    # ── Aggregate tokens over entire batch ────────────────────────────────────
    total_tok_in = sum(v.tokens_input or 0 for v in variants)
    total_tok_out = sum(v.tokens_output or 0 for v in variants)
    token_cost_rub = total_tok_in * rub_in + total_tok_out * rub_out

    # ── Extract per-check scores from best variant ────────────────────────────
    def _solvability_detail(variant) -> str:
        for chk in (variant.reward_checks or []):
            if chk.get("type") == "SOLVABILITY":
                return chk.get("detail", "") or ""
        return ""

    gate: dict[str, int] = {}
    soft: dict[str, float] = {}
    if best is not None and best.reward_checks:
        for chk in best.reward_checks:
            t = chk.get("type", "")
            s = float(chk.get("score", 0.0))
            if t in ("FORMAT", "FUNCTIONAL", "SOLVABILITY", "NON_TRIVIALITY"):
                gate[t] = int(round(s))
            elif t in ("RAG_GROUNDING", "CVE_RELEVANCE"):
                soft[t] = round(s, 6)

    # ── XSS self-test provenance (only meaningful for web_static_xss) ─────────
    is_xss = task_type == SELFTEST_TASK_TYPE
    if is_xss:
        solvability_source = _solvability_source(_solvability_detail(best)) if best else "na"
        # count how many variants in the batch got an authoritative live verdict
        n_selftest_live = sum(
            1 for v in variants
            if _solvability_source(_solvability_detail(v)) in ("live_pass", "live_fail")
        )
    else:
        solvability_source = ""  # blank for non-XSS types
        n_selftest_live = 0
    xss_selftest_live = int(solvability_source in ("live_pass", "live_fail"))

    # ── Self-test compute cost (flat per live invocation; 0 unless rate given) ─
    selftest_cost_rub = n_selftest_live * rub_per_selftest
    cost_rub = token_cost_rub + selftest_cost_rub

    total_reward = float(best.reward_total or 0.0) if best else 0.0
    quality_score = float(best.quality_score or 0.0) if best else 0.0
    passed_all_binary = bool(best.passed_all_binary) if best else False

    # ── Save full artifact JSON ───────────────────────────────────────────────
    artifact_dir = out_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if best is not None:
        safe_cve = cve_id.replace("/", "_")
        artifact_path = artifact_dir / f"{safe_cve}__{condition}.json"
        with artifact_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "cve_id": cve_id,
                    "condition": condition,
                    "batch_id": str(batch_id),
                    "batch_status": batch_status,
                    "variant_id": str(best.id),
                    "is_selected": best.is_selected,
                    "selection_status": selection_status,
                    "total_reward": total_reward,
                    "quality_score": quality_score,
                    "solvability_source": solvability_source,
                    "xss_selftest_live": bool(xss_selftest_live),
                    "n_selftest_live": n_selftest_live,
                    "generated_spec": best.generated_spec,
                    "artifact_result": best.artifact_result,
                    "reward_checks": best.reward_checks,
                    "quality_details": best.quality_details,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    return {
        "cve_id": cve_id,
        "condition": condition,
        "batch_id": str(batch_id),
        "batch_status": batch_status,
        "total_reward": round(total_reward, 6),
        "quality_score": round(quality_score, 6),
        "gate_FORMAT": gate.get("FORMAT", ""),
        "gate_FUNCTIONAL": gate.get("FUNCTIONAL", ""),
        "gate_SOLVABILITY": gate.get("SOLVABILITY", ""),
        "gate_NON_TRIVIALITY": gate.get("NON_TRIVIALITY", ""),
        "soft_RAG_GROUNDING": soft.get("RAG_GROUNDING", ""),
        "soft_CVE_RELEVANCE": soft.get("CVE_RELEVANCE", ""),
        "passed_all_binary": int(passed_all_binary),
        "pub_ge_06": int(total_reward >= 0.6),
        "pub_ge_090": int(total_reward >= 0.90),
        "is_selected": int(bool(best.is_selected) if best else False),
        "selection_status": selection_status,
        "solvability_source": solvability_source,
        "xss_selftest_live": xss_selftest_live if is_xss else "",
        "n_selftest_live": n_selftest_live if is_xss else "",
        "tokens_in": total_tok_in,
        "tokens_out": total_tok_out,
        "selftest_cost_rub": round(selftest_cost_rub, 6),
        "cost_rub": round(cost_rub, 6),
        "wall_clock_s": round(wall_clock_s, 3),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Condition runner
# ═══════════════════════════════════════════════════════════════════════════════

async def run_one_condition(
    *,
    cve_id: str,
    condition: str,
    task_type: str,
    difficulty: str,
    num_variants_full: int,
    rub_in: float,
    rub_out: float,
    rub_per_selftest: float,
    out_dir: Path,
) -> dict[str, Any]:
    """
    Run one (CVE, condition) pair end-to-end.  Returns a CSV row dict.

    Session management mirrors the production _run_pipeline_bg wrapper
    (backend/app/routes/ai_generate.py): create batch in its own commit,
    then pass a fresh session to run_pipeline.

    Condition mapping:
      full          → num_variants=N  inject_rag=True   enable_self_test=True   (production default)
      no_rag        → num_variants=N  inject_rag=False  enable_self_test=True   (ablates RAG context)
      no_bon        → num_variants=1  inject_rag=True   enable_self_test=True   (ablates multi-candidate GRPO)
      no_self_test  → num_variants=N  inject_rag=True   enable_self_test=False  (ablates XSS browser self-test)
                      Note: only meaningful when --task-type=web_static_xss and
                      AI_GEN_ENABLE_SELFTEST=true; otherwise full ≡ no_self_test.
    """
    num_variants = 1 if condition == "no_bon" else num_variants_full
    inject_rag = condition != "no_rag"
    enable_self_test = condition != "no_self_test"

    # Step 1: create the batch row (committed before pipeline reads it)
    async with AsyncSessionLocal() as db:
        batch_id = await _create_batch(
            db,
            task_type=task_type,
            difficulty=difficulty,
            num_variants=num_variants,
        )

    # Step 2: run the pipeline (own session, same pattern as _run_pipeline_bg)
    t0 = time.monotonic()
    async with AsyncSessionLocal() as db:
        await run_pipeline(
            task_type=task_type,
            difficulty=difficulty,
            num_variants=num_variants,
            user_id=None,
            batch_id=batch_id,
            db=db,
            cve_id=cve_id,
            inject_rag=inject_rag,
            enable_self_test=enable_self_test,
        )
    wall_clock_s = time.monotonic() - t0

    # Step 3: read back results
    async with AsyncSessionLocal() as db:
        row = await _extract_result(
            db,
            batch_id,
            cve_id=cve_id,
            condition=condition,
            task_type=task_type,
            wall_clock_s=wall_clock_s,
            rub_in=rub_in,
            rub_out=rub_out,
            rub_per_selftest=rub_per_selftest,
            out_dir=out_dir,
        )

    return row


# ═══════════════════════════════════════════════════════════════════════════════
# Statistics (hand-rolled; no scipy dependency)
# ═══════════════════════════════════════════════════════════════════════════════

def _bootstrap_ci(
    values: list[float],
    n_boot: int = 10_000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """
    Non-parametric bootstrap confidence interval on the mean.

    Method: percentile bootstrap with `n_boot` resamples.
    No distribution assumption; appropriate for any continuous outcome.
    Returns (mean, lower_bound, upper_bound).

    Statistical note: percentile bootstrap is slightly conservative
    (wider CI than BCa) but unbiased and has no additional dependencies.
    """
    if not values:
        return float("nan"), float("nan"), float("nan")
    n = len(values)
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = (1.0 - ci) / 2.0
    lo_idx = max(0, int(math.floor(alpha * n_boot)))
    hi_idx = min(n_boot - 1, int(math.ceil((1.0 - alpha) * n_boot)) - 1)
    observed_mean = sum(values) / n
    return observed_mean, means[lo_idx], means[hi_idx]


def _norm_cdf(z: float) -> float:
    """Standard normal CDF via math.erfc (no scipy required)."""
    return math.erfc(z / math.sqrt(2.0)) / 2.0


def _wilcoxon_p(diffs: list[float]) -> float:
    """
    Two-sided Wilcoxon signed-rank test p-value (normal approximation,
    continuity correction, average-rank tie handling).

    Choice rationale
    ----------------
    Wilcoxon signed-rank is the default for paired difference testing when
    normality is not established.  With no scipy available, Shapiro-Wilk
    cannot be run; rather than defaulting to paired t-test (which assumes
    normality) we always use Wilcoxon (which only assumes symmetry of diffs
    around the true median — a much weaker assumption).

    Implementation
    --------------
    Uses normal approximation with continuity correction.  This approximation
    is reliable for n >= 10 (all practical pool sizes for this experiment).
    For n < 10 the approximation is labelled in output as approximate.

    Returns p-value in [0, 1].
    """
    nonzero = [d for d in diffs if abs(d) > 1e-12]
    if not nonzero:
        return 1.0
    n = len(nonzero)

    # Rank by |diff|, with average-rank tie breaking
    abs_vals = sorted(enumerate(nonzero), key=lambda x: abs(x[1]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n and abs(abs_vals[j][1]) == abs(abs_vals[i][1]):
            j += 1
        avg_rank = (i + j + 1) / 2.0  # 1-indexed
        for k in range(i, j):
            ranks[abs_vals[k][0]] = avg_rank
        i = j

    W_plus = sum(r for orig_i, r in enumerate(ranks) if nonzero[orig_i] > 0)
    W = min(W_plus, n * (n + 1) / 2.0 - W_plus)

    mu_W = n * (n + 1) / 4.0
    sigma_W = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
    if sigma_W < 1e-9:
        return 1.0

    z = (W - 0.5 - mu_W) / sigma_W  # continuity correction
    p = 2.0 * _norm_cdf(z)
    return min(max(p, 0.0), 1.0)


def _stdev(values: list[float], mean: float) -> float:
    """Sample standard deviation."""
    if len(values) < 2:
        return 0.0
    return math.sqrt(sum((x - mean) ** 2 for x in values) / (len(values) - 1))


# ═══════════════════════════════════════════════════════════════════════════════
# Summary & delta computation
# ═══════════════════════════════════════════════════════════════════════════════

def compute_summary(rows: list[dict]) -> dict[str, dict]:
    """
    Compute per-condition descriptive statistics.
    Only rows with non-empty total_reward are included.
    """
    by_cond: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("total_reward") not in ("", None):
            by_cond[r["condition"]].append(r)

    summary: dict[str, dict] = {}
    for cond, crows in by_cond.items():
        tr = [float(r["total_reward"]) for r in crows]
        # quality_score is 0 when judge was skipped; exclude zeros for mean
        qs = [float(r["quality_score"]) for r in crows if float(r.get("quality_score") or 0) > 0]
        pb = [int(r["passed_all_binary"]) for r in crows if r.get("passed_all_binary") != ""]
        p6 = [int(r["pub_ge_06"]) for r in crows if r.get("pub_ge_06") != ""]
        p9 = [int(r["pub_ge_090"]) for r in crows if r.get("pub_ge_090") != ""]
        cost = [float(r["cost_rub"]) for r in crows if r.get("cost_rub") not in ("", None)]
        wall = [float(r["wall_clock_s"]) for r in crows if r.get("wall_clock_s") not in ("", None)]

        tr_mean, tr_lo, tr_hi = _bootstrap_ci(tr)
        qs_mean, qs_lo, qs_hi = _bootstrap_ci(qs)

        summary[cond] = {
            "n": len(crows),
            "total_reward_mean": tr_mean,
            "total_reward_std": _stdev(tr, tr_mean),
            "total_reward_ci95_lo": tr_lo,
            "total_reward_ci95_hi": tr_hi,
            "quality_score_mean": qs_mean,
            "quality_score_std": _stdev(qs, qs_mean),
            "quality_score_ci95_lo": qs_lo,
            "quality_score_ci95_hi": qs_hi,
            "pass_rate": sum(pb) / len(pb) if pb else 0.0,
            "pub_ge_06_rate": sum(p6) / len(p6) if p6 else 0.0,
            "pub_ge_090_rate": sum(p9) / len(p9) if p9 else 0.0,
            "mean_cost_rub": sum(cost) / len(cost) if cost else 0.0,
            "mean_time_s": sum(wall) / len(wall) if wall else 0.0,
        }
    return summary


def compute_deltas(rows: list[dict]) -> dict[str, dict]:
    """
    Compute paired deltas: mean(full ES − ablated ES) for each ablated condition.

    Pairing: each CVE must appear in BOTH full and the ablated condition.
    CVEs missing from either condition are excluded from that delta calculation
    (logged as warnings).

    Two metrics:
      total_reward : always available (0.0 when pipeline failed)
      quality_score: only when both full and ablated scored > 0 (judge ran)

    Test: Wilcoxon signed-rank (two-sided, normal approximation).
    CI: bootstrap 95% on mean difference.
    """
    by_cve_cond: dict[tuple[str, str], dict] = {}
    for r in rows:
        if r.get("total_reward") not in ("", None):
            by_cve_cond[(r["cve_id"], r["condition"])] = r

    all_cves = {r["cve_id"] for r in rows}
    deltas: dict[str, dict] = {}

    # Only compute deltas for ablations actually present in the data — e.g.
    # no_self_test rows exist for web_static_xss only, so non-XSS runs must not
    # emit an empty (NaN) no_self_test delta.
    present_conditions = {r["condition"] for r in rows}
    ablations = [a for a in ["no_rag", "no_bon", "no_self_test"] if a in present_conditions]

    for ablated in ablations:
        tr_diffs: list[float] = []
        qs_diffs: list[float] = []
        missing: list[str] = []

        for cve_id in sorted(all_cves):
            full_row = by_cve_cond.get((cve_id, "full"))
            abl_row = by_cve_cond.get((cve_id, ablated))
            if full_row is None or abl_row is None:
                missing.append(cve_id)
                continue
            tr_diffs.append(float(full_row["total_reward"]) - float(abl_row["total_reward"]))
            qs_full = float(full_row.get("quality_score") or 0)
            qs_abl = float(abl_row.get("quality_score") or 0)
            if qs_full > 0 and qs_abl > 0:
                qs_diffs.append(qs_full - qs_abl)

        if missing:
            logger.warning(
                "Delta full-%s: %d CVEs missing from one side, excluded: %s",
                ablated, len(missing), missing[:5],
            )

        tr_mean_diff, tr_lo, tr_hi = _bootstrap_ci(tr_diffs)
        qs_mean_diff, qs_lo, qs_hi = _bootstrap_ci(qs_diffs)

        deltas[ablated] = {
            "n_pairs_total_reward": len(tr_diffs),
            "mean_diff_total_reward": tr_mean_diff,
            "diff_ci95_lo_total_reward": tr_lo,
            "diff_ci95_hi_total_reward": tr_hi,
            "wilcoxon_p_total_reward": _wilcoxon_p(tr_diffs) if tr_diffs else float("nan"),
            "n_pairs_quality_score": len(qs_diffs),
            "mean_diff_quality_score": qs_mean_diff,
            "diff_ci95_lo_quality_score": qs_lo,
            "diff_ci95_hi_quality_score": qs_hi,
            "wilcoxon_p_quality_score": _wilcoxon_p(qs_diffs) if qs_diffs else float("nan"),
        }
    return deltas


# ═══════════════════════════════════════════════════════════════════════════════
# Output formatting
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt(v: Any, width: int = 8, decimals: int = 4) -> str:
    if isinstance(v, float) and math.isnan(v):
        return f"{'NaN':>{width}}"
    if isinstance(v, float):
        return f"{v:>{width}.{decimals}f}"
    if isinstance(v, int):
        return f"{v:>{width}}"
    return f"{str(v):>{width}}"


def print_summary_table(summary: dict[str, dict]) -> None:
    cols = [
        ("Condition", 12, "condition", 0, "s"),
        ("N", 5, "n", 0, "d"),
        ("TotalR μ", 10, "total_reward_mean", 4, "f"),
        ("95% CI", 20, None, 0, "ci_tr"),
        ("QScore μ", 10, "quality_score_mean", 4, "f"),
        ("Pass%", 7, "pass_rate", 1, "%"),
        ("≥0.6", 6, "pub_ge_06_rate", 1, "%"),
        ("≥0.90", 6, "pub_ge_090_rate", 1, "%"),
        ("RUB/task", 9, "mean_cost_rub", 4, "f"),
        ("Time(s)", 8, "mean_time_s", 1, "f"),
    ]
    sep = "  "
    header = sep.join(f"{c[0]:<{c[1]}}" if c[0] == "Condition" else f"{c[0]:>{c[1]}}" for c in cols)
    rule = "─" * len(header)

    print()
    print("╔" + "═" * (len(header) + 2) + "╗")
    print("║  SUMMARY — per condition (bootstrap 95% CI, 10k resamples, percentile method)  ║"[:len(header)+4])
    print("╠" + "═" * (len(header) + 2) + "╣")
    print(f"║  {header}  ║")
    print(f"║  {rule}  ║")

    for cond in CONDITIONS:
        if cond not in summary:
            continue
        s = summary[cond]
        ci_tr = f"[{s['total_reward_ci95_lo']:.3f},{s['total_reward_ci95_hi']:.3f}]"
        row_parts = []
        for name, width, key, dec, fmt in cols:
            if fmt == "ci_tr":
                row_parts.append(f"{ci_tr:>{width}}")
            elif fmt == "s":
                row_parts.append(f"{cond:<{width}}")
            elif fmt == "d":
                row_parts.append(f"{s[key]:>{width}}")
            elif fmt == "%":
                row_parts.append(f"{s[key]:>{width}.{dec}%}")
            else:
                row_parts.append(f"{s[key]:>{width}.{dec}f}")
        print(f"║  {sep.join(row_parts)}  ║")

    print("╚" + "═" * (len(header) + 2) + "╝")


def print_delta_table(deltas: dict[str, dict]) -> None:
    print()
    print("╔" + "═" * 78 + "╗")
    print("║  COMPONENT CONTRIBUTION (causal ablation deltas: mean[full − ablated])        ║")
    print("║  Test: Wilcoxon signed-rank, two-sided, normal approx + continuity correction ║")
    print("║  CI:   non-parametric bootstrap 95% (10k resamples, percentile method)        ║")
    print("╠" + "═" * 78 + "╣")
    for ablated in ["no_rag", "no_bon", "no_self_test"]:
        if ablated not in deltas:
            continue
        d = deltas[ablated]
        label = {
            "no_rag": "RAG context",
            "no_bon": "GRPO multi-candidate",
            "no_self_test": "XSS browser self-test",
        }.get(ablated, ablated)
        print(f"║  Contribution of {label:<20} (full − {ablated})          ║"[:82])
        print(f"║  {'':78}  ║"[:82])

        tr_p = d["wilcoxon_p_total_reward"]
        tr_sig = "**" if tr_p < 0.01 else ("*" if tr_p < 0.05 else "ns")
        qs_p = d["wilcoxon_p_quality_score"]
        qs_sig = "**" if qs_p < 0.01 else ("*" if qs_p < 0.05 else "ns")

        print(
            f"║    total_reward : Δ={d['mean_diff_total_reward']:+.4f}"
            f"  95%CI=[{d['diff_ci95_lo_total_reward']:+.4f},{d['diff_ci95_hi_total_reward']:+.4f}]"
            f"  p={tr_p:.4f} {tr_sig}"
            f"  n={d['n_pairs_total_reward']}"
            f"  ║"[:82]
        )
        print(
            f"║    quality_score: Δ={d['mean_diff_quality_score']:+.4f}"
            f"  95%CI=[{d['diff_ci95_lo_quality_score']:+.4f},{d['diff_ci95_hi_quality_score']:+.4f}]"
            f"  p={qs_p:.4f} {qs_sig}"
            f"  n={d['n_pairs_quality_score']}"
            f"  ║"[:82]
        )
        print(f"║  {'':78}  ║"[:82])
    print("║  * p<0.05  ** p<0.01  ns = not significant                                   ║")
    print("╚" + "═" * 78 + "╝")


# ═══════════════════════════════════════════════════════════════════════════════
# CSV helpers
# ═══════════════════════════════════════════════════════════════════════════════

SUMMARY_FIELDS: list[str] = [
    "condition", "n",
    "total_reward_mean", "total_reward_std", "total_reward_ci95_lo", "total_reward_ci95_hi",
    "quality_score_mean", "quality_score_std", "quality_score_ci95_lo", "quality_score_ci95_hi",
    "pass_rate", "pub_ge_06_rate", "pub_ge_090_rate",
    "mean_cost_rub", "mean_time_s",
]


def save_summary_csv(summary: dict[str, dict], out_dir: Path) -> None:
    path = out_dir / "results_summary.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        for cond in CONDITIONS:
            if cond not in summary:
                continue
            row: dict[str, Any] = {"condition": cond}
            for k, v in summary[cond].items():
                row[k] = round(v, 6) if isinstance(v, float) else v
            w.writerow(row)
    logger.info("Saved %s", path)


def save_metadata(
    *,
    args: argparse.Namespace,
    cve_pool: list[str],
    model_uri: str,
    num_variants_full: int,
    git_commit: str,
    summary: dict[str, dict],
    deltas: dict[str, dict],
    out_dir: Path,
) -> None:
    metadata = {
        "experiment": "H3_GRPO_ablation",
        "hypothesis": "H3: each removed component lowers total_reward and quality_score",
        "conditions_run": conditions_for(args.task_type),
        "seed": args.seed,
        "pool_size": len(cve_pool),
        "cve_ids": cve_pool,
        "task_type": args.task_type,
        "difficulty": args.difficulty,
        "model_uri": model_uri,
        "num_variants_full": num_variants_full,
        "reward_threshold_production": 0.6,
        "reward_threshold_thesis": 0.90,
        "rub_per_input_token": args.rub_in,
        "rub_per_output_token": args.rub_out,
        "rub_per_selftest": args.rub_per_selftest,
        "selftest_cost_basis": (
            "Self-test runs in a Yandex Serverless Container billed by runtime, not "
            "tokens, and is not tracked in the DB. selftest_cost_rub = n_selftest_live "
            "* --rub-per-selftest (default 0 = excluded). Billing reference: "
            "19.2 core-hours = 80.82 RUB => ~4.21 RUB/core-hour; per-invocation RUB = "
            "cores x selftest_seconds/3600 x 4.21."
        ),
        "cost_note": (
            "cost_rub = token cost (+ selftest_cost_rub if --rub-per-selftest given). "
            "Token cost covers spec-generation inference only, summed over ALL variants "
            "in the batch (winners + losers). LLM-judge (review_variant) tokens are NOT "
            "persisted by the pipeline; judge inference cost is excluded rather than "
            "estimated. Token rates are user-supplied via CLI; production does NOT compute RUB."
        ),
        "no_self_test_note": (
            "no_self_test condition ablates the Yandex Serverless Container self-test "
            "(Playwright/Chromium harness in self_test/container/). "
            "Only meaningful when task_type=web_static_xss and AI_GEN_ENABLE_SELFTEST=true; "
            "for other task types full ≡ no_self_test (crypto/forensics use in-process solvers). "
            "When enabled=true, the self-test replaces the static XSS SOLVABILITY heuristic "
            "with an authoritative browser-execution verdict (executed + flag_reachable)."
        ),
        "confound_note": (
            "task_type and difficulty are held constant within a single run. "
            "REWARD_WEIGHTS differ by task_type (see reward.py). "
            "Results should not be compared across runs with different task_type."
        ),
        "stat_note": (
            "Summary CI: non-parametric bootstrap, 10 000 resamples, percentile method. "
            "Delta test: Wilcoxon signed-rank, two-sided, normal approximation with "
            "continuity correction (distribution-free; no normality assumption). "
            "Paired t-test was not used: scipy absent and normality unverified."
        ),
        "git_commit": git_commit,
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "summary": {
            cond: {k: (round(v, 6) if isinstance(v, float) else v) for k, v in s.items()}
            for cond, s in summary.items()
        },
        "deltas": {
            cond: {k: (round(v, 6) if isinstance(v, float) else v) for k, v in d.items()}
            for cond, d in deltas.items()
        },
    }
    path = out_dir / "run_metadata.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    logger.info("Saved %s", path)


# ═══════════════════════════════════════════════════════════════════════════════
# Argument parser
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "H₃ ablation experiment for the GRPO CTF generation pipeline. "
            "Measures causal contribution of RAG context, multi-candidate GRPO, and "
            "(web_static_xss only) the live browser self-test, over a fixed CVE pool."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Validate plumbing (2 CVEs, all conditions):\n"
            "  python -m experiments.ablation_h3 --dry-run\n\n"
            "  # Full run (80 CVEs):\n"
            "  python -m experiments.ablation_h3 --pool-size 80 --seed 1337\n\n"
            "  # Resume after crash (reads checkpoint from results_raw.csv):\n"
            "  python -m experiments.ablation_h3 --pool-size 80 --seed 1337\n\n"
            "  # Custom cost rates (defaults are deepseek-v4-flash: 0.0003 in / 0.0005 out):\n"
            "  python -m experiments.ablation_h3 --rub-in 0.0003 --rub-out 0.0005\n"
        ),
    )
    p.add_argument(
        "--pool-size", type=int, default=80, metavar="N",
        help="Number of CVEs to sample from kb_entries (default: 80)",
    )
    p.add_argument(
        "--seed", type=int, default=1337, metavar="SEED",
        help="Random seed for CVE pool sampling (default: 1337)",
    )
    p.add_argument(
        "--task-type",
        default="crypto_text_web",
        choices=["crypto_text_web", "forensics_image_metadata", "web_static_xss", "chat_llm"],
        help="Task type to generate — held constant across all conditions (default: crypto_text_web)",
    )
    p.add_argument(
        "--difficulty",
        default="medium",
        choices=["easy", "medium", "hard"],
        help="Difficulty level — held constant across all conditions (default: medium)",
    )
    p.add_argument(
        "--rub-in", type=float, default=0.0003, dest="rub_in", metavar="RATE",
        help="Cost rate: RUB per input token (default: 0.0003, deepseek-v4-flash). NOT from production.",
    )
    p.add_argument(
        "--rub-out", type=float, default=0.0005, dest="rub_out", metavar="RATE",
        help="Cost rate: RUB per output token (default: 0.0005, deepseek-v4-flash). NOT from production.",
    )
    p.add_argument(
        "--rub-per-selftest", type=float, default=0.0, dest="rub_per_selftest", metavar="RATE",
        help=(
            "Cost per live XSS self-test invocation in RUB (default: 0.0 = excluded). "
            "Serverless-Container compute is billed by runtime, not tokens, and is not "
            "tracked in the DB. Derive from billing: cores x selftest_seconds/3600 x "
            "(RUB/core-hour); reference rate ~4.21 RUB/core-hour (80.82 RUB / 19.2 core-h)."
        ),
    )
    p.add_argument(
        "--out-dir", default="experiments/results_h3", dest="out_dir", metavar="DIR",
        help="Output directory (default: experiments/results_h3)",
    )
    p.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Force pool_size=2 and run all conditions for the task type (validate plumbing)",
    )
    return p.parse_args()


# ═══════════════════════════════════════════════════════════════════════════════
# Self-test preflight (honest-or-stop for the no_self_test condition)
# ═══════════════════════════════════════════════════════════════════════════════

async def selftest_preflight(task_type: str, run_conditions: list[str]) -> None:
    """
    Guarantee the no_self_test ablation is REAL before spending hours of LLM calls.

    Only relevant when task_type=web_static_xss and no_self_test is being run.
    Two gates, both hard-exit on failure (so we never silently produce a vacuous
    full ≡ no_self_test result):
      1. Env: AI_GEN_ENABLE_SELFTEST=true AND AI_GEN_SELFTEST_URL set.
      2. Smoke test: one live call to the container must return is_live=True
         (proves connectivity + auth; verdict pass/fail is irrelevant here).
    """
    if task_type != SELFTEST_TASK_TYPE or "no_self_test" not in run_conditions:
        return

    if not (settings.AI_GEN_ENABLE_SELFTEST and settings.AI_GEN_SELFTEST_URL.strip()):
        logger.error(
            "no_self_test is VACUOUS: self-test not enabled in env. "
            "Set AI_GEN_ENABLE_SELFTEST=true and AI_GEN_SELFTEST_URL=<container-url> "
            "(and YANDEX_IAM_TOKEN or run on a VM with the metadata SA). "
            "Refusing to run — would silently make full ≡ no_self_test."
        )
        sys.exit(2)

    from app.services.ai_generator.self_test.xss_selftest import run_xss_self_test
    smoke_html = (
        "<!doctype html><html><body><div id=out></div>"
        "<script>document.getElementById('out').innerHTML="
        "new URLSearchParams(location.search).get('q');</script></body></html>"
    )
    smoke_spec = {
        "xss_type": "reflected",
        "vulnerable_param": "q",
        "payload_solution": "<img src=x onerror=alert(1)>",
        "flag": "CTF{SMOKE}",
    }
    logger.info("📡 Self-test preflight: pinging container at %s ...", settings.AI_GEN_SELFTEST_URL)
    try:
        res = await run_xss_self_test(smoke_html, smoke_spec)
    except Exception as exc:
        logger.error("💥 Self-test preflight crashed: %s — refusing to run.", exc)
        sys.exit(2)

    if not res.is_live:
        logger.error(
            "❌ Self-test preflight FAILED (fell back to static): %s — refusing to run. "
            "Fix container/auth before launching the XSS ablation.",
            res.detail,
        )
        sys.exit(2)

    logger.info(
        "✅ Self-test preflight OK: container LIVE (executed=%s flag_reachable=%s baseline_safe=%s)",
        res.executed, res.flag_reachable, res.baseline_safe,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

async def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "artifacts").mkdir(exist_ok=True)

    pool_size = 2 if args.dry_run else args.pool_size
    if args.dry_run:
        logger.info("🧪 ━━━ DRY-RUN MODE: pool_size forced to 2 ━━━")

    # ── CVE pool ──────────────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        cve_pool = await fetch_cve_pool(db, pool_size, args.seed)
    if not cve_pool:
        logger.error(
            "No eligible CVEs in kb_entries (need source='nvd', non-null cve_id and embedding). "
            "Run nvd_sync + backfill_embeddings first."
        )
        sys.exit(1)

    # ── Model URI (for metadata) ──────────────────────────────────────────────
    folder = settings.YANDEX_CLOUD_FOLDER.strip()
    model_uri = f"gpt://{folder}/{GENERATOR_MODEL_ID}/{GENERATOR_MODEL_VERSION}"
    num_variants_full = settings.AI_GEN_NUM_VARIANTS

    # ── Git commit ────────────────────────────────────────────────────────────
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).parent.parent,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        git_commit = "unknown"

    # ── Conditions for this task type (XSS gets no_self_test; others do not) ──
    run_conditions = conditions_for(args.task_type)

    logger.info(
        "⚙️ Experiment config: pool=%d seed=%d task_type=%s difficulty=%s "
        "num_variants_full=%d conditions=%s model=%s git=%s",
        len(cve_pool), args.seed, args.task_type, args.difficulty,
        num_variants_full, run_conditions, model_uri, git_commit[:8],
    )

    # ── Self-test preflight (hard-exits if no_self_test would be vacuous) ─────
    await selftest_preflight(args.task_type, run_conditions)

    # ── Checkpoint: load completed (cve, condition) pairs ────────────────────
    raw_csv_path = out_dir / "results_raw.csv"
    done_pairs: set[tuple[str, str]] = set()
    existing_rows: list[dict] = []
    if raw_csv_path.exists():
        with raw_csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                existing_rows.append(r)
                done_pairs.add((r["cve_id"], r["condition"]))
        if done_pairs:
            logger.info(
                "Checkpoint: %d / %d pairs already completed — skipping",
                len(done_pairs), len(cve_pool) * len(run_conditions),
            )

    # ── Open CSV for append ───────────────────────────────────────────────────
    write_header = not raw_csv_path.exists()
    csv_fh = raw_csv_path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
    if write_header:
        writer.writeheader()

    total_pairs = len(cve_pool) * len(run_conditions)
    completed = len(done_pairs)
    all_rows: list[dict] = list(existing_rows)

    # ── Main loop ─────────────────────────────────────────────────────────────
    try:
        for cve_id in cve_pool:
            for condition in run_conditions:
                if (cve_id, condition) in done_pairs:
                    logger.info("SKIP %s / %s (checkpoint)", cve_id, condition)
                    continue

                completed += 1
                cond_emoji = {
                    "full": "🟦", "no_rag": "🟨", "no_bon": "🟧", "no_self_test": "🟪",
                }.get(condition, "🔬")
                logger.info(
                    "%s ━━━ [%d/%d]  cve=%s  condition=%s ━━━",
                    cond_emoji, completed, total_pairs, cve_id, condition,
                )

                try:
                    row = await run_one_condition(
                        cve_id=cve_id,
                        condition=condition,
                        task_type=args.task_type,
                        difficulty=args.difficulty,
                        num_variants_full=num_variants_full,
                        rub_in=args.rub_in,
                        rub_out=args.rub_out,
                        rub_per_selftest=args.rub_per_selftest,
                        out_dir=out_dir,
                    )
                except Exception as exc:
                    logger.exception("FAILED cve=%s condition=%s: %s", cve_id, condition, exc)
                    row = {f: "" for f in CSV_FIELDS}
                    row["cve_id"] = cve_id
                    row["condition"] = condition
                    row["batch_status"] = f"error: {exc}"
                    row["total_reward"] = 0.0
                    row["quality_score"] = 0.0

                writer.writerow(row)
                csv_fh.flush()
                all_rows.append(row)

                st = str(row.get("batch_status", ""))
                passed = str(row.get("passed_all_binary")) == "1"
                if st == "completed":
                    st_emoji = "✅" if passed else "☑️"
                elif st == "failed":
                    st_emoji = "⚠️"
                else:
                    st_emoji = "💥"
                logger.info(
                    "  %s status=%-10s  📊 ES=%.4f  ⭐ q=%.4f  🚪 gates=%s  💰 %.2f₽  ⏱ %.0fs",
                    st_emoji, st,
                    float(row.get("total_reward") or 0),
                    float(row.get("quality_score") or 0),
                    "pass" if passed else "FAIL",
                    float(row.get("cost_rub") or 0),
                    float(row.get("wall_clock_s") or 0),
                )

    finally:
        csv_fh.close()

    # ── Statistics ────────────────────────────────────────────────────────────
    good_rows = [r for r in all_rows if r.get("total_reward") not in ("", None)]
    summary = compute_summary(good_rows)
    deltas = compute_deltas(good_rows)

    print_summary_table(summary)
    print_delta_table(deltas)
    save_summary_csv(summary, out_dir)
    save_metadata(
        args=args,
        cve_pool=cve_pool,
        model_uri=model_uri,
        num_variants_full=num_variants_full,
        git_commit=git_commit,
        summary=summary,
        deltas=deltas,
        out_dir=out_dir,
    )

    logger.info("🏁 ━━━ DONE ━━━")
    logger.info("  📄 %-28s  %d rows", "results_raw.csv", len(all_rows))
    logger.info("  📈 %-28s  per-condition stats", "results_summary.csv")
    logger.info("  🗂️ %-28s  seed, CVE list, model, stats", "run_metadata.json")
    logger.info("  📦 %-28s  full spec+artifact per (CVE, cond)", "artifacts/")

    if args.dry_run:
        logger.info("🧪✅ ━━━ DRY-RUN complete: pipeline plumbing validated ━━━")


if __name__ == "__main__":
    asyncio.run(main())
