#!/usr/bin/env python
"""
aggregate.py — combine per-task-type H₃ ablation results into one place.

Each `ablation_h3.py` run writes its own directory:
    experiments/results_h3_<task_type>/
        results_raw.csv        (one row per CVE×condition)
        results_summary.csv    (per-condition stats, already computed)
        run_metadata.json      (seed, cve list, AND the computed deltas)

This script does NOT recompute anything — it concatenates the already-computed
outputs and tags every row with its `task_type` (read authoritatively from each
run's run_metadata.json). Pure stdlib; no DB / .env / LLM needed.

IMPORTANT: reward metrics are NEVER pooled across task types — REWARD_WEIGHTS
differ by type (see reward.py), so a mean over mixed types is meaningless. The
combined summary and deltas stay keyed by (task_type, condition/ablation). The
combined raw CSV is a tagged concatenation for plotting / archival only.

Outputs (in --out-dir, default experiments/results_h3_combined/):
    combined_raw.csv       all raw rows, with a leading task_type column
    combined_summary.csv   all per-(task_type,condition) summary rows
    combined_deltas.csv    all per-(task_type,ablation,metric) deltas
    combined_metadata.json roll-up of each run's metadata (seed, git, cve count…)
Plus printed master tables: per-type summary, and a cross-type delta matrix
that answers "does each component's effect replicate across task types?".

Usage:
    cd backend/
    python -m experiments.aggregate                       # scans experiments/results_h3_*
    python -m experiments.aggregate --base-dir experiments --glob 'results_h3_*'
    python -m experiments.aggregate --dirs experiments/results_h3_crypto_text_web ...
    python -m experiments.aggregate --out-dir experiments/thesis_combined
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Optional

CONDITION_ORDER = ["full", "no_rag", "no_bon", "no_self_test"]
ABLATION_ORDER = ["no_rag", "no_bon", "no_self_test"]
ABLATION_LABEL = {
    "no_rag": "RAG context",
    "no_bon": "GRPO multi-candidate",
    "no_self_test": "XSS browser self-test",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Discovery
# ═══════════════════════════════════════════════════════════════════════════════

def discover_run_dirs(base_dir: Path, glob: str, explicit: Optional[list[str]]) -> list[Path]:
    """Return run directories that contain a run_metadata.json, sorted by name."""
    if explicit:
        dirs = [Path(d) for d in explicit]
    else:
        dirs = sorted(base_dir.glob(glob))
    out: list[Path] = []
    for d in dirs:
        if not d.is_dir():
            continue
        if d.name.endswith("_combined"):  # never re-ingest our own output
            continue
        if (d / "run_metadata.json").exists():
            out.append(d)
        else:
            print(f"  skip {d} (no run_metadata.json)")
    return out


def _read_metadata(run_dir: Path) -> dict[str, Any]:
    with (run_dir / "run_metadata.json").open(encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ═══════════════════════════════════════════════════════════════════════════════
# Aggregation
# ═══════════════════════════════════════════════════════════════════════════════

def aggregate(run_dirs: list[Path], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_rows: list[dict[str, Any]] = []
    raw_fields: list[str] = []
    summary_rows: list[dict[str, Any]] = []
    summary_fields: list[str] = []
    delta_rows: list[dict[str, Any]] = []
    meta_rollup: dict[str, Any] = {}

    for run_dir in run_dirs:
        meta = _read_metadata(run_dir)
        task_type = meta.get("task_type", run_dir.name)
        print(f"  + {task_type:<26} ← {run_dir}")

        # roll-up of per-run metadata
        meta_rollup[task_type] = {
            "dir": str(run_dir),
            "seed": meta.get("seed"),
            "pool_size": meta.get("pool_size"),
            "n_cves": len(meta.get("cve_ids", [])),
            "model_uri": meta.get("model_uri"),
            "num_variants_full": meta.get("num_variants_full"),
            "git_commit": meta.get("git_commit"),
            "date_utc": meta.get("date_utc"),
            "conditions_run": meta.get("conditions_run"),
            "dry_run": meta.get("dry_run"),
        }

        # raw rows (tag task_type as the leading column)
        for r in _read_csv(run_dir / "results_raw.csv"):
            row = {"task_type": task_type, **r}
            raw_rows.append(row)
            for k in row:
                if k not in raw_fields:
                    raw_fields.append(k)

        # summary rows (already computed per condition)
        for r in _read_csv(run_dir / "results_summary.csv"):
            row = {"task_type": task_type, **r}
            summary_rows.append(row)
            for k in row:
                if k not in summary_fields:
                    summary_fields.append(k)

        # deltas (flatten metadata["deltas"][ablation] into one row per metric)
        for ablation, d in (meta.get("deltas") or {}).items():
            for metric in ("total_reward", "quality_score"):
                delta_rows.append({
                    "task_type": task_type,
                    "ablation": ablation,
                    "metric": metric,
                    "mean_diff": d.get(f"mean_diff_{metric}"),
                    "ci95_lo": d.get(f"diff_ci95_lo_{metric}"),
                    "ci95_hi": d.get(f"diff_ci95_hi_{metric}"),
                    "wilcoxon_p": d.get(f"wilcoxon_p_{metric}"),
                    "n_pairs": d.get(f"n_pairs_{metric}"),
                })

    # ── Write combined CSVs ───────────────────────────────────────────────────
    _write_csv(out_dir / "combined_raw.csv", raw_rows, raw_fields)
    _write_csv(out_dir / "combined_summary.csv", summary_rows, summary_fields)
    _write_csv(
        out_dir / "combined_deltas.csv", delta_rows,
        ["task_type", "ablation", "metric", "mean_diff", "ci95_lo", "ci95_hi", "wilcoxon_p", "n_pairs"],
    )
    with (out_dir / "combined_metadata.json").open("w", encoding="utf-8") as f:
        json.dump(meta_rollup, f, ensure_ascii=False, indent=2)

    print(f"\nWrote → {out_dir}/")
    print(f"  combined_raw.csv      ({len(raw_rows)} rows)")
    print(f"  combined_summary.csv  ({len(summary_rows)} rows)")
    print(f"  combined_deltas.csv   ({len(delta_rows)} rows)")
    print(f"  combined_metadata.json")

    # ── Printed master tables ─────────────────────────────────────────────────
    print_summary_matrix(summary_rows)
    print_delta_matrix(delta_rows)


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# Printed tables
# ═══════════════════════════════════════════════════════════════════════════════

def _f(v: Any, dec: int = 4) -> str:
    try:
        x = float(v)
        if math.isnan(x):
            return "  NaN"
        return f"{x:.{dec}f}"
    except (TypeError, ValueError):
        return str(v) if v not in (None, "") else "—"


def _pct(v: Any) -> str:
    try:
        return f"{float(v) * 100:.0f}%"
    except (TypeError, ValueError):
        return "—"


def print_summary_matrix(summary_rows: list[dict]) -> None:
    by_type: dict[str, list[dict]] = {}
    for r in summary_rows:
        by_type.setdefault(r["task_type"], []).append(r)

    print("\n" + "═" * 100)
    print(" PER-TYPE SUMMARY (stats as computed by each run; NOT pooled across types)")
    print("═" * 100)
    hdr = f"{'task_type':<26}{'condition':<14}{'totalR μ':>10}{'  95% CI':>18}{'qual μ':>9}{'≥0.90':>7}{'pass':>7}{'RUB':>9}"
    for ttype in sorted(by_type):
        print(f"\n{ttype}")
        print(hdr)
        print(" " * 26 + "─" * 74)
        rows = {r["condition"]: r for r in by_type[ttype]}
        for cond in CONDITION_ORDER:
            if cond not in rows:
                continue
            s = rows[cond]
            ci = f"[{_f(s.get('total_reward_ci95_lo'),3)},{_f(s.get('total_reward_ci95_hi'),3)}]"
            print(
                f"{'':<26}{cond:<14}"
                f"{_f(s.get('total_reward_mean')):>10}"
                f"{ci:>18}"
                f"{_f(s.get('quality_score_mean'),3):>9}"
                f"{_pct(s.get('pub_ge_090_rate')):>7}"
                f"{_pct(s.get('pass_rate')):>7}"
                f"{_f(s.get('mean_cost_rub'),2):>9}"
            )


def print_delta_matrix(delta_rows: list[dict]) -> None:
    """Cross-type matrix: does each component's contribution replicate?"""
    # index: (ablation, metric, task_type) -> row
    idx: dict[tuple, dict] = {
        (r["ablation"], r["metric"], r["task_type"]): r for r in delta_rows
    }
    task_types = sorted({r["task_type"] for r in delta_rows})

    print("\n" + "═" * 100)
    print(" COMPONENT CONTRIBUTION ACROSS TASK TYPES  (Δ = mean[full − ablated], per type)")
    print(" + = component helps · CI excludes 0 → robust · '*'/'**' Wilcoxon p<0.05/0.01")
    print("═" * 100)

    for metric in ("total_reward", "quality_score"):
        print(f"\n metric: {metric}")
        print(f"  {'component (ablation)':<26}" + "".join(f"{t.split('_')[0][:10]:>12}" for t in task_types))
        print("  " + "─" * (26 + 12 * len(task_types)))
        for ablation in ABLATION_ORDER:
            cells = []
            for t in task_types:
                r = idx.get((ablation, metric, t))
                # Treat missing / NaN / zero-pair deltas as "did not run" (—).
                d = r.get("mean_diff") if r else None
                n = r.get("n_pairs") if r else None
                is_empty = d is None or d == "" or str(d).lower() == "nan"
                try:
                    is_empty = is_empty or math.isnan(float(d)) or int(float(n)) == 0
                except (TypeError, ValueError):
                    pass
                if is_empty:
                    cells.append(f"{'—':>12}")
                    continue
                try:
                    p = float(r.get("wilcoxon_p"))
                    sig = "**" if p < 0.01 else ("*" if p < 0.05 else "")
                except (TypeError, ValueError):
                    sig = ""
                cells.append(f"{_f(d, 3)+sig:>12}")
            label = ABLATION_LABEL.get(ablation, ablation)
            print(f"  {label:<26}" + "".join(cells))

    print("\n  Read across a row: if Δ stays positive across types, that component's")
    print("  contribution replicates. A type showing '—' did not run that ablation")
    print("  (no_self_test is web_static_xss only).")
    print("═" * 100)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Aggregate per-task-type H₃ ablation results (no recomputation; no DB).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--base-dir", default="experiments", help="Where to scan (default: experiments)")
    p.add_argument("--glob", default="results_h3_*", help="Glob for run dirs (default: results_h3_*)")
    p.add_argument("--dirs", nargs="*", default=None, help="Explicit run dirs (overrides --glob)")
    p.add_argument("--out-dir", default="experiments/results_h3_combined", help="Output directory")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    base = Path(args.base_dir)
    print(f"Scanning {base}/{args.glob} ..." if not args.dirs else f"Using {len(args.dirs)} explicit dirs ...")
    run_dirs = discover_run_dirs(base, args.glob, args.dirs)
    if not run_dirs:
        print("No run directories with run_metadata.json found. Nothing to aggregate.")
        return 1
    aggregate(run_dirs, Path(args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
