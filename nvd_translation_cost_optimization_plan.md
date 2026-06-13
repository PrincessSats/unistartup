# NVD Translation Cost Optimization Plan

## Executive Summary

The NVD sync translation process currently uses the expensive `deepseek-v32` model via Yandex Cloud, costing approximately **1.15 RUB per CVE** (three separate LLM calls per entry). For a typical sync of 1000 CVEs, this translates to **1150 RUB**. Additionally, server restarts interrupt translation after 20–40 entries, causing wasted costs and incomplete data.

This plan outlines a systematic approach to reduce translation costs by **80–96%** while preserving acceptable translation quality. The proposed optimizations range from simple configuration changes to architectural improvements, with phased implementation to minimize risk.

## Current Cost Analysis

### Cost Drivers
1. **Model choice**: `deepseek-v32` at 0.5 RUB per 1000 input tokens + 0.5 RUB per 1000 output tokens.
2. **Multiple LLM calls per CVE**: `TranslationService.translate_full_cve` makes three separate calls (title, summary, explainer).
3. **No batching**: Each entry is processed individually (concurrency limit = 3).
4. **No caching**: Duplicate descriptions are translated again.
5. **High reasoning effort**: `YANDEX_REASONING_EFFORT=high` increases token cost.
6. **Interruptions**: Server restarts cause partial translation, wasting already‑paid tokens.

### Estimated Token Usage per CVE
- **Title**: ~150 characters → ~195 tokens
- **Summary**: ~3000 characters → ~3900 tokens  
- **Explainer**: ~8000 characters → ~10400 tokens
- **Total per CVE**: ~14495 tokens (input + output ≈ 2×)
- **Cost per CVE**: (14495 / 1000) × 0.5 RUB × 2 ≈ **1.15 RUB**

### Annual Projection (assuming 10,000 CVEs/year)
- Current: **11,500 RUB**
- Target after optimization: **2,300–460 RUB** (80–96% reduction)

## Optimization Strategies

### Tier 1 – Configuration Changes (Immediate, No Code Changes)
1. **Switch to cheaper model**: Change `TRANSLATION_MODEL_ID` from `"deepseek-v32"` to `"yandexgpt-lite"` (cost: 0.2 RUB/1K tokens). Quality sufficient for technical translation.
2. **Lower reasoning effort**: Set `YANDEX_REASONING_EFFORT=low` or `medium` (reduces cost per token for deepseek‑v32 if kept).
3. **Increase batch size**: Raise `BATCH_SIZE` from 20 to 50 (reduces per‑chunk overhead).
4. **Adjust concurrency**: Keep `CONCURRENCY_LIMIT=3` (Yandex quota is 10 concurrent requests).

### Tier 2 – Architectural Improvements (Code Changes Required)
5. **Consolidate translation calls**: Replace `translate_full_cve` with `generate_article_payload` (single LLM call per CVE instead of three). Already used by `_translate_entries_for_log` for backlog translation.
6. **Batch translation API calls**: Group up to `BATCH_SIZE` CVEs into a single LLM request with a prompt that returns a JSON array of `{ru_title, ru_summary, ru_explainer}` objects.
7. **Translation cache**: Add table `translation_cache(hash text PRIMARY KEY, ru_title text, ru_summary text, ru_explainer text)`. Hash raw English text (SHA‑256) before translation; skip duplicates.
8. **Severity‑based filtering**: Only translate CVEs with CVSS base score ≥ 5.0 (configurable). Reduces volume by ~50% while covering significant vulnerabilities.

### Tier 3 – Alternative Services
9. **Yandex Translate API**: Use `https://translate.api.cloud.yandex.net/translate/v2/translate` at ~0.1 RUB per 1000 characters. Post‑processing can split translation into title/summary/explainer.
10. **Open‑source translation model**: Deploy `Helsinki‑NLP/opus‑mt‑en‑ru` in the same container (zero ongoing cost). Slower inference but acceptable for background sync.
11. **Hybrid approach**: Use Yandex Translate for bulk translation, falling back to `yandexgpt‑lite` for complex/ambiguous descriptions.

## Implementation Phases

### Phase 1 (Immediate – Days)
- Change `TRANSLATION_MODEL_ID` to `"yandexgpt-lite"` in `translation_service.py`.
- Set `YANDEX_REASONING_EFFORT=low` in environment variables.
- Increase `BATCH_SIZE` to 50 in `nvd_sync.py`.
- Update `cleanup_stale_sync_logs` to treat translation progress as partial success (already implemented? verify).

**Expected cost reduction**: ~83% (from 1.15 RUB/CVE to ~0.2 RUB/CVE).

### Phase 2 (Next Release – Weeks)
- Replace `translate_full_cve` with `generate_article_payload` in `store_kb_entries` translation hook.
- Add translation cache table and logic (migration + service integration).
- Implement severity filter (CVSS ≥ 5.0) as an optional configuration.

**Expected cost reduction**: additional 5–10% (total ~87%).

### Phase 3 (Future – Months)
- Implement batch translation API calls (requires prompt engineering and JSON array output).
- Integrate Yandex Translate API as a fallback or primary translation engine.
- Monitor cost per CVE and quality metrics; adjust model selection accordingly.

**Expected cost reduction**: up to 96% (cost per CVE ~0.05 RUB).

## Quality Assurance & Monitoring

### Quality Sampling
- Randomly sample 5% of translated entries for manual review.
- Compare `deepseek‑v32` vs `yandexgpt‑lite` translations on key technical terms.
- Collect user feedback on KB article clarity and completeness.

### Cost Tracking
- Log token usage per sync in `nvd_sync_log` (add columns `input_tokens`, `output_tokens`, `estimated_cost_rub`).
- Create dashboard showing translation cost per CVE over time.
- Set up Yandex Cloud billing alerts for translation service.

### Performance Metrics
- Translation success rate (completed/total).
- Average time per CVE.
- Token usage per CVE (input/output).
- Cache hit ratio (after cache implementation).

### Fallback Strategy
- Maintain ability to revert to `deepseek‑v32` if quality issues arise.
- Implement A/B testing for new translation methods on a subset of CVEs.

## Risk Mitigation

### Technical Risks
- **Rate limiting**: Yandex quota is 10 concurrent requests; keep `CONCURRENCY_LIMIT ≤ 5`.
- **Timeout handling**: Translation calls have 150s timeout; batch processing must respect this.
- **Error recovery**: Failed translations should be retried with exponential backoff (already present).
- **Data consistency**: Cache invalidation when source text changes (rare for NVD).

### Business Risks
- **Quality degradation**: Monitor user feedback and adjust model selection.
- **Increased latency**: Batch translation may increase per‑request latency but reduce overall sync time.
- **Service dependency**: Relying on Yandex Translate API adds another external dependency.

## Success Criteria
1. Translation cost reduced by ≥80% while maintaining acceptable quality (user satisfaction score ≥4/5).
2. No increase in translation failure rate (<5% failures).
3. Automated cost monitoring in place (daily cost reports).
4. Clear documentation of optimization choices and trade‑offs.

## Next Steps
1. **Immediate action**: Apply Phase 1 configuration changes and deploy to staging.
2. **Test**: Run a limited sync (e.g., 100 CVEs) and compare cost/quality with baseline.
3. **Plan Phase 2**: Design translation cache schema and update translation hook.
4. **Schedule**: Coordinate with development team for implementation sprints.

## References
- `backend/app/services/nvd_sync.py` – Translation hook, batch processing.
- `backend/app/services/ai_generator/translation_service.py` – Model ID, translation methods.
- `backend/app/services/article_generation.py` – `generate_article_payload` implementation.
- `backend/app/config.py` – `YANDEX_REASONING_EFFORT` setting.
- Skill: `nvd-sync-cost-optimization` (detailed technical guidance).
- Skill: `nvd-sync-translation-failures` (server restart issue).

---

*Document generated on April 19, 2026. Review and update as new data becomes available.*