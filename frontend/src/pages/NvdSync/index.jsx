import React, { useEffect, useRef, useState } from 'react';
import useNvdSyncData from './useNvdSyncData';

function fmt(value) {
  if (value === null || value === undefined) return '—';
  if (Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('ru-RU');
}

function fmtDt(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function pct(completed, total) {
  if (!total) return 0;
  return Math.max(0, Math.min(100, Math.round((Math.min(completed, total) / total) * 100)));
}

const STATUS_COLORS = {
  fetching: { dot: 'bg-blue-400 animate-pulse', badge: 'bg-blue-500/10 border-blue-500/25', text: 'text-blue-400', label: 'Fetching CVEs...' },
  translating: { dot: 'bg-purple-400 animate-pulse', badge: 'bg-purple-500/10 border-purple-500/25', text: 'text-purple-400', label: 'Translating articles...' },
  embedding: { dot: 'bg-cyan-400 animate-pulse', badge: 'bg-cyan-500/10 border-cyan-500/25', text: 'text-cyan-400', label: 'Computing embeddings...' },
  success: { dot: 'bg-emerald-400', badge: 'bg-emerald-500/10 border-emerald-500/25', text: 'text-emerald-400', label: 'Completed' },
  partial_success: { dot: 'bg-amber-400', badge: 'bg-amber-500/10 border-amber-500/25', text: 'text-amber-400', label: 'Partial success' },
  failed: { dot: 'bg-rose-400', badge: 'bg-rose-500/10 border-rose-500/25', text: 'text-rose-400', label: 'Failed' },
  cancelled: { dot: 'bg-white/40', badge: 'bg-white/5 border-white/15', text: 'text-white/50', label: 'Stopped' },
};

function StatusBadge({ status }) {
  const c = STATUS_COLORS[status] || STATUS_COLORS.success;
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border ${c.badge}`}>
      <div className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      <span className={`text-[12px] ${c.text}`}>{c.label}</span>
    </div>
  );
}

function ProgressBar({ value, color = 'emerald', label, current, total, showWhenEmpty = false }) {
  const isEmpty = !total;
  if (isEmpty && !showWhenEmpty) return null;
  const barClass = color === 'purple'
    ? 'bg-gradient-to-r from-purple-400 to-fuchsia-400'
    : color === 'cyan'
      ? 'bg-gradient-to-r from-cyan-400 to-blue-400'
      : 'bg-gradient-to-r from-emerald-400 to-teal-400';

  return (
    <div>
      <div className="flex justify-between items-baseline mb-1.5">
        <span className="text-[12px] text-white/50">{label}</span>
        <span className="text-[11px] font-mono text-white/40">{fmt(current)} / {fmt(total || 0)}</span>
      </div>
      <div className="h-2 bg-white/[0.07] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${barClass}`}
          style={{ width: `${isEmpty ? 0 : value}%` }}
        />
      </div>
      <div className="text-right mt-0.5">
        <span className="text-[10px] text-white/25">{isEmpty ? '—' : `${value}%`}</span>
      </div>
    </div>
  );
}

function ActionButton({ label, onClick, disabled, loading, color = 'white' }) {
  const colorMap = {
    white: 'bg-white/[0.1] border-white/[0.3] text-white/60 hover:bg-white/[0.2] hover:text-white/80 hover:border-white/[0.5]',
    purple: 'bg-purple-500/10 border-purple-500/30 text-purple-300 hover:bg-purple-500/20 hover:text-purple-200 hover:border-purple-400/50',
    cyan: 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/20 hover:text-cyan-200 hover:border-cyan-400/50',
  };
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`h-9 px-4 rounded-[9px] border text-[12px] tracking-[0.05em] font-medium transition-colors duration-200 whitespace-nowrap disabled:opacity-40 disabled:cursor-not-allowed ${colorMap[color]}`}
    >
      {loading ? (
        <span className="flex items-center gap-2">
          <span className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
          Running...
        </span>
      ) : label}
    </button>
  );
}

function NvdSync() {
  const { nvdSync, isBusy, pendingOp, isActive, error, onFetch, onTranslate, onEmbed, onStop, onPurge } = useNvdSyncData();
  const [translateLimit, setTranslateLimit] = useState('');
  const eventLogRef = useRef(null);

  const s = nvdSync || {};
  const status = s.status || null;
  const isFetching = status === 'fetching' || pendingOp === 'fetch';
  const isTranslating = status === 'translating' || pendingOp === 'translate';
  const isEmbedding = status === 'embedding' || pendingOp === 'embed';

  const transPct = pct((s.translation_completed || 0) + (s.translation_failed || 0), s.translation_total);
  const embedPct = pct((s.embedding_completed || 0) + (s.embedding_failed || 0), s.embedding_total);

  const eventLog = Array.isArray(s.event_log) ? s.event_log : [];

  useEffect(() => {
    if (eventLogRef.current) {
      eventLogRef.current.scrollTop = eventLogRef.current.scrollHeight;
    }
  }, [eventLog.length]);

  const STAGE_COLOR = { FETCHING: 'text-blue-400', TRANSLATING: 'text-purple-400', EMBEDDING: 'text-cyan-400', SUCCESS: 'text-emerald-400', ERROR: 'text-rose-400', INIT: 'text-white/50' };

  return (
    <div className="flex-1 min-w-0 space-y-4">
      {/* Header */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[22px] leading-[26px] font-semibold tracking-[0.02em] text-white">NVD Sync</div>
          <div className="text-[13px] text-white/40 mt-1">Синхронизация CVE из National Vulnerability Database</div>
        </div>
      </div>

      {error && (
        <div className="text-[13px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-[10px] px-4 py-2">
          {error}
        </div>
      )}

      {/* Status row */}
      <div className="bg-white/[0.04] border border-white/[0.07] rounded-[16px] px-5 py-4 flex items-center gap-4 flex-wrap">
        {status ? <StatusBadge status={status} /> : <span className="text-[12px] text-white/30 italic">Нет данных</span>}
        {s.detailed_status && (
          <span className="text-[12px] text-white/40">{s.detailed_status}</span>
        )}
        <span className="ml-auto text-[11px] text-white/25">Last: {fmtDt(s.last_fetch_at)}</span>
        {isActive && (
          <button
            type="button"
            onClick={onStop}
            disabled={pendingOp === 'stop'}
            className="h-8 px-3 rounded-[8px] border border-rose-500/40 bg-rose-500/10 text-rose-400 text-[12px] tracking-[0.04em] transition-colors duration-200 hover:bg-rose-500/20 hover:border-rose-400/60 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {pendingOp === 'stop' ? 'Stopping...' : '■ Stop'}
          </button>
        )}
      </div>

      {/* 3 stage cards */}
      <div className="grid grid-cols-3 gap-4">
        {/* Fetch */}
        <div className="bg-white/[0.04] border border-white/[0.07] rounded-[16px] p-5 flex flex-col gap-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="text-[11px] uppercase tracking-[0.15em] text-blue-400/60 mb-1">Stage 1</div>
              <div className="text-[14px] font-semibold text-white">Fetch CVEs</div>
              <div className="text-[11px] text-white/35 mt-0.5">Загрузка из NVD API за 24ч</div>
            </div>
            <ActionButton
              label="▶ Fetch"
              onClick={onFetch}
              disabled={isBusy}
              loading={isFetching}
              color="white"
            />
          </div>
          <div className="grid grid-cols-2 gap-2 mt-auto">
            <div className="bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2">
              <div className="text-[16px] font-semibold text-white">{fmt(s.fetched_count)}</div>
              <div className="text-[10px] text-white/35 mt-0.5">CVEs fetched</div>
            </div>
            <div className="bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2">
              <div className="text-[16px] font-semibold text-white">{fmt(s.last_inserted)}</div>
              <div className="text-[10px] text-white/35 mt-0.5">New stored</div>
            </div>
          </div>
          {isFetching && s.total_to_fetch > 0 && (
            <ProgressBar
              value={pct(s.fetched_count, s.total_to_fetch)}
              color="emerald"
              label="Fetching"
              current={s.fetched_count}
              total={s.total_to_fetch}
              showWhenEmpty
            />
          )}
        </div>

        {/* Translate */}
        <div className="bg-white/[0.04] border border-white/[0.07] rounded-[16px] p-5 flex flex-col gap-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="text-[11px] uppercase tracking-[0.15em] text-purple-400/60 mb-1">Stage 2</div>
              <div className="text-[14px] font-semibold text-white">Translate</div>
              <div className="text-[11px] text-white/35 mt-0.5">Генерация KB-статей (ru)</div>
            </div>
            <ActionButton
              label="▶ Translate"
              onClick={() => onTranslate(translateLimit ? parseInt(translateLimit, 10) : undefined)}
              disabled={isBusy}
              loading={isTranslating}
              color="purple"
            />
          </div>

          {/* Untranslated count + limit input */}
          <div className="flex items-center gap-2">
            {s.untranslated_count != null && (
              <span className="text-[11px] text-purple-400/70">
                {fmt(s.untranslated_count)} untranslated
              </span>
            )}
            <div className="ml-auto flex items-center gap-1.5">
              <span className="text-[11px] text-white/30">Limit:</span>
              <input
                type="number"
                min="1"
                placeholder={s.untranslated_count != null ? String(s.untranslated_count) : 'all'}
                value={translateLimit}
                onChange={e => setTranslateLimit(e.target.value)}
                disabled={isBusy}
                className="w-20 h-7 px-2 rounded-[6px] bg-white/[0.06] border border-white/[0.12] text-white/70 text-[11px] font-mono placeholder-white/25 focus:outline-none focus:border-purple-400/40 disabled:opacity-40"
              />
            </div>
          </div>
          {/* Purge untranslated */}
          <button
            type="button"
            onClick={() => {
              if (window.confirm('Delete all untranslated articles except the newest 300?')) {
                onPurge(300);
              }
            }}
            disabled={isBusy}
            className="self-start h-7 px-3 rounded-[6px] border border-rose-500/30 bg-rose-500/08 text-rose-400/80 text-[11px] tracking-[0.04em] transition-colors duration-200 hover:bg-rose-500/15 hover:border-rose-400/50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {pendingOp === 'purge' ? 'Purging...' : '🗑 Purge untranslated (keep 300)'}
          </button>
          <ProgressBar
            value={transPct}
            color="purple"
            label="Translation"
            current={(s.translation_completed || 0) + (s.translation_failed || 0)}
            total={s.translation_total}
            showWhenEmpty={isTranslating}
          />
          <div className="grid grid-cols-2 gap-2 mt-auto">
            <div className="bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2">
              <div className="text-[16px] font-semibold text-emerald-400">{fmt(s.translation_completed)}</div>
              <div className="text-[10px] text-white/35 mt-0.5">Done</div>
            </div>
            <div className="bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2">
              <div className="text-[16px] font-semibold text-rose-400">{fmt(s.translation_failed)}</div>
              <div className="text-[10px] text-white/35 mt-0.5">Failed</div>
            </div>
          </div>
        </div>

        {/* Embed */}
        <div className="bg-white/[0.04] border border-white/[0.07] rounded-[16px] p-5 flex flex-col gap-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="text-[11px] uppercase tracking-[0.15em] text-cyan-400/60 mb-1">Stage 3</div>
              <div className="text-[14px] font-semibold text-white">Embed</div>
              <div className="text-[11px] text-white/35 mt-0.5">Векторные embeddings</div>
            </div>
            <ActionButton
              label="▶ Embed"
              onClick={onEmbed}
              disabled={isBusy}
              loading={isEmbedding}
              color="cyan"
            />
          </div>
          <ProgressBar
            value={embedPct}
            color="cyan"
            label="Embeddings"
            current={(s.embedding_completed || 0) + (s.embedding_failed || 0)}
            total={s.embedding_total}
            showWhenEmpty={isEmbedding}
          />
          <div className="grid grid-cols-2 gap-2 mt-auto">
            <div className="bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2">
              <div className="text-[16px] font-semibold text-emerald-400">{fmt(s.embedding_completed)}</div>
              <div className="text-[10px] text-white/35 mt-0.5">Done</div>
            </div>
            <div className="bg-white/[0.04] border border-white/[0.06] rounded-lg px-3 py-2">
              <div className="text-[16px] font-semibold text-rose-400">{fmt(s.embedding_failed)}</div>
              <div className="text-[10px] text-white/35 mt-0.5">Failed</div>
            </div>
          </div>
        </div>
      </div>

      {/* Event log */}
      <div className="bg-white/[0.04] border border-white/[0.07] rounded-[16px] p-5">
        <div className="mb-3">
          <div className="text-[11px] uppercase tracking-[0.15em] text-white/25 mb-1">Event Log</div>
          <div className="text-[14px] font-semibold text-white">Real-time Sync Log</div>
        </div>
        <div
          ref={eventLogRef}
          className="h-52 overflow-y-auto bg-white/[0.02] border border-white/[0.05] rounded-lg p-3 font-mono text-[11px] leading-relaxed"
        >
          {eventLog.length > 0 ? (
            eventLog.map((ev, idx) => {
              const ts = new Date(ev.timestamp).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
              const col = STAGE_COLOR[ev.stage] || 'text-white/40';
              return (
                <div key={idx} className="border-b border-white/[0.04] py-1 last:border-b-0">
                  <span className="text-white/25">[{ts}]</span>
                  {' '}
                  <span className={col}>{ev.stage}</span>
                  {' '}
                  <span className="text-white/65">{ev.message}</span>
                </div>
              );
            })
          ) : (
            <div className="text-white/30 italic">Нет событий</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default NvdSync;
