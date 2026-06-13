# H₃ Ablation Experiment — README

## What This Is

A research harness for **thesis hypothesis H₃**: each component of the GRPO CTF-task
generation pipeline makes a measurable, positive contribution to task quality.

The experiment runs four paired conditions over a fixed, randomly-sampled pool of CVEs.
By keeping the CVE fixed across conditions (within-subject/paired design), the deltas
between conditions are causally attributable to the removed component rather than
to variation in the input CVEs.

---

## Background: What the Pipeline Actually Does

> **Read this before interpreting results.** The pipeline is not "Best-of-N" in the
> classical sense — it is GRPO-inspired.

The production pipeline (`backend/app/services/ai_generator/pipeline.py`) does the
following per generation request:

1. **RAG context retrieval** — `rag_context.py` performs a two-stage pgvector cosine
   search over `kb_entries` to find semantically relevant CVE records. The retrieved
   context (CVE descriptions, CWE tags, CVSS scores) is injected verbatim into the
   LLM system prompt.

2. **Fan-out spec generation** — N=`AI_GEN_NUM_VARIANTS` (default 5) task specs are
   generated in parallel with temperature-laddered sampling
   (`base_temp + i * temp_step`).

3. **Artifact creation** — each spec is turned into a concrete artifact
   (cipher text, image, XSS page, etc.) by `artifact_creator.py`.

4. **Binary gate validation** — four binary checks (0 or 1) per variant:
   - `FORMAT` — spec structure, required fields present
   - `FUNCTIONAL` — artifact can be created without errors
   - `SOLVABILITY` — flag is recoverable (in-process solver for crypto/forensics;
     Playwright/Chromium self-test via Yandex Serverless Container for `web_static_xss`)
   - `NON_TRIVIALITY` — spec is not trivially easy or plagiarised

   For `web_static_xss`: when `AI_GEN_ENABLE_SELFTEST=true`, the SOLVABILITY gate
   is replaced by a live browser execution — a Yandex Serverless Container
   (`self_test/container/`) that injects the `payload_solution` into the rendered
   HTML page and confirms JS fires and the flag is reachable in `document.cookie`.
   Falls back to the static keyword heuristic if the container is unavailable.

5. **LLM-as-judge quality scoring** — only for variants that passed all 4 binary
   gates. `reviewer.py` sends the spec to an LLM judge that scores 5 dimensions:
   `educational_value`, `scenario_realism`, `hint_quality`, `writeup_clarity`,
   `difficulty_calibration`. Mean of these 5 scores = `quality_score` (0–1).

6. **GRPO advantage computation** — `advantage_i = (reward_i − mean) / std` over
   all variants in the batch. Also computed: soft rewards `RAG_GROUNDING` and
   `CVE_RELEVANCE` (0–1, not binary gates).

7. **Selection** — variant with the highest advantage among those that passed all
   binary gates is selected, provided `total_reward >= AI_GEN_MIN_REWARD_THRESHOLD`
   (default 0.6). If none qualify, the batch is retried up to `AI_GEN_MAX_RETRIES`.

---

## Conditions

| Condition | N variants | RAG injected | Self-test | Description |
|-----------|-----------|--------------|-----------|-------------|
| `full`         | 5 (default) | Yes | Yes | Production pipeline, unmodified |
| `no_rag`       | 5 (default) | **No** | Yes | RAG context omitted from LLM prompt |
| `no_bon`       | **1** | Yes | Yes | Single candidate; no GRPO ranking |
| `no_self_test` | 5 (default) | Yes | **No** | XSS browser self-test disabled; static heuristic only (web_static_xss only) |

`num_variants_full` is read live from `settings.AI_GEN_NUM_VARIANTS` at runtime —
not hardcoded. If the setting changes, the experiment reflects the new production N.

The `no_rag` condition uses `inject_rag=False`. The `no_self_test` condition uses
`enable_self_test=False`. Both parameters were added to `run_pipeline`; production
callers always use the defaults and are unaffected.

**Note on `no_self_test` scope:** this condition only produces a measurable delta
when `--task-type=web_static_xss` and `AI_GEN_ENABLE_SELFTEST=true` in the
environment. For other task types (crypto/forensics/chat_llm) `full ≡ no_self_test`
because those types use in-process solvers regardless.

---

## Quality Metrics ("ES" proxies)

The thesis brief used "ES metric" which does not exist by that name. Two scalars
are recorded per (CVE, condition) and both are used for CI and delta testing:

| Column | What it measures |
|--------|-----------------|
| `total_reward` | Weighted mean of ALL reward checks (binary gates + QUALITY soft rewards). This is the production selection signal. Threshold ≥ 0.6 = "published" in production. |
| `quality_score` | LLM-judge mean of 5 dimensions. Available only when the variant passed all 4 binary gates (otherwise the judge is skipped and the value is 0). |

Both metrics are used in the delta/causal analysis.

---

## Prerequisites

1. **Python environment**: the backend virtual environment must be activated.
   ```bash
   cd backend/
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   ```

2. **Database running**: PostgreSQL on port 6432 (PgBouncer) must be up and have
   the `kb_entries` table populated with NVD CVE records.
   - Check: `psql -h localhost -p 6432 -d <DB_NAME> -c "SELECT count(*) FROM kb_entries WHERE source='nvd' AND embedding IS NOT NULL;"`
   - If count is low, run: `python -m app.scripts.backfill_embeddings`
   - If no CVEs at all, run NVD sync first (see `nvd_sync.py`).

3. **`.env` file**: must have valid credentials:
   - `YANDEX_CLOUD_API_KEY` / `YANDEX_CLOUD_FOLDER` — for LLM inference
   - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` — database
   - `AI_GEN_NUM_VARIANTS` (optional; default 5)
   - `AI_GEN_MIN_REWARD_THRESHOLD` (optional; default 0.6)
   - `AI_GEN_REQUIRE_RAG` — must be set to `false` OR left True; the `no_rag`
     condition bypasses this check entirely via `inject_rag=False`.

4. **Self-test env (web_static_xss ONLY)**: the `no_self_test` condition is real
   only for XSS, and only when the Serverless Container is reachable. The required
   settings are already loaded from `backend/.env` (config.py reads it via
   pydantic-settings) — no manual `export` needed:
   - `AI_GEN_ENABLE_SELFTEST=true`
   - `AI_GEN_SELFTEST_URL=<serverless-container-url>`
   - `AI_GEN_SELFTEST_TIMEOUT_S` (optional; default 20)

   Only `YANDEX_IAM_TOKEN` is NOT in `.env`. Export it ONLY if the container
   requires IAM auth (skip if the container has public access). On a Yandex VM the
   metadata service provides it automatically. The script's **preflight smoke-test**
   hard-exits (code 2) if the container is not live, so an auth problem surfaces
   immediately rather than producing a vacuous `full ≡ no_self_test`.
   For crypto/forensics/chat these vars are irrelevant (those types run 3 conditions).

5. **Disk space**: each (CVE, condition) pair writes a JSON artifact to
   `<out_dir>/artifacts/`. ~50 KB each → ~12 MB for 50 CVEs × 3 conditions.

---

## Running the Experiment

### Conditions are task-type-aware

`conditions_for(task_type)` decides what runs:
- `web_static_xss` → **4** conditions (`full`, `no_rag`, `no_bon`, `no_self_test`)
- everything else → **3** conditions (no_self_test is inert → skipped, saves calls)

### Step 1 — Dry run (ALWAYS do this first)

Non-XSS plumbing check (3 conditions, 6 calls):
```bash
cd backend/
python -m experiments.ablation_h3 --dry-run --task-type crypto_text_web
```

XSS plumbing + self-test check (4 conditions, 8 calls) — exercises the live container.
Self-test config comes from `backend/.env`; only export `YANDEX_IAM_TOKEN` if the
container requires IAM auth:
```bash
cd backend/
# export YANDEX_IAM_TOKEN=<iam-token>   # only if container needs auth
python -m experiments.ablation_h3 --dry-run --task-type web_static_xss \
  --out-dir experiments/results_h3_xss
```

Check (XSS dry-run — this is the proof the ablation is real):
- Preflight logs `Self-test preflight OK: container LIVE`
- `results_raw.csv` has 8 rows; `artifacts/` has 8 JSON files
- For `full`/`no_rag`/`no_bon` rows: `solvability_source` = `live_pass`/`live_fail`,
  `xss_selftest_live=1`
- For `no_self_test` rows: `solvability_source=static`, `xss_selftest_live=0`
- `run_metadata.json` valid; summary prints without NaN in `total_reward_mean`

If the preflight hard-exits (code 2), the container/auth isn't reachable — fix it
before spending hours of LLM calls.

### Step 2 — Full run (4 separate runs, pool 50, same seed)

Same `--seed 1337` makes all four task types hit the **same 50 CVEs** (maximally
controlled). Each run is independent and crash-resumable. Analyze per-type — never
pool rewards across types (`REWARD_WEIGHTS` differ).

```bash
cd backend/

# 3 conditions each (~150 calls/run):
python -m experiments.ablation_h3 --pool-size 50 --seed 1337 \
  --task-type crypto_text_web          --out-dir experiments/results_h3_crypto
python -m experiments.ablation_h3 --pool-size 50 --seed 1337 \
  --task-type forensics_image_metadata --out-dir experiments/results_h3_forensics
python -m experiments.ablation_h3 --pool-size 50 --seed 1337 \
  --task-type chat_llm                 --out-dir experiments/results_h3_chat

# 4 conditions (~200 calls) — self-test config from backend/.env:
# export YANDEX_IAM_TOKEN=<iam-token>   # only if container needs auth
python -m experiments.ablation_h3 --pool-size 50 --seed 1337 \
  --task-type web_static_xss --out-dir experiments/results_h3_xss \
  --rub-per-selftest 0.0   # optional: cores×sec/3600×4.21 if you want self-test compute in cost
```

Budget: ~650 pipeline calls total; each 30–120 s → plan for several hours.
Each pipeline call typically takes 30–120 seconds depending on LLM latency and N.

#### Optional: custom cost rates

Defaults are deepseek-v4-flash pricing: **0.0003 RUB/input-token, 0.0005 RUB/output-token**.
Override only if the rates change:
```bash
python -m experiments.ablation_h3 --pool-size 50 --seed 1337 \
  --rub-in 0.0003 --rub-out 0.0005
```

### Step 3 — Resume after a crash

Re-run the **same command verbatim** (same `--out-dir`). The script reads
`results_raw.csv` at startup, identifies completed `(cve_id, condition)` pairs, and
skips them.

```bash
# Crash at CVE 30 → re-run identical command → continues from CVE 30
python -m experiments.ablation_h3 --pool-size 50 --seed 1337 \
  --task-type web_static_xss --out-dir experiments/results_h3_xss
```

After resume the summary and deltas are recomputed from ALL rows (including the
ones from the previous run), so the final statistics are always over the full pool.

---

## Output Files

All outputs go to `--out-dir` (default `experiments/results_h3/`).

```
experiments/results_h3/
├── results_raw.csv          ← one row per (CVE, condition); the primary dataset
├── results_summary.csv      ← per-condition aggregate statistics
├── run_metadata.json        ← seed, CVE list, model URI, stat notes, results summary
└── artifacts/
    ├── CVE-2024-1234__full.json
    ├── CVE-2024-1234__no_rag.json
    ├── CVE-2024-1234__no_bon.json
    └── ...                  ← one JSON per (CVE, condition)
```

### `results_raw.csv` — column reference

| Column | Type | Description |
|--------|------|-------------|
| `cve_id` | str | CVE identifier (e.g. `CVE-2024-12345`) |
| `condition` | str | `full` / `no_rag` / `no_bon` / `no_self_test` |
| `batch_id` | UUID | DB batch UUID; use to inspect variants in `ai_generation_batches` |
| `batch_status` | str | `completed` / `failed` / `error: …` |
| `total_reward` | float | Weighted mean of all reward checks (0–1). Production signal. |
| `quality_score` | float | LLM-judge mean (0–1); 0 if binary gates failed (judge skipped). |
| `gate_FORMAT` | 0/1 | Binary gate: spec has required fields |
| `gate_FUNCTIONAL` | 0/1 | Binary gate: artifact created without errors |
| `gate_SOLVABILITY` | 0/1 | Binary gate: in-process solver OR Playwright self-test confirmed flag recoverable |
| `gate_NON_TRIVIALITY` | 0/1 | Binary gate: not trivial/plagiarised |
| `soft_RAG_GROUNDING` | 0–1 | Soft reward: how well spec references retrieved CVE context |
| `soft_CVE_RELEVANCE` | 0–1 | Soft reward: CVE relevance of the generated task |
| `passed_all_binary` | 0/1 | 1 iff all 4 binary gates passed |
| `pub_ge_06` | 0/1 | 1 iff `total_reward >= 0.6` (production publication gate) |
| `pub_ge_090` | 0/1 | 1 iff `total_reward >= 0.90` (thesis quality bar) |
| `is_selected` | 0/1 | 1 iff pipeline marked this variant as the selected winner |
| `selection_status` | str | `selected` / `best_unselected` / `none` |
| `solvability_source` | str | XSS only: `live_pass`/`live_fail` (container browser verdict), `static` (keyword heuristic), `na`. Blank for non-XSS. Best variant. |
| `xss_selftest_live` | 0/1 | XSS only: 1 iff best variant's SOLVABILITY came from the live container. Blank for non-XSS. |
| `n_selftest_live` | int | XSS only: number of batch variants that got a live container verdict. Blank for non-XSS. |
| `tokens_in` | int | Total input tokens summed over ALL variants in batch |
| `tokens_out` | int | Total output tokens summed over ALL variants in batch |
| `selftest_cost_rub` | float | `n_selftest_live * --rub-per-selftest` (0 unless rate given) |
| `cost_rub` | float | `tokens_in * rub_in + tokens_out * rub_out + selftest_cost_rub` |
| `wall_clock_s` | float | Wall-clock time for the entire `run_pipeline` call (seconds) |

**Verifying the self-test ablation (XSS runs):** in a correct XSS run, the
`full`/`no_rag`/`no_bon` rows should show `solvability_source ∈ {live_pass, live_fail}`
and `xss_selftest_live=1`, while `no_self_test` rows show `solvability_source=static`,
`xss_selftest_live=0`. If `full` rows are `static`, the container wasn't live and the
self-test delta is meaningless — re-run after fixing the container (the preflight
should have caught this).

**Important caveats for `cost_rub`:**
- Token cost does NOT include LLM-judge tokens (`review_variant` does not persist usage).
- Self-test compute (Serverless Container runtime) is excluded unless you pass
  `--rub-per-selftest` (billed by runtime, not tokens; not in the DB). Reference
  rate ≈ 4.21 RUB/core-hour (80.82 RUB / 19.2 core-h).
- Token rates are user-supplied, not from production (production does not track RUB).
- For `no_bon` batches: only 1 variant, so tokens and cost are much lower than
  `full` — a real difference (fewer LLM calls), not a bug.

**Important caveat for `quality_score`:**
- 0.0 does not mean "bad quality" — it means the variant failed binary gates so
  the judge was never called. When computing means over `quality_score`, the
  experiment script excludes rows where `quality_score == 0` to avoid downward bias
  from judge-skipped rows. The `pass_rate` column tracks gate pass rate separately.

### `results_summary.csv` — column reference

| Column | Description |
|--------|-------------|
| `condition` | Condition name |
| `n` | Number of (CVE, condition) rows included |
| `total_reward_mean` | Mean across CVEs |
| `total_reward_std` | Sample std dev |
| `total_reward_ci95_lo/hi` | Bootstrap 95% CI lower/upper |
| `quality_score_mean` | Mean (judge-skipped rows excluded) |
| `quality_score_std` | Sample std dev |
| `quality_score_ci95_lo/hi` | Bootstrap 95% CI lower/upper |
| `pass_rate` | Fraction with `passed_all_binary == 1` |
| `pub_ge_06_rate` | Fraction with `total_reward >= 0.6` |
| `pub_ge_090_rate` | Fraction with `total_reward >= 0.90` |
| `mean_cost_rub` | Mean cost per (CVE, condition) pair |
| `mean_time_s` | Mean wall-clock seconds per pair |

### `run_metadata.json`

Contains: seed, exact CVE-ID list (for reproducibility), model URI, N, cost rates,
task_type, difficulty, git commit hash, UTC timestamp, dry_run flag, and embedded
copies of summary and deltas for single-file archival.

Also contains plain-language notes about:
- What `no_self_test` ablates and when it is meaningful
- Why cost rates are user-supplied
- What statistical methods were used and why

### `artifacts/<CVE>__<condition>.json`

One JSON file per (CVE, condition). Contains the full generated spec and artifact
so results are auditable. Fields:
- `generated_spec` — the raw LLM-generated task specification JSON
- `artifact_result` — the concrete artifact (cipher text, image URL, XSS page URL,
  etc.) or error string
- `reward_checks` — list of all reward check objects (type, score, weight, detail)
- `quality_details` — LLM judge's 5-dimension breakdown (if judge ran)

---

## Statistical Methodology

### Confidence intervals

**Method**: non-parametric bootstrap, 10 000 resamples, percentile method.

This method makes no distributional assumptions (no normality required), which is
appropriate for reward scores that may be bimodal (pass/fail clusters).

### Delta hypothesis testing

**Test**: Wilcoxon signed-rank test, two-sided, normal approximation with continuity
correction, average-rank tie handling.

**Why not paired t-test**: the t-test assumes normality of paired differences.
With no scipy available (and normality unverified), Wilcoxon signed-rank is the
safer default — it only assumes symmetry of differences around the true median,
a much weaker assumption.

**Interpretation**:
- `Δ = mean(full − ablated)` on a given metric
- Positive Δ means the full pipeline scores higher → the ablated component contributes positively
- `p < 0.05` (*): weak evidence the component matters
- `p < 0.01` (**): strong evidence
- `ns`: cannot reject null that the component has no effect
- The 95% CI on Δ gives the range of plausible contribution sizes

### Pairing

Each CVE is processed by all 4 conditions in the same run (same seed, same pool).
The delta is computed per-CVE pair: `full_reward[i] − ablated_reward[i]`.
CVEs missing from either condition (e.g. due to errors) are excluded from the
delta calculation for that ablation, which is logged.

---

## Confounds and Limitations

1. **Task type held constant per run.** `REWARD_WEIGHTS` differ by task type
   (see `reward.py`). Do not compare runs with different `--task-type` directly.
   Run once per task type if multi-type results are needed for the thesis.

2. **`quality_score` is 0 when binary gates fail.** The script excludes these
   zeros from means, but if the full condition has a much higher gate-pass rate
   than `no_rag`, the quality comparison is on different subsets. Report
   `pass_rate` alongside `quality_score_mean` in the thesis.

3. **`no_rag` still gets `soft_RAG_GROUNDING = 0.0`** (expected). The RAG grounding
   check in `validator.py` compares spec content against the (empty) RAG context,
   so it always gives 0. This reduces `total_reward` via the grounding weight.
   This is the correct causal effect: removing RAG removes grounding.

4. **`no_bon` costs much less** (1 LLM call vs 5). The cost comparison is
   meaningful for the thesis (it quantifies what GRPO buys per RUB), but do not
   mistake cost difference for quality difference.

5. **Cost excludes judge tokens.** `review_variant` calls the LLM but the pipeline
   does not persist its token usage. Judge cost is excluded rather than estimated.
   The `cost_rub` column is labelled accordingly in `run_metadata.json`.

6. **Yandex Cloud LLM latency varies.** `wall_clock_s` includes network round-trips
   to the Yandex Foundation Models API. Do not use it as a proxy for compute cost.

---

## Thesis Reporting Template

Suggested table structure for the thesis (adapt as needed):

```
Table X. H₃ ablation results (n=80 CVEs, seed=1337, task_type=web_static_xss, difficulty=medium)

Condition      N  total_reward        quality_score      Pass  ≥0.6  ≥0.90  RUB/task
               n  mean ± std [95%CI]  mean ± std [95%CI]  %     %     %      mean
full           80 ...                 ...                 ...   ...   ...    ...
no_rag         80 ...                 ...                 ...   ...   ...    ...
no_bon         80 ...                 ...                 ...   ...   ...    ...
no_self_test   80 ...                 ...                 ...   ...   ...    ...

Δ (full − no_rag):       total_reward Δ=..., 95%CI=[..., ...], p=... (Wilcoxon)
Δ (full − no_bon):       total_reward Δ=..., 95%CI=[..., ...], p=... (Wilcoxon)
Δ (full − no_self_test): total_reward Δ=..., 95%CI=[..., ...], p=... (Wilcoxon)

Note: CI = non-parametric bootstrap 95% (10 000 resamples).
      Test = Wilcoxon signed-rank (distribution-free, paired).
      Cost = spec-generation tokens only (judge tokens excluded).
      no_self_test meaningful only for web_static_xss with AI_GEN_ENABLE_SELFTEST=true.
      For other task types, full ≡ no_self_test (in-process solvers; no container).
```

---

## Troubleshooting

### "No eligible CVEs in kb_entries"
Run embedding backfill:
```bash
python -m app.scripts.backfill_embeddings
```
And/or run NVD sync to populate CVE records.

### Pipeline fails for every CVE in `no_rag` condition
Check that `AI_GEN_REQUIRE_RAG=false` is not set to block empty-RAG batches at some
other layer. The `inject_rag=False` path bypasses the REQUIRE_RAG check entirely.

### High `batch_status=failed` rate
Check Yandex Cloud API key quotas. The pipeline retries internally
(`AI_GEN_MAX_RETRIES`), but repeated LLM API failures will exhaust retries.

### Checkpoint not working (re-running all CVEs)
The checkpoint reads from `results_raw.csv`. Make sure `--out-dir` points to the
same directory as the previous run. The `(cve_id, condition)` combination is the
checkpoint key — changing `--seed` or `--task-type` does not invalidate the checkpoint
but will produce inconsistent data if the pool changes. Always use the same seed for
a given experiment run.

### Very slow runs
Each pipeline call to Yandex GPT can take 30–120 s depending on load. Conditions
run sequentially (full → no_rag → no_bon) per CVE. Running 80 CVEs fully sequentially
could take 4–10 hours. If faster runs are needed, consider:
- Reducing `--pool-size` (minimum ~30 for meaningful statistics)
- Reducing `AI_GEN_MAX_RETRIES` in `.env` (e.g. set to 1)
- Running multiple seeds in parallel in separate `--out-dir` directories and pooling
  the CSVs before computing statistics
- For the `no_self_test` condition specifically: container round-trips add ~2–5s per
  variant but are the source of the signal; reducing `AI_GEN_NUM_VARIANTS` lowers
  self-test calls proportionally

---

## Files Changed

| File | Change |
|------|--------|
| `backend/app/services/ai_generator/pipeline.py` | Added `inject_rag: bool = True` and `enable_self_test: bool = True` parameters to `run_pipeline`. Defaults preserve production behaviour. |
| `backend/app/services/ai_generator/validator.py` | `_validate_xss` made `async`; when `AI_GEN_ENABLE_SELFTEST=true` the SOLVABILITY gate uses the live container verdict instead of the static keyword heuristic. |
| `backend/app/services/ai_generator/self_test/__init__.py` | New: package marker |
| `backend/app/services/ai_generator/self_test/xss_selftest.py` | New: async client that POSTs to the Serverless Container and returns `XssSelfTestResult`. Fail-open fallback on timeout/error. |
| `backend/app/services/ai_generator/self_test/container/app.py` | New: FastAPI + Playwright container server |
| `backend/app/services/ai_generator/self_test/container/Dockerfile` | New: Playwright/Chromium container image |
| `backend/app/services/ai_generator/self_test/container/requirements.txt` | New: container Python deps |
| `backend/app/services/ai_generator/self_test/container/README.md` | New: build + deploy instructions for Yandex Serverless Containers |
| `backend/app/config.py` | Added `AI_GEN_ENABLE_SELFTEST`, `AI_GEN_SELFTEST_URL`, `AI_GEN_SELFTEST_TIMEOUT_S` settings |
| `backend/experiments/__init__.py` | New: package marker |
| `backend/experiments/ablation_h3.py` | New: experiment harness |
| `backend/experiments/README.md` | New: this file |
