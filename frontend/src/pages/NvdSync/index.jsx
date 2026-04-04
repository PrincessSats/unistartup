import React, { useEffect, useRef } from 'react';
import useNvdSyncData from './useNvdSyncData';

const cardBase = 'bg-white/[0.05] border border-white/[0.08] rounded-[18px]';

function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  if (Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('ru-RU');
}

function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getNvdProgress(sync) {
  const total = Number(sync?.embedding_total || 0);
  const completed = Number(sync?.embedding_completed || 0);
  const failed = Number(sync?.embedding_failed || 0);
  const processed = total > 0 ? Math.min(total, completed + failed) : 0;
  const percent = total > 0 ? Math.max(0, Math.min(100, Math.round((processed / total) * 100))) : 0;

  const transTotal = Number(sync?.translation_total || 0);
  const transCompleted = Number(sync?.translation_completed || 0);
  const transFailed = Number(sync?.translation_failed || 0);
  const transProcessed = transTotal > 0 ? Math.min(transTotal, transCompleted + transFailed) : 0;
  const transPercent = transTotal > 0 ? Math.max(0, Math.min(100, Math.round((transProcessed / transTotal) * 100))) : 0;

  return {
    total,
    completed,
    failed,
    processed,
    percent,
    transTotal,
    transCompleted,
    transFailed,
    transProcessed,
    transPercent,
  };
}

const NVD_ACTIVE_STATUSES = new Set(['fetching', 'embedding', 'translating']);

function NvdSync() {
  const { nvdSync, isRunning, error, onFetch } = useNvdSyncData();
  const eventLogRef = useRef(null);

  const nvdStatus = nvdSync?.status || null;
  const nvdProgress = React.useMemo(() => getNvdProgress(nvdSync), [nvdSync]);
  const isNvdBusy = isRunning || NVD_ACTIVE_STATUSES.has(nvdStatus);

  const nvdStatusLabel = React.useMemo(() => {
    if (nvdStatus === 'fetching') return 'Получаем CVE из NVD';
    if (nvdStatus === 'translating') return 'Генерируем статьи для KB';
    if (nvdStatus === 'embedding') return 'Считаем embeddings';
    if (nvdStatus === 'failed') return 'Синхронизация завершилась ошибкой';
    if (nvdStatus === 'partial_success') return 'Синхронизация прервана, но данные сохранены';
    if (nvdStatus === 'success' && nvdProgress.total > 0) return 'Embeddings готовы';
    if (nvdStatus === 'success') return 'Синхронизация завершена';
    return 'Нет активной синхронизации';
  }, [nvdProgress.total, nvdStatus]);

  // Auto-scroll event log to bottom when new events arrive
  useEffect(() => {
    if (eventLogRef.current) {
      eventLogRef.current.scrollTop = eventLogRef.current.scrollHeight;
    }
  }, [nvdSync?.event_log]);

  const eventLog = nvdSync?.event_log || [];

  return (
    <div className="flex-1 min-w-0">
      {/* Page Header */}
      <div className="mb-6">
        <div className="text-[22px] leading-[26px] font-semibold tracking-[0.02em] text-white">
          NVD Sync
        </div>
        <div className="text-[13px] text-white/40 mt-1">
          Синхронизация CVE из National Vulnerability Database
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="text-[14px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-[12px] px-4 py-2 mb-4">
          {error}
        </div>
      )}

      {/* 3-Panel Grid */}
      <div className="grid grid-cols-2 gap-4">
        {/* Panel 1: Sync Data */}
        <div className={`${cardBase} p-6`}>
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              <div className="text-[12px] uppercase tracking-[0.18em] text-white/30 mb-2">Sync Data</div>
              <div className="text-[16px] leading-[20px] font-semibold text-white">
                Current Sync Status
              </div>
              <div className="text-[12px] text-white/40 mt-1">
                Состояние синхронизации и управление запуском
              </div>
            </div>
            <button
              type="button"
              onClick={onFetch}
              disabled={isNvdBusy}
              className="h-10 px-4 rounded-[10px] bg-white/[0.15] border border-white/[0.4] text-white/70 text-[13px] tracking-[0.04em] transition-colors duration-200 hover:bg-white/[0.25] hover:text-white/80 hover:border-white/[0.6] disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap flex-shrink-0"
            >
              {isRunning
                ? 'Starting...'
                : nvdStatus === 'fetching'
                  ? 'Fetching NVD...'
                  : nvdStatus === 'embedding'
                    ? 'Embedding...'
                    : '▶ Fetch NVD 24h'}
            </button>
          </div>

          {/* Status Badge */}
          <div className="flex items-center gap-2 mb-4">
            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full border ${
              nvdStatus === 'failed' ? 'bg-rose-500/10 border-rose-500/25' :
              nvdStatus === 'partial_success' ? 'bg-amber-500/10 border-amber-500/25' :
              NVD_ACTIVE_STATUSES.has(nvdStatus) ? 'bg-purple-500/10 border-purple-500/25' :
              'bg-emerald-500/10 border-emerald-500/25'
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${
                nvdStatus === 'failed' ? 'bg-rose-400' :
                nvdStatus === 'partial_success' ? 'bg-amber-400' :
                NVD_ACTIVE_STATUSES.has(nvdStatus) ? 'bg-purple-400 animate-pulse' :
                'bg-emerald-400'
              }`} />
              <span className={`text-[12px] ${
                nvdStatus === 'failed' ? 'text-rose-400' :
                nvdStatus === 'partial_success' ? 'text-amber-400' :
                NVD_ACTIVE_STATUSES.has(nvdStatus) ? 'text-purple-400' :
                'text-emerald-400'
              }`}>{nvdStatusLabel}</span>
            </div>
            <span className="text-[11px] text-white/30 ml-auto">
              Last: {formatDateTime(nvdSync?.last_fetch_at)}
            </span>
          </div>

          {/* Pipeline Stages */}
          <div className="flex gap-2 mb-4">
            <div className="flex-1 px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/7 text-center">
              <div className="text-[11px] font-semibold text-emerald-400 mb-1">Fetching</div>
              <div className="text-[10px] text-emerald-400/70">{formatNumber(nvdSync?.fetched_count)}</div>
            </div>
            <div className="flex-1 px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/7 text-center">
              <div className="text-[11px] font-semibold text-emerald-400 mb-1">Translating</div>
              <div className="text-[10px] text-emerald-400/70">{formatNumber(nvdSync?.translation_total)}</div>
            </div>
            <div className="flex-1 px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/7 text-center">
              <div className="text-[11px] font-semibold text-emerald-400 mb-1">Embedding</div>
              <div className="text-[10px] text-emerald-400/70">{formatNumber(nvdProgress.total)}</div>
            </div>
          </div>

          {/* Stats */}
          <div className="flex gap-3">
            <div className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2">
              <div className="text-[18px] font-semibold text-white font-variant-numeric">{formatNumber(nvdSync?.fetched_count)}</div>
              <div className="text-[11px] text-white/40 mt-0.5">CVEs fetched</div>
            </div>
            <div className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2">
              <div className="text-[18px] font-semibold text-white">{formatNumber(nvdSync?.last_inserted)}</div>
              <div className="text-[11px] text-white/40 mt-0.5">New articles</div>
            </div>
          </div>
        </div>

        {/* Panel 2: Translation Progress */}
        <div className={`${cardBase} p-6`}>
          <div className="mb-4">
            <div className="text-[12px] uppercase tracking-[0.18em] text-white/30 mb-2">Translation Progress</div>
            <div className="text-[16px] leading-[20px] font-semibold text-white">
              Pipeline Status
            </div>
            <div className="text-[12px] text-white/40 mt-1">
              Статус перевода и embeddings
            </div>
          </div>

          {/* Translation Progress */}
          <div className="mb-4">
            <div className="flex justify-between items-baseline mb-2">
              <span className="text-[12px] text-white/50">Translation</span>
              <span className="text-[12px] font-mono text-white/60">{formatNumber(nvdProgress.transProcessed)} / {formatNumber(nvdProgress.transTotal)}</span>
            </div>
            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-emerald-400 to-teal-400 rounded-full transition-all duration-500"
                style={{ width: `${nvdProgress.transPercent}%` }}
              />
            </div>
          </div>

          {/* Embedding Progress */}
          <div className="mb-4">
            <div className="flex justify-between items-baseline mb-2">
              <span className="text-[12px] text-white/50">Embeddings</span>
              <span className="text-[12px] font-mono text-white/60">{formatNumber(nvdProgress.processed)} / {formatNumber(nvdProgress.total)}</span>
            </div>
            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  nvdProgress.failed > 0
                    ? 'bg-gradient-to-r from-amber-400 to-yellow-400'
                    : 'bg-gradient-to-r from-emerald-400 to-teal-400'
                }`}
                style={{ width: `${nvdProgress.percent}%` }}
              />
            </div>
          </div>

          {/* Stats */}
          <div className="flex gap-3">
            <div className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2">
              <div className="text-[18px] font-semibold text-emerald-400">{formatNumber(nvdProgress.completed)}</div>
              <div className="text-[11px] text-white/40 mt-0.5">Complete</div>
            </div>
            <div className="flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2">
              <div className="text-[18px] font-semibold text-rose-400">{formatNumber(nvdProgress.failed)}</div>
              <div className="text-[11px] text-white/40 mt-0.5">Failed</div>
            </div>
          </div>
        </div>

        {/* Panel 3: Event Log (Full Width) */}
        <div className={`${cardBase} p-6 col-span-2`}>
          <div className="mb-4">
            <div className="text-[12px] uppercase tracking-[0.18em] text-white/30 mb-2">Event Log</div>
            <div className="text-[16px] leading-[20px] font-semibold text-white">
              Real-time Sync Log
            </div>
            <div className="text-[12px] text-white/40 mt-1">
              Событийный лог текущей синхронизации
            </div>
          </div>

          {/* Event Log Container */}
          <div
            ref={eventLogRef}
            className="h-64 max-h-64 overflow-y-auto bg-white/[0.02] border border-white/[0.05] rounded-lg p-3 font-mono text-[11px] leading-relaxed"
          >
            {eventLog && eventLog.length > 0 ? (
              eventLog.map((event, idx) => {
                const timestamp = new Date(event.timestamp).toLocaleTimeString('ru-RU', {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                });
                let stageColor = 'text-white/40';
                if (event.stage === 'FETCHING') stageColor = 'text-blue-400';
                else if (event.stage === 'TRANSLATING') stageColor = 'text-purple-400';
                else if (event.stage === 'EMBEDDING') stageColor = 'text-cyan-400';
                else if (event.stage === 'SUCCESS') stageColor = 'text-emerald-400';
                else if (event.stage === 'ERROR') stageColor = 'text-rose-400';
                else if (event.stage === 'INIT') stageColor = 'text-white/60';

                return (
                  <div key={idx} className="border-b border-white/[0.05] py-1 last:border-b-0">
                    <span className="text-white/30">[{timestamp}]</span>
                    {' '}
                    <span className={stageColor}>{event.stage}</span>
                    {' '}
                    <span className="text-white/70">{event.message}</span>
                  </div>
                );
              })
            ) : (
              <div className="text-white/40 italic">Нет событий</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default NvdSync;
