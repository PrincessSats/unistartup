import React, { useState, useEffect, useCallback } from 'react';
import { pipelineAPI } from '../services/api';

// ── Constants ──────────────────────────────────────────────────────────────────

const TASK_TYPES = [
  { value: 'crypto_text_web', label: 'Crypto Text/Web' },
  { value: 'forensics_image_metadata', label: 'Forensics Image' },
  { value: 'web_static_xss', label: 'Web XSS' },
  { value: 'chat_llm', label: 'Chat LLM' },
];

const DIFFICULTIES = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'advanced', label: 'Advanced' },
];

// Ordered list — no "failed" here, it's just a status
const PIPELINE_STAGE_ORDER = [
  { key: 'rag_context',        label: 'RAG Context',  desc: 'Building context from knowledge base' },
  { key: 'spec_generation',    label: 'Spec Gen',     desc: 'Generating task specifications' },
  { key: 'artifact_creation',  label: 'Artifacts',    desc: 'Creating challenge artifacts' },
  { key: 'validation',         label: 'Validation',   desc: 'Running binary reward checks' },
  { key: 'llm_quality_review', label: 'Quality',      desc: 'LLM judge quality assessment' },
  { key: 'grpo_computation',   label: 'GRPO',         desc: 'Computing group-relative advantages' },
  { key: 'selection',          label: 'Selection',    desc: 'Selecting best variant' },
  { key: 'completed',          label: 'Done',         desc: 'Pipeline complete' },
];

const DIFFICULTY_COLORS = {
  beginner:     'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  intermediate: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  advanced:     'text-red-400 bg-red-500/10 border-red-500/30',
};

const STATUS_COLORS = {
  pending:    'text-white/50 bg-white/5 border-white/10',
  generating: 'text-[#9B6BFF] bg-[#9B6BFF]/10 border-[#9B6BFF]/30',
  completed:  'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  failed:     'text-red-400 bg-red-500/10 border-red-500/30',
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function getStageIndex(stage) {
  return PIPELINE_STAGE_ORDER.findIndex(s => s.key === stage);
}

function formatMs(ms) {
  if (!ms) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtFloat(v, digits = 3) {
  return v != null ? v.toFixed(digits) : '—';
}

// ── Stage Visualizer ───────────────────────────────────────────────────────────

function StageNode({ stageKey, label, currentStage, isFailed }) {
  const currentIdx = getStageIndex(currentStage);
  const nodeIdx = getStageIndex(stageKey);
  const isActive = currentStage === stageKey;
  const isCompleted = (currentStage === 'completed')
    ? true
    : (!isFailed && nodeIdx >= 0 && currentIdx > nodeIdx);
  const isStruck = isFailed && nodeIdx > 0 && currentIdx >= 0 && nodeIdx >= currentIdx;

  let cls = 'px-2.5 py-1 rounded-full border text-[11px] font-medium whitespace-nowrap select-none ';
  if (isStruck) {
    cls += 'bg-red-500/5 border-red-500/20 text-red-400/60 line-through';
  } else if (isActive) {
    cls += 'bg-[#9B6BFF]/20 border-[#9B6BFF] text-white animate-pulse';
  } else if (isCompleted) {
    cls += 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400';
  } else {
    cls += 'bg-white/[0.03] border-dashed border-white/10 text-white/25';
  }

  return (
    <span className={cls}>
      {isCompleted && !isStruck ? '✓ ' : isActive ? '⟳ ' : ''}{label}
    </span>
  );
}

function StageVisualizer({ currentStage, isFailed }) {
  const currentIdx = getStageIndex(currentStage);

  return (
    <div className="flex flex-wrap gap-x-1 gap-y-2 items-center">
      {PIPELINE_STAGE_ORDER.map((stage, i) => (
        <React.Fragment key={stage.key}>
          <StageNode
            stageKey={stage.key}
            label={stage.label}
            currentStage={currentStage}
            isFailed={isFailed}
          />
          {i < PIPELINE_STAGE_ORDER.length - 1 && (
            <span className={`text-[10px] select-none ${
              !isFailed && currentIdx > i ? 'text-emerald-500/40' : 'text-white/10'
            }`}>→</span>
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ── Stage Detail Panel ─────────────────────────────────────────────────────────

function StageDetailPanel({ batchStatus }) {
  const {
    current_stage, status, rag_query_text, rag_context_ids, variants,
    group_mean_reward, group_std_reward, pass_rate, selected_variant_id,
    stage_meta, task_type, difficulty, num_variants,
  } = batchStatus;

  const stageInfo = PIPELINE_STAGE_ORDER.find(s => s.key === current_stage);
  const isFailed = status === 'failed';

  // Derived variant counts
  const passedVariants = (variants || []).filter(v => v.passed_all_binary);
  const failedVariants = (variants || []).filter(v => !v.passed_all_binary && v.reward_checks?.length);
  const selectedVariant = (variants || []).find(v => v.id === selected_variant_id);

  // RAG context count
  const ragCount = rag_context_ids?.length ?? 0;

  const rows = [];

  if (current_stage === 'rag_context' || (ragCount > 0 && current_stage !== 'pending')) {
    rows.push({ label: 'RAG query', value: rag_query_text || '(building…)', mono: true });
    rows.push({ label: 'RAG entries loaded', value: ragCount > 0 ? `${ragCount} entries` : '…' });
  }

  if (['spec_generation', 'artifact_creation', 'validation', 'llm_quality_review', 'grpo_computation', 'selection', 'completed'].includes(current_stage)) {
    rows.push({ label: 'Task type', value: task_type });
    rows.push({ label: 'Difficulty', value: difficulty });
    rows.push({ label: 'Variants requested', value: num_variants });
  }

  if (stage_meta) {
    if (stage_meta.variants_generated != null) rows.push({ label: 'Variants generated', value: stage_meta.variants_generated });
    if (stage_meta.variant_number != null) rows.push({ label: 'Quality review — variant', value: `#${stage_meta.variant_number}` });
    if (stage_meta.pass_rate != null) rows.push({ label: 'Pass rate (this attempt)', value: `${(stage_meta.pass_rate * 100).toFixed(0)}%` });
  }

  if (variants?.length > 0) {
    rows.push({ label: 'Variants evaluated', value: variants.length });
    if (passedVariants.length > 0) {
      rows.push({ label: 'Passed binary checks', value: `${passedVariants.length} / ${variants.length}` });
      // Show passed variant scores
      passedVariants.forEach(v => {
        rows.push({
          label: `  Variant #${v.variant_number} reward`,
          value: `${fmtFloat(v.reward_total)} (T=${v.temperature?.toFixed(2) ?? '?'})`,
          indent: true,
        });
      });
    }
    if (failedVariants.length > 0) {
      rows.push({ label: 'Failed binary checks', value: failedVariants.length, warn: true });
    }
  }

  if (group_mean_reward != null) {
    rows.push({ label: 'Group mean reward', value: fmtFloat(group_mean_reward) });
    rows.push({ label: 'Group std reward', value: fmtFloat(group_std_reward) });
  }

  if (pass_rate != null) {
    rows.push({ label: 'Overall pass rate', value: `${(pass_rate * 100).toFixed(0)}%` });
  }

  if (selectedVariant) {
    rows.push({ label: 'Selected variant', value: `#${selectedVariant.variant_number} — reward ${fmtFloat(selectedVariant.reward_total)}`, highlight: true });
    if (selectedVariant.spec_title) {
      rows.push({ label: 'Task title', value: selectedVariant.spec_title, highlight: true });
    }
  }

  if (isFailed) {
    rows.push({ label: 'Status', value: 'All retry attempts exhausted', warn: true });
  }

  if (current_stage === 'pending') {
    return (
      <div className="mt-4 pt-4 border-t border-white/[0.06]">
        <p className="text-[12px] text-white/30 italic">Waiting to start…</p>
      </div>
    );
  }

  return (
    <div className="mt-4 pt-4 border-t border-white/[0.06]">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[11px] text-white/40 uppercase tracking-[0.06em]">
          {isFailed ? '✗ Pipeline Failed' : stageInfo ? `${stageInfo.label} — ${stageInfo.desc}` : current_stage}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3">
        {rows.map((r, i) => (
          <div key={i} className={r.indent ? 'pl-3' : ''}>
            <span className="block text-[10px] text-white/30 uppercase tracking-[0.05em]">{r.label}</span>
            <span className={`block text-[12px] font-medium mt-0.5 break-all ${
              r.highlight ? 'text-[#9B6BFF]' : r.warn ? 'text-red-400' : r.mono ? 'text-white/70 font-mono' : 'text-white/80'
            }`}>
              {String(r.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Review Modal ───────────────────────────────────────────────────────────────

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  }
  return (
    <button
      type="button"
      onClick={handleCopy}
      className="text-[10px] px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/50 hover:text-white/80 transition-colors"
    >
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  );
}

function ReviewSection({ title, children }) {
  return (
    <div className="border border-white/[0.07] rounded-[12px] p-4 space-y-3">
      <h4 className="text-[11px] text-white/40 uppercase tracking-[0.06em]">{title}</h4>
      {children}
    </div>
  );
}

function ReviewField({ label, value, mono, secret, pre }) {
  const [revealed, setRevealed] = useState(false);
  if (value == null || value === '') return null;
  const displayValue = secret && !revealed ? '••••••••••••••••' : String(value);
  return (
    <div>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[11px] text-white/40">{label}</span>
        {secret && (
          <button
            type="button"
            onClick={() => setRevealed(!revealed)}
            className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/50 transition-colors"
          >
            {revealed ? 'Hide' : 'Reveal'}
          </button>
        )}
        {(revealed || !secret) && <CopyButton text={String(value)} />}
      </div>
      {pre ? (
        <pre className="text-[11px] font-mono text-white/70 bg-white/[0.04] rounded-lg p-3 overflow-auto max-h-48 whitespace-pre-wrap break-all">
          {displayValue}
        </pre>
      ) : (
        <p className={`text-[13px] ${secret && !revealed ? 'text-white/20 select-none' : 'text-white/85'}`}>
          {displayValue}
        </p>
      )}
    </div>
  );
}

function ScoreBar({ value }) {
  const pct = Math.max(0, Math.min(100, ((value ?? 0)) * 100));
  const col = (value ?? 0) >= 0.6 ? 'bg-emerald-500' : (value ?? 0) >= 0.3 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${col}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] text-white/50 w-10 text-right">{value != null ? value.toFixed(3) : '—'}</span>
    </div>
  );
}

function ChainStep({ label, value, isFlag, isCiphertext, isFirst, isLast }) {
  const [revealed, setRevealed] = useState(isFirst); // flag revealed by default only if it's the first step? Actually reveal ciphertext always, flag behind reveal
  const shouldHide = isFlag && !revealed;

  return (
    <div className={`rounded-[10px] border p-3 ${
      isFlag ? 'bg-[#9B6BFF]/5 border-[#9B6BFF]/20' :
      isCiphertext ? 'bg-emerald-500/5 border-emerald-500/20' :
      'bg-white/[0.03] border-white/[0.07]'
    }`}>
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className={`text-[10px] uppercase tracking-[0.05em] ${isFlag ? 'text-[#9B6BFF]/70' : isCiphertext ? 'text-emerald-400/70' : 'text-white/40'}`}>
          {label}
        </span>
        <div className="flex gap-1.5">
          {isFlag && (
            <button type="button" onClick={() => setRevealed(!revealed)}
              className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/40 transition-colors">
              {revealed ? 'Hide' : 'Reveal'}
            </button>
          )}
          {value && !shouldHide && <CopyButton text={String(value)} />}
        </div>
      </div>
      <p className={`text-[13px] font-mono font-semibold break-all ${
        shouldHide ? 'text-white/15 select-none' :
        isFlag ? 'text-[#9B6BFF]' :
        isCiphertext ? 'text-emerald-300' :
        'text-white/80'
      }`}>
        {shouldHide ? '••••••••••••••••' : (value || '(empty)')}
      </p>
    </div>
  );
}

function ReviewModal({ batchId, variant, onClose, onPublish, publishing }) {
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    pipelineAPI.getVariantReview(batchId, variant.id)
      .then(data => setReview(data))
      .catch(err => setError(err?.response?.data?.detail || err.message || 'Failed to load'))
      .finally(() => setLoading(false));
  }, [batchId, variant.id]);

  const r = review;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-start justify-center p-4 overflow-y-auto">
      <div className="bg-[#12111A] border border-white/[0.1] rounded-[20px] w-full max-w-2xl my-8">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-white/[0.07]">
          <div>
            <h3 className="text-[16px] font-semibold text-white">
              Review — Variant #{variant.variant_number}
            </h3>
            {r?.spec_title && <p className="text-[13px] text-[#9B6BFF] mt-0.5">{r.spec_title}</p>}
          </div>
          <button type="button" onClick={onClose} className="text-white/40 hover:text-white/80 text-xl leading-none transition-colors">✕</button>
        </div>

        <div className="p-5 space-y-4">
          {loading && <p className="text-white/40 text-center py-8">Loading full review…</p>}
          {error && <p className="text-red-400 text-center py-4">{error}</p>}

          {r && (
            <>
              {/* Spec */}
              <ReviewSection title="Task Specification">
                <ReviewField label="Title" value={r.spec_title} />
                <ReviewField label="Description" value={r.spec_description} />
                {r.spec_story && <ReviewField label="Story / Participant Description" value={r.spec_story} />}
                {r.spec_hint && <ReviewField label="Hint" value={r.spec_hint} />}
                {r.spec_category && <ReviewField label="Category" value={r.spec_category} />}
                <ReviewField label="FLAG (admin only)" value={r.spec_flag} secret pre />
              </ReviewSection>

              {/* Crypto chain visualization (or generic artifact) */}
              {r.artifact_verification?.chain ? (
                <ReviewSection title="Encryption Chain (flag → ciphertext)">
                  <p className="text-[11px] text-white/40 mb-3">
                    How the flag was transformed. Player receives the ciphertext and must reverse each step.
                  </p>
                  {/* Chain diagram */}
                  <div className="space-y-1">
                    {/* Step 0: original flag */}
                    <ChainStep
                      label="Original flag"
                      value={r.artifact_verification.flag || r.spec_flag}
                      isFlag
                      isFirst
                    />
                    {r.artifact_verification.chain.map((op, i) => {
                      const name = op.cipher || op.type || '?';
                      const params = op.params || {};
                      const paramStr = Object.entries(params).map(([k, v]) => `${k}=${v}`).join(', ');
                      return (
                        <React.Fragment key={i}>
                          <div className="flex items-center gap-2 pl-4">
                            <div className="w-px h-4 bg-white/20" />
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#9B6BFF]/15 border border-[#9B6BFF]/30 text-[#9B6BFF]">
                              {name}{paramStr ? ` (${paramStr})` : ''}
                            </span>
                            <span className="text-[10px] text-white/30">↓</span>
                          </div>
                          {i === r.artifact_verification.chain.length - 1 && (
                            <ChainStep
                              label="Ciphertext (what the player sees)"
                              value={r.artifact_content}
                              isCiphertext
                              isLast
                            />
                          )}
                        </React.Fragment>
                      );
                    })}
                  </div>
                  {/* Reverse path */}
                  <div className="mt-4 pt-3 border-t border-white/[0.06]">
                    <p className="text-[10px] text-white/30 uppercase tracking-[0.05em] mb-2">Player solution path (reversed)</p>
                    <div className="flex flex-wrap gap-1.5 items-center">
                      <span className="text-[11px] font-mono px-2 py-1 rounded bg-white/[0.06] text-white/60">ciphertext</span>
                      {[...r.artifact_verification.chain].reverse().map((op, i) => {
                        const name = op.cipher || op.type || '?';
                        const params = op.params || {};
                        const paramStr = Object.entries(params).map(([k, v]) => `${k}=${v}`).join(', ');
                        return (
                          <React.Fragment key={i}>
                            <span className="text-white/20 text-[10px]">→</span>
                            <span className="text-[11px] font-mono px-2 py-1 rounded bg-white/[0.04] border border-white/[0.08] text-white/50">
                              reverse {name}{paramStr ? ` (${paramStr})` : ''}
                            </span>
                          </React.Fragment>
                        );
                      })}
                      <span className="text-white/20 text-[10px]">→</span>
                      <span className="text-[11px] font-mono px-2 py-1 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">flag ✓</span>
                    </div>
                  </div>
                </ReviewSection>
              ) : (
                <ReviewSection title="Artifact">
                  {r.artifact_file_url && <ReviewField label="File URL" value={r.artifact_file_url} />}
                  {r.artifact_content && <ReviewField label="Content" value={r.artifact_content} pre />}
                  {r.artifact_verification && Object.keys(r.artifact_verification).length > 0 && (
                    <ReviewField label="Verification Data" value={JSON.stringify(r.artifact_verification, null, 2)} pre />
                  )}
                  {r.artifact_error && <p className="text-[12px] text-red-400">{r.artifact_error}</p>}
                  {!r.artifact_content && !r.artifact_file_url && !r.artifact_error && (
                    <p className="text-[12px] text-white/30 italic">No artifact available</p>
                  )}
                </ReviewSection>
              )}

              {/* Rewards */}
              <ReviewSection title="Reward Checks">
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <p className="text-[11px] text-white/40 mb-1">Total Reward</p>
                    <ScoreBar value={r.reward_total} />
                  </div>
                  <div>
                    <p className="text-[11px] text-white/40 mb-1">Quality Score</p>
                    <ScoreBar value={r.quality_score} />
                  </div>
                </div>
                {r.reward_checks?.map(c => {
                  const isBinary = ['FORMAT', 'FUNCTIONAL', 'SOLVABILITY', 'NON_TRIVIALITY'].includes(c.type);
                  return (
                    <div key={c.type} className="flex items-start gap-2 py-1 border-b border-white/[0.04] last:border-0">
                      <span className={`text-[12px] font-bold mt-0.5 ${c.score >= 1.0 ? 'text-emerald-400' : c.score > 0 ? 'text-yellow-400' : 'text-red-400'}`}>
                        {isBinary ? (c.score >= 1.0 ? '✓' : '✗') : '~'}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] font-mono text-white/70">{c.type}</span>
                          <span className="text-[10px] text-white/30">w={c.weight}</span>
                          {!isBinary && <div className="flex-1 max-w-[140px]"><ScoreBar value={c.score} /></div>}
                        </div>
                        {c.detail && <p className="text-[11px] text-white/40 mt-0.5 break-words">{c.detail}</p>}
                        {c.error && <p className="text-[11px] text-red-400 mt-0.5">{c.error}</p>}
                      </div>
                    </div>
                  );
                })}
              </ReviewSection>

              {/* Quality details */}
              {r.quality_details && Object.keys(r.quality_details).length > 0 && (
                <ReviewSection title="Quality Dimensions">
                  {Object.entries(r.quality_details).map(([k, v]) => (
                    <div key={k}>
                      <p className="text-[11px] text-white/40 capitalize mb-1">{k.replace(/_/g, ' ')}</p>
                      {typeof v === 'number' ? <ScoreBar value={v} /> : (
                        <p className="text-[12px] text-white/60">{String(v)}</p>
                      )}
                    </div>
                  ))}
                </ReviewSection>
              )}

              {/* Generation stats */}
              <ReviewSection title="Generation Stats">
                <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
                  {[
                    ['Temperature', r.temperature?.toFixed(3)],
                    ['Model', r.model_used?.split('/').pop()],
                    ['Generation time', formatMs(r.generation_time_ms)],
                    ['Tokens in', r.tokens_input],
                    ['Tokens out', r.tokens_output],
                    ['Advantage', fmtFloat(r.advantage)],
                    ['Rank in group', r.rank_in_group != null ? `#${r.rank_in_group}` : null],
                  ].filter(([, v]) => v != null).map(([label, value]) => (
                    <div key={label}>
                      <span className="block text-[10px] text-white/30 uppercase tracking-[0.05em]">{label}</span>
                      <span className="block text-[12px] text-white/80 font-medium mt-0.5">{value}</span>
                    </div>
                  ))}
                </div>
              </ReviewSection>

              {/* Full spec JSON */}
              {r.spec_raw && (
                <ReviewSection title="Full LLM Spec (raw JSON)">
                  <p className="text-[10px] text-white/30 mb-2">Complete output from the generator, including flag and crypto_chain.</p>
                  <ReviewField value={JSON.stringify(r.spec_raw, null, 2)} pre />
                </ReviewSection>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-5 border-t border-white/[0.07]">
          <button
            type="button"
            onClick={onClose}
            className="h-10 px-5 rounded-[12px] bg-white/10 border border-white/10 text-white/80 text-[14px] hover:bg-white/15 transition-colors"
          >
            Close
          </button>
          {variant.passed_all_binary && onPublish && (
            <button
              type="button"
              onClick={() => onPublish(variant.id)}
              disabled={publishing}
              className="h-10 px-5 rounded-[12px] bg-[#9B6BFF] hover:bg-[#8452FF] text-white text-[14px] transition-colors disabled:opacity-50"
            >
              {publishing ? 'Publishing…' : 'Publish Task'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Variant Cards ──────────────────────────────────────────────────────────────

function CheckIcon({ passed }) {
  return passed
    ? <span className="text-emerald-400 font-bold text-[12px]">✓</span>
    : <span className="text-red-400 font-bold text-[12px]">✗</span>;
}

function RewardChecks({ checks }) {
  if (!checks?.length) return <p className="text-white/25 text-[11px]">No checks yet</p>;
  return (
    <div className="space-y-1.5">
      {checks.map((c) => {
        const isBinary = ['FORMAT', 'FUNCTIONAL', 'SOLVABILITY', 'NON_TRIVIALITY'].includes(c.type);
        return (
          <div key={c.type} className="flex items-start gap-2">
            {isBinary ? <CheckIcon passed={c.score >= 1.0} /> : <span className="text-white/30 text-[11px]">~</span>}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-white/60">{c.type}</span>
                {!isBinary && (
                  <div className="flex-1 max-w-[120px]">
                    <ScoreBar value={c.score} />
                  </div>
                )}
              </div>
              {c.detail && <p className="text-[10px] text-white/35 mt-0.5 truncate">{c.detail}</p>}
              {c.error && <p className="text-[10px] text-red-400 mt-0.5 truncate">{c.error}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function VariantCard({ batchId, variant, isSelected, onPublish, onReview, publishing }) {
  const [expanded, setExpanded] = useState(false);
  const failed = !variant.passed_all_binary && variant.reward_checks?.length > 0;

  let borderCls = 'border-white/[0.07]';
  if (isSelected) borderCls = 'border-yellow-400/50 shadow-[0_0_24px_rgba(250,204,21,0.06)]';
  else if (failed) borderCls = 'border-red-500/15';
  else if (variant.passed_all_binary) borderCls = 'border-emerald-500/20';

  return (
    <div className={`bg-white/[0.03] border ${borderCls} rounded-[16px] p-4 flex flex-col gap-3 transition-all duration-300 ${failed && !expanded ? 'opacity-55' : ''}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center flex-wrap gap-1.5">
          <span className="text-[13px] font-semibold text-white">#{variant.variant_number}</span>
          {isSelected && <span className="px-1.5 py-0.5 rounded-full text-[10px] border bg-yellow-400/10 border-yellow-400/30 text-yellow-400">★ Selected</span>}
          {failed && <span className="px-1.5 py-0.5 rounded-full text-[10px] border bg-red-500/10 border-red-500/20 text-red-400/80">Discarded</span>}
          {!failed && variant.passed_all_binary && !isSelected && <span className="px-1.5 py-0.5 rounded-full text-[10px] border bg-emerald-500/10 border-emerald-500/20 text-emerald-400">Passed</span>}
        </div>
        {variant.temperature != null && (
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.06] text-white/40 shrink-0">T={variant.temperature.toFixed(2)}</span>
        )}
      </div>

      {/* Score bar */}
      <div>
        <div className="flex justify-between text-[10px] text-white/40 mb-1">
          <span>Total Reward</span>
          <span className="font-mono">{variant.reward_total != null ? variant.reward_total.toFixed(3) : '—'}</span>
        </div>
        <ScoreBar value={variant.reward_total} />
      </div>

      {/* Metrics */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-white/40">
        {variant.advantage != null && (
          <span>Adv: <span className={`font-mono ${variant.advantage >= 0 ? 'text-emerald-400/80' : 'text-red-400/80'}`}>{variant.advantage.toFixed(3)}</span></span>
        )}
        {variant.rank_in_group != null && <span>Rank: <span className="text-white/60">#{variant.rank_in_group}</span></span>}
        {variant.tokens_input != null && <span>↑{variant.tokens_input} ↓{variant.tokens_output}</span>}
        {variant.generation_time_ms != null && <span>{formatMs(variant.generation_time_ms)}</span>}
      </div>

      {/* Spec preview */}
      {variant.spec_title && <p className="text-[12px] text-white/70 font-medium truncate">{variant.spec_title}</p>}
      {variant.spec_description && <p className="text-[10px] text-white/35 line-clamp-2">{variant.spec_description}</p>}

      {/* Failure reason */}
      {variant.failure_reason && (
        <p className="text-[10px] text-red-400/80 bg-red-500/5 px-2 py-1.5 rounded-lg border border-red-500/10 break-words line-clamp-3">
          {variant.failure_reason}
        </p>
      )}

      {/* Checks toggle */}
      <button type="button" onClick={() => setExpanded(!expanded)} className="text-[10px] text-white/30 hover:text-white/60 transition-colors text-left">
        {expanded ? '▲ Hide checks' : '▼ Checks'}
      </button>
      {expanded && <RewardChecks checks={variant.reward_checks} />}

      {/* Actions */}
      <div className="flex gap-2 mt-auto pt-1">
        <button
          type="button"
          onClick={() => onReview(variant)}
          className="flex-1 h-8 rounded-[10px] text-[12px] bg-white/[0.07] hover:bg-white/[0.12] border border-white/[0.08] text-white/70 transition-colors"
        >
          Review
        </button>
        {isSelected && (
          <button
            type="button"
            onClick={() => onPublish(variant.id)}
            disabled={publishing}
            className="flex-1 h-8 rounded-[10px] text-[12px] bg-[#9B6BFF] hover:bg-[#8452FF] text-white transition-colors disabled:opacity-50"
          >
            {publishing ? '…' : 'Publish'}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Batch History ──────────────────────────────────────────────────────────────

function BatchHistoryItem({ batch, isActive, onClick }) {
  const taskTypeShort = batch.task_type.split('_')[0].toUpperCase();
  const statusCls = STATUS_COLORS[batch.status] || STATUS_COLORS.pending;
  const diffCls = DIFFICULTY_COLORS[batch.difficulty] || '';
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left px-3 py-2 rounded-[10px] border transition-all duration-200 ${
        isActive ? 'bg-[#9B6BFF]/10 border-[#9B6BFF]/30' : 'bg-white/[0.02] border-white/[0.05] hover:bg-white/[0.05]'
      }`}
    >
      <div className="flex items-center gap-1.5 mb-1">
        <span className="text-[10px] font-mono text-white/50 bg-white/10 px-1.5 py-0.5 rounded">{taskTypeShort}</span>
        <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${diffCls}`}>{batch.difficulty}</span>
        <span className={`ml-auto text-[9px] px-1.5 py-0.5 rounded-full border ${statusCls}`}>{batch.status}</span>
      </div>
      <p className="text-[9px] text-white/25 font-mono">
        {batch.created_at ? new Date(batch.created_at).toLocaleString() : '—'}
      </p>
    </button>
  );
}

// ── Confirm Publish Modal ──────────────────────────────────────────────────────

function ConfirmPublishModal({ variant, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#13121A] border border-white/[0.1] rounded-[20px] p-6 max-w-sm w-full">
        <h3 className="text-[16px] font-semibold text-white mb-2">Publish Task?</h3>
        {variant.spec_title && <p className="text-[13px] text-[#9B6BFF] mb-2">{variant.spec_title}</p>}
        {variant.spec_description && <p className="text-[12px] text-white/50 mb-4 line-clamp-3">{variant.spec_description}</p>}
        <p className="text-[11px] text-white/30 mb-5">Creates a live CTF task from Variant #{variant.variant_number}.</p>
        <div className="flex gap-3">
          <button type="button" onClick={onCancel} className="flex-1 h-9 rounded-[10px] bg-white/10 border border-white/10 text-white/70 text-[13px] hover:bg-white/15 transition-colors">Cancel</button>
          <button type="button" onClick={onConfirm} className="flex-1 h-9 rounded-[10px] bg-[#9B6BFF] hover:bg-[#8452FF] text-white text-[13px] transition-colors">Publish</button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function Pipeline() {
  const [taskType, setTaskType] = useState('crypto_text_web');
  const [difficulty, setDifficulty] = useState('beginner');
  const [numVariants, setNumVariants] = useState(5);
  const [topic, setTopic] = useState('');
  const [cveId, setCveId] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState(null);

  const [activeBatchId, setActiveBatchId] = useState(null);
  const [batchStatus, setBatchStatus] = useState(null);
  const [pollError, setPollError] = useState(null);

  const [batches, setBatches] = useState([]);
  const [batchesLoading, setBatchesLoading] = useState(false);

  const [publishTarget, setPublishTarget] = useState(null);
  const [publishing, setPublishing] = useState(false);
  const [publishSuccess, setPublishSuccess] = useState(null);

  const [reviewTarget, setReviewTarget] = useState(null);

  const [toast, setToast] = useState(null);

  const loadBatches = useCallback(async () => {
    setBatchesLoading(true);
    try {
      const data = await pipelineAPI.listBatches({ limit: 30 });
      setBatches(data.items || []);
    } catch { /* not critical */ } finally {
      setBatchesLoading(false);
    }
  }, []);

  useEffect(() => { loadBatches(); }, [loadBatches]);

  // Polling
  const batchStatusStr = batchStatus?.status ?? null;
  useEffect(() => {
    if (!activeBatchId) return;
    if (batchStatusStr && ['completed', 'failed'].includes(batchStatusStr)) return;
    const interval = setInterval(async () => {
      try {
        const data = await pipelineAPI.getBatchStatus(activeBatchId);
        setBatchStatus(data);
        setPollError(null);
        if (['completed', 'failed'].includes(data.status)) loadBatches();
      } catch { setPollError('Status fetch failed'); }
    }, 2500);
    return () => clearInterval(interval);
  }, [activeBatchId, batchStatusStr, loadBatches]);

  async function handleGenerate() {
    setGenerateError(null);
    setGenerating(true);
    setBatchStatus(null);
    setPublishSuccess(null);
    setReviewTarget(null);
    try {
      const data = await pipelineAPI.startGeneration({
        task_type: taskType,
        difficulty,
        num_variants: numVariants,
        topic: topic || undefined,
        cve_id: cveId || undefined,
      });
      setActiveBatchId(data.batch_id);
      setBatchStatus({ status: 'pending', current_stage: 'pending', variants: [], task_type: taskType, difficulty, num_variants: numVariants });
      loadBatches();
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message || 'Generation failed';
      setGenerateError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setGenerating(false);
    }
  }

  async function handleLoadBatch(batchId) {
    setActiveBatchId(batchId);
    setPublishSuccess(null);
    setReviewTarget(null);
    try {
      const data = await pipelineAPI.getBatchStatus(batchId);
      setBatchStatus(data);
    } catch { setPollError('Failed to load batch'); }
  }

  async function handlePublishConfirm() {
    if (!publishTarget || !activeBatchId) return;
    setPublishing(true);
    try {
      const result = await pipelineAPI.publishVariant(activeBatchId, publishTarget.id);
      setPublishSuccess(result.task_id);
      setToast({ type: 'success', message: `Task #${result.task_id} published!` });
      const data = await pipelineAPI.getBatchStatus(activeBatchId);
      setBatchStatus(data);
    } catch (err) {
      const detail = err?.response?.data?.detail || err.message || 'Publish failed';
      setToast({ type: 'error', message: typeof detail === 'string' ? detail : 'Publish failed' });
    } finally {
      setPublishing(false);
      setPublishTarget(null);
    }
  }

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const currentStage = batchStatus?.current_stage || 'pending';
  const isFailed = batchStatus?.status === 'failed';
  const selectedVariantId = batchStatus?.selected_variant_id;
  const variants = batchStatus?.variants || [];

  return (
    <div className="min-h-screen p-6 space-y-5">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-6 right-6 z-50 px-4 py-3 rounded-[12px] border text-[13px] font-medium shadow-xl transition-all ${
          toast.type === 'success' ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300' : 'bg-red-500/20 border-red-500/30 text-red-300'
        }`}>{toast.message}</div>
      )}

      {/* Modals */}
      {publishTarget && (
        <ConfirmPublishModal
          variant={publishTarget}
          onConfirm={handlePublishConfirm}
          onCancel={() => setPublishTarget(null)}
        />
      )}
      {reviewTarget && (
        <ReviewModal
          batchId={activeBatchId}
          variant={reviewTarget}
          onClose={() => setReviewTarget(null)}
          onPublish={(variantId) => { setReviewTarget(null); setPublishTarget(variants.find(v => v.id === variantId)); }}
          publishing={publishing}
        />
      )}

      <h1 className="text-[28px] leading-[32px] tracking-[0.02em] text-white font-semibold">AI Pipeline</h1>

      <div className="flex gap-5 items-start">
        {/* Main column */}
        <div className="flex-1 min-w-0 space-y-4">

          {/* Task Constructor */}
          <div className="bg-white/[0.05] border border-white/[0.08] rounded-[18px] p-5">
            <h2 className="text-[12px] text-white/40 tracking-[0.06em] uppercase mb-4">Task Constructor</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5 mb-4">
              <div>
                <label className="block text-[11px] text-white/40 mb-1.5">Task Type</label>
                <select value={taskType} onChange={e => setTaskType(e.target.value)}
                  className="w-full h-9 px-3 rounded-[10px] bg-white/[0.06] border border-white/[0.09] text-white text-[12px] focus:outline-none focus:border-[#9B6BFF]/50">
                  {TASK_TYPES.map(t => <option key={t.value} value={t.value} className="bg-[#0B0A10]">{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-white/40 mb-1.5">Difficulty</label>
                <select value={difficulty} onChange={e => setDifficulty(e.target.value)}
                  className="w-full h-9 px-3 rounded-[10px] bg-white/[0.06] border border-white/[0.09] text-white text-[12px] focus:outline-none focus:border-[#9B6BFF]/50">
                  {DIFFICULTIES.map(d => <option key={d.value} value={d.value} className="bg-[#0B0A10]">{d.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-white/40 mb-1.5">Variants: {numVariants}</label>
                <input type="range" min={3} max={7} value={numVariants} onChange={e => setNumVariants(Number(e.target.value))}
                  className="w-full mt-2.5 accent-[#9B6BFF]" />
              </div>
              <div>
                <label className="block text-[11px] text-white/40 mb-1.5">Topic</label>
                <input type="text" value={topic} onChange={e => setTopic(e.target.value)} placeholder="optional"
                  className="w-full h-9 px-3 rounded-[10px] bg-white/[0.06] border border-white/[0.09] text-white text-[12px] placeholder-white/20 focus:outline-none focus:border-[#9B6BFF]/50" />
              </div>
              <div>
                <label className="block text-[11px] text-white/40 mb-1.5">CVE ID</label>
                <input type="text" value={cveId} onChange={e => setCveId(e.target.value)} placeholder="optional"
                  className="w-full h-9 px-3 rounded-[10px] bg-white/[0.06] border border-white/[0.09] text-white text-[12px] placeholder-white/20 focus:outline-none focus:border-[#9B6BFF]/50" />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button type="button" onClick={handleGenerate} disabled={generating}
                className="h-10 px-6 rounded-[12px] bg-[#9B6BFF] hover:bg-[#8452FF] text-white text-[14px] font-medium transition-colors disabled:opacity-50">
                {generating ? 'Starting…' : 'Generate'}
              </button>
              {generateError && <p className="text-[12px] text-red-400">{generateError}</p>}
            </div>
          </div>

          {/* Pipeline Stage Flow + Detail */}
          {batchStatus && (
            <div className="bg-white/[0.05] border border-white/[0.08] rounded-[18px] p-5">
              <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                <h2 className="text-[12px] text-white/40 tracking-[0.06em] uppercase">Pipeline Stages</h2>
                <div className="flex items-center gap-3 text-[11px] flex-wrap">
                  {batchStatus.pass_rate != null && (
                    <span className="text-white/40">Pass rate: <span className="text-white font-medium">{(batchStatus.pass_rate * 100).toFixed(0)}%</span></span>
                  )}
                  {batchStatus.group_mean_reward != null && (
                    <span className="text-white/40">Mean reward: <span className="text-white font-medium">{batchStatus.group_mean_reward.toFixed(3)}</span></span>
                  )}
                  {pollError && <span className="text-red-400">{pollError}</span>}
                  {isFailed && <span className="text-red-400 border border-red-500/30 px-2 py-0.5 rounded-full bg-red-500/10">Failed</span>}
                  {batchStatus.status === 'completed' && <span className="text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full bg-emerald-500/10">✓ Complete</span>}
                </div>
              </div>

              {/* Stage nodes — wraps naturally */}
              <StageVisualizer currentStage={currentStage} isFailed={isFailed} />

              {/* Live detail panel */}
              <StageDetailPanel batchStatus={batchStatus} />
            </div>
          )}

          {/* Variant Cards */}
          {variants.length > 0 && (
            <div>
              <h2 className="text-[12px] text-white/40 tracking-[0.06em] uppercase mb-3">Variants</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                {variants.map(v => (
                  <VariantCard
                    key={v.id}
                    batchId={activeBatchId}
                    variant={v}
                    isSelected={v.id === selectedVariantId && !publishSuccess}
                    onPublish={(variantId) => setPublishTarget(variants.find(x => x.id === variantId))}
                    onReview={setReviewTarget}
                    publishing={publishing}
                  />
                ))}
              </div>
              {publishSuccess && (
                <div className="mt-3 px-4 py-3 rounded-[12px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-[13px]">
                  ✓ Task #{publishSuccess} published successfully.
                </div>
              )}
            </div>
          )}

          {/* Empty state */}
          {!batchStatus && (
            <div className="bg-white/[0.03] border border-dashed border-white/[0.07] rounded-[18px] p-12 text-center">
              <p className="text-white/25 text-[13px]">Configure and generate a task to see pipeline results.</p>
            </div>
          )}
        </div>

        {/* History sidebar */}
        <div className="w-60 shrink-0">
          <div className="bg-white/[0.05] border border-white/[0.08] rounded-[18px] p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[12px] text-white/40 tracking-[0.06em] uppercase">History</h2>
              <button type="button" onClick={loadBatches} className="text-[11px] text-white/25 hover:text-white/60 transition-colors">↻</button>
            </div>
            {batchesLoading && <p className="text-[11px] text-white/25 text-center py-4">Loading…</p>}
            {!batchesLoading && batches.length === 0 && <p className="text-[11px] text-white/20 text-center py-4">No batches yet</p>}
            <div className="space-y-1.5 max-h-[70vh] overflow-y-auto">
              {batches.map(b => (
                <BatchHistoryItem
                  key={b.batch_id}
                  batch={b}
                  isActive={b.batch_id === activeBatchId}
                  onClick={() => handleLoadBatch(b.batch_id)}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
