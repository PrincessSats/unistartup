#!/usr/bin/env bash
#
# run_all.sh — launch the H₃ ablation across all task types.
#
# Each task type runs as its own process, writing to its own --out-dir with its
# own crash-resumable checkpoint. Same --seed makes every task type hit the SAME
# CVE pool (maximally controlled). Analyze per-type — never pool across types
# (REWARD_WEIGHTS differ).
#
# Concurrency (Yandex LLM quota ≈ 10 concurrent sessions):
#   Each run's gen+judge fan-out is capped to (quota / concurrent-runs) via the
#   exported AI_GEN_MAX_CONCURRENT_LLM, so concurrent runs never exceed the quota —
#   no throttling, no 429-retry waste.
#   default / --sequential — 1 run at a time (cap = quota; full speed)
#   --stagger              — 2 at a time (cap = quota/2 = 5; BOTH run at full speed)
#   --parallel             — all at once (cap = quota/ntypes; quota-safe but per-run slower)
#   --batch N              — N runs at a time
#   --quota Q              — override the session quota (default 10)
#
# Live progress:
#   Every mode STREAMS per-CVE completion lines to the terminal (full logs still
#   written). Sequential streams plain; batched/parallel prefixes each line with
#   [task_type] so concurrent runs stay readable. --no-follow silences it.
#
# Usage:
#   experiments/run_all.sh --clean              # sequential, pool 50, seed 1337
#   experiments/run_all.sh --clean --stagger    # 2 at a time
#   experiments/run_all.sh --clean --parallel   # all 4 (only if your quota is raised)
#   experiments/run_all.sh --pool-size 50 --seed 1337
#   experiments/run_all.sh --dry-run            # forwarded: 2 CVEs/type, smoke all 4
#   experiments/run_all.sh --types "crypto_text_web web_static_xss"
#
# Any unrecognised flag is forwarded verbatim to ablation_h3.py.
# Env overrides: POOL_SIZE, SEED, DIFFICULTY, RUB_PER_SELFTEST, PYTHON, TYPES.
#
set -uo pipefail

# ── Locate backend/ and the venv python ──────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"          # experiments/ lives under backend/
cd "$BACKEND_DIR"

PY="${PYTHON:-$BACKEND_DIR/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then
  echo "ERROR: venv python not found at '$PY'. Activate the venv or set PYTHON=..." >&2
  exit 1
fi

# ── Defaults (overridable via env or flags) ──────────────────────────────────
POOL_SIZE="${POOL_SIZE:-50}"
SEED="${SEED:-1337}"
DIFFICULTY="${DIFFICULTY:-medium}"
RUB_PER_SELFTEST="${RUB_PER_SELFTEST:-0.0}"
TYPES="${TYPES:-crypto_text_web forensics_image_metadata chat_llm web_static_xss}"
# Concurrency = how many task-type runs at once. Yandex LLM quota is 10 concurrent
# sessions; each run uses up to AI_GEN_NUM_VARIANTS (≈5). So BATCH=1 (sequential,
# ≈5 concurrent) is SAFE; BATCH=2 (≈10) sits at the limit; more WILL throttle.
# Default is sequential for that reason.
BATCH="${BATCH:-1}"
QUOTA="${QUOTA:-10}"       # Yandex concurrent LLM-session quota (allowed in-flight)
CLEAN=0
FOLLOW="${FOLLOW:-auto}"   # auto = stream live when sequential (BATCH=1); 1=force, 0=off
EXTRA_ARGS=()

usage() { sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^#\{1,\} \{0,1\}//'; }

# ── Parse flags ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sequential)       BATCH=1; shift;;
    --stagger)          BATCH=2; shift;;
    --parallel)         BATCH=0; shift;;            # 0 → all at once
    --batch)            BATCH="$2"; shift 2;;
    --quota)            QUOTA="$2"; shift 2;;        # concurrent LLM-session quota (default 10)
    --follow)           FOLLOW=1; shift;;           # stream per-CVE progress to terminal
    --no-follow)        FOLLOW=0; shift;;           # logs only (quiet)
    --clean)            CLEAN=1; shift;;
    --pool-size)        POOL_SIZE="$2"; shift 2;;
    --seed)             SEED="$2"; shift 2;;
    --difficulty)       DIFFICULTY="$2"; shift 2;;
    --rub-per-selftest) RUB_PER_SELFTEST="$2"; shift 2;;
    --types)            TYPES="$2"; shift 2;;
    -h|--help)          usage; exit 0;;
    *)                  EXTRA_ARGS+=("$1"); shift;;   # forward to ablation_h3.py
  esac
done

read -r -a TASK_TYPES <<< "$TYPES"
# Resolve BATCH: 0 or >ntypes means "all at once".
if [[ $BATCH -le 0 || $BATCH -gt ${#TASK_TYPES[@]} ]]; then BATCH=${#TASK_TYPES[@]}; fi

# Per-process LLM cap so (cap × concurrent runs) ≤ quota → no throttling.
# Exported so each child run_pipeline bounds its own gen+judge fan-out.
# Sequential (BATCH=1): cap = quota (a single 5-variant run never nears it).
# Stagger (BATCH=2):    cap = quota/2 = 5 → both runs at FULL speed, total ≤ quota.
CAP=$(( QUOTA / BATCH )); [[ $CAP -lt 1 ]] && CAP=1
export AI_GEN_MAX_CONCURRENT_LLM="$CAP"
# Resolve FOLLOW: stream live by default in every mode. Sequential streams cleanly;
# batched/parallel streams with a [task_type] prefix so interleaved lines stay readable.
if [[ "$FOLLOW" == "auto" ]]; then FOLLOW=1; fi

out_dir_for() { echo "experiments/results_h3_${1}"; }
log_for()     { echo "experiments/run_${1}.log"; }

# ── Forward Ctrl-C / TERM to all child runs ──────────────────────────────────
trap 'echo; echo "Interrupted — killing runs..."; kill $(jobs -p) 2>/dev/null; exit 130' INT TERM

# ── Launch one task type in the background. Runs in the CURRENT shell (functions
#    do not subshell), so the caller can read its PID via $! immediately after.
#    Do NOT wrap a call to this in $(...) — that would fork a subshell and the
#    background job would no longer be a child of the main shell (wait fails).
# Build + run the python invocation for one task type (foreground; writes to caller's stdout).
pyrun() {
  local t="$1" out="$2"
  "$PY" -m experiments.ablation_h3 \
    --pool-size "$POOL_SIZE" --seed "$SEED" --difficulty "$DIFFICULTY" \
    --task-type "$t" --out-dir "$out" --rub-per-selftest "$RUB_PER_SELFTEST" \
    ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
}

# Background launch → log file (used by parallel / batched / stagger modes).
launch() {
  local t="$1" out log
  out="$(out_dir_for "$t")"; log="$(log_for "$t")"
  if [[ $CLEAN -eq 1 ]]; then rm -rf "$out"; fi
  mkdir -p "$out"
  echo "🚀 [launch] $t  → $out  (log: $log)" >&2
  pyrun "$t" "$out" > "$log" 2>&1 &
}

echo "════════════════════════════════════════════════════════════════════"
echo " H₃ ablation launcher"
echo "   python      : $PY"
echo "   task types  : ${TASK_TYPES[*]}"
echo "   pool-size   : $POOL_SIZE   seed: $SEED   difficulty: $DIFFICULTY"
echo "   rub/selftest: $RUB_PER_SELFTEST"
echo "   clean       : $([[ $CLEAN -eq 1 ]] && echo yes || echo no)"
if [[ $BATCH -eq 1 ]]; then mode="SEQUENTIAL (1 at a time)";
elif [[ $BATCH -ge ${#TASK_TYPES[@]} ]]; then mode="ALL PARALLEL ($BATCH at once, capped to quota)";
else mode="BATCHED ($BATCH at a time, capped to quota)"; fi
echo "   concurrency : $mode"
echo "   LLM quota   : $QUOTA  →  cap $CAP in-flight/run  ($BATCH run(s) × $CAP = $((BATCH*CAP)) ≤ $QUOTA)"
[[ ${#EXTRA_ARGS[@]} -gt 0 ]] && echo "   forwarded   : ${EXTRA_ARGS[*]}"
echo "════════════════════════════════════════════════════════════════════"

overall_fail=0   # any run exited non-zero
overall_warn=0   # any run completed but throttled / had failed rows
res_types=()     # parallel arrays: per-run final classification for the summary
res_codes=()     # 0=ok  1=warn  2=fail

# Throttle/rate-limit markers the Yandex LLM API / pipeline emit into the log.
THROTTLE_RE='429|too many requests|rate.?limit|throttl|quota|resourceexhausted|temporarily unavailable|503'

# Classify one finished run and print a bright status line.
record() {
  local t="$1" ec="$2"
  local log out csv; log="$(log_for "$t")"; out="$(out_dir_for "$t")"; csv="$out/results_raw.csv"

  if [[ "$ec" -ne 0 ]]; then
    echo "❌ 🔴 FAIL   $t   (exit $ec)   → $log"
    overall_fail=1; res_types+=("$t"); res_codes+=(2); return
  fi

  local throttled=0 errored=0 why=""
  grep -qiE "$THROTTLE_RE" "$log" 2>/dev/null && throttled=1
  # batch_status column holds "failed" or "error: ..." on per-CVE failures (exit still 0)
  [[ -f "$csv" ]] && grep -qiE '(^|,)(error[:_ ]|failed)' "$csv" 2>/dev/null && errored=1

  if [[ $throttled -eq 1 || $errored -eq 1 ]]; then
    [[ $throttled -eq 1 ]] && why="throttling detected"
    [[ $errored -eq 1 ]] && why="${why:+$why & }failed rows in CSV"
    echo "⚠️ 🟡 WARN   $t   — completed, $why   → $log"
    overall_warn=1; res_types+=("$t"); res_codes+=(1); return
  fi

  echo "✅ 🟢 OK     $t"
  res_types+=("$t"); res_codes+=(0)
}

# Per-CVE progress lines worth streaming live (ablation_h3's own log lines).
FOLLOW_RE='ablation_h3|━━━|preflight'

if [[ $BATCH -eq 1 ]]; then
  # ── SEQUENTIAL (one type at a time). With FOLLOW, run in the FOREGROUND through
  #    tee so per-CVE progress streams to the terminal AND the full log is written;
  #    python's exit code (masked by the pipe) is recovered via a tiny rc file.
  #    No tail, no orphan processes. ───────────────────────────────────────────
  for t in "${TASK_TYPES[@]}"; do
    out="$(out_dir_for "$t")"; log="$(log_for "$t")"
    if [[ $CLEAN -eq 1 ]]; then rm -rf "$out"; fi
    mkdir -p "$out"
    echo "════════════════════════════════════════════════════════════════════"
    echo "▶ $t   (full log: $log)"
    if [[ "$FOLLOW" == "1" ]]; then
      rc="$out/.exit_rc"; rm -f "$rc"
      { pyrun "$t" "$out"; echo "$?" > "$rc"; } 2>&1 | tee "$log" | grep --line-buffered -E "$FOLLOW_RE"
      ec="$(<"$rc")"; rm -f "$rc"; [[ -z "$ec" ]] && ec=1
    else
      pyrun "$t" "$out" > "$log" 2>&1; ec=$?
    fi
    record "$t" "$ec"
  done
else
  # ── Batched/parallel: background launches → log files, classify on completion.
  #    When FOLLOW=1, also stream each running log to the terminal with a
  #    [task_type] prefix so the interleaved batch stays readable. Streamers are
  #    subshells torn down by killing the subshell AND its pipeline children
  #    (pkill -P) — no orphan tail/grep left behind. ──────────────────────────
  i=0
  while [[ $i -lt ${#TASK_TYPES[@]} ]]; do
    btypes=(); bpids=(); spids=()
    for ((j=0; j<BATCH && i<${#TASK_TYPES[@]}; j++, i++)); do
      launch "${TASK_TYPES[$i]}"; bpids+=("$!"); btypes+=("${TASK_TYPES[$i]}")
    done
    if [[ "$FOLLOW" == "1" ]]; then
      echo "▶ streaming: ${btypes[*]}   (prefixed; full logs: experiments/run_*.log)"
      for t in "${btypes[@]}"; do
        log="$(log_for "$t")"
        ( tail -n +1 -f "$log" 2>/dev/null \
            | grep --line-buffered -E "$FOLLOW_RE" \
            | awk -v p="[$t] " '{print p $0; fflush()}' ) &
        spids+=("$!")
      done
    else
      echo "⏳ [wait] ${btypes[*]}    (tail -f experiments/run_*.log)"
    fi
    for k in "${!bpids[@]}"; do
      if wait "${bpids[$k]}"; then ec=0; else ec=$?; fi
      record "${btypes[$k]}" "$ec"
    done
    # Tear down this batch's streamers. Order matters: kill the pipeline children
    # (pkill -P) BEFORE the subshell, else they reparent to init and survive.
    # Also kill the tail directly by its unique log arg — that closes grep/awk by
    # EOF cascade — as a belt-and-suspenders against any shell's pipeline model.
    for k in "${!spids[@]}"; do
      sp="${spids[$k]}"; t="${btypes[$k]}"
      pkill -P "$sp" 2>/dev/null
      kill "$sp" 2>/dev/null
      pkill -f "tail -n .* experiments/run_${t}\.log" 2>/dev/null
      wait "$sp" 2>/dev/null
    done
  done
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════════════════════"
echo " SUMMARY"
for idx in "${!res_types[@]}"; do
  case "${res_codes[$idx]}" in
    0) echo "   ✅ 🟢 ${res_types[$idx]}";;
    1) echo "   ⚠️ 🟡 ${res_types[$idx]}   (throttled / failed rows — check log)";;
    2) echo "   ❌ 🔴 ${res_types[$idx]}   (run failed — check log)";;
  esac
done
echo "────────────────────────────────────────────────────────────────────"
if [[ $overall_fail -eq 1 ]]; then
  echo " ❌ 🔴 ONE OR MORE RUNS FAILED — inspect experiments/run_*.log"
elif [[ $overall_warn -eq 1 ]]; then
  echo " ⚠️ 🟡 ALL COMPLETED, but with throttling / failed rows — inspect logs"
else
  echo " ✅ 🟢 ALL RUNS CLEAN"
fi
echo " Outputs: experiments/results_h3_<task_type>/{results_raw,results_summary}.csv, run_metadata.json, artifacts/"
echo "════════════════════════════════════════════════════════════════════"

# ── Auto-aggregate the runs from THIS invocation (best-effort) ────────────────
if [[ ${#res_types[@]} -gt 0 ]]; then
  echo
  echo "📊 Aggregating combined results ..."
  agg_dirs=()
  for t in "${res_types[@]}"; do agg_dirs+=("$(out_dir_for "$t")"); done
  "$PY" -m experiments.aggregate --dirs "${agg_dirs[@]}" \
    --out-dir experiments/results_h3_combined \
    || echo "⚠️ 🟡 aggregate step failed (runs are fine — run 'python -m experiments.aggregate' manually)"
fi

exit $overall_fail
