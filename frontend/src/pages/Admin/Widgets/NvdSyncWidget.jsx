import React, { useMemo } from 'react';

const cardBase = 'bg-white/[0.05] border border-white/[0.08] rounded-[18px]';

const NVD_ACTIVE_STATUSES = new Set(['fetching', 'embedding', 'translating']);

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

  // For partial_success, also calculate translation progress if embedding progress is not available
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

function NvdSyncWidget({ nvdSync, onFetch, isRunning, error }) {
  const nvdStatus = nvdSync?.status || null;
  const nvdProgress = useMemo(() => getNvdProgress(nvdSync), [nvdSync]);
  const isNvdBusy = isRunning || NVD_ACTIVE_STATUSES.has(nvdStatus);

  const nvdStatusLabel = useMemo(() => {
    if (nvdStatus === 'fetching') return 'Получаем CVE из NVD';
    if (nvdStatus === 'translating') return 'Генерируем статьи для KB';
    if (nvdStatus === 'embedding') return 'Считаем embeddings';
    if (nvdStatus === 'failed') return 'Синхронизация завершилась ошибкой';
    if (nvdStatus === 'partial_success') return 'Синхронизация прервана, но данные сохранены';
    if (nvdStatus === 'success' && nvdProgress.total > 0) return 'Embeddings готовы';
    if (nvdStatus === 'success') return 'Синхронизация завершена';
    return 'Нет активной синхронизации';
  }, [nvdProgress.total, nvdStatus]);

  const nvdStatusDetail = useMemo(() => {
    const fetched = Number(nvdSync?.fetched_count || 0);
    const inserted = Number(nvdSync?.last_inserted || 0);
    if (nvdStatus === 'fetching') {
      return 'Читаем страницы NVD и собираем новые CVE за последние 24 часа';
    }
    if (nvdStatus === 'translating') {
      return `Сохранено ${formatNumber(inserted)} новых записей. Генерируем статьи...`;
    }
    if (nvdStatus === 'embedding') {
      return `Обработано ${formatNumber(nvdProgress.processed)} из ${formatNumber(nvdProgress.total)} новых статей`;
    }
    if (nvdStatus === 'failed') {
      return nvdSync?.error || 'Фоновая задача синхронизации упала';
    }
    if (nvdStatus === 'partial_success') {
      const detail = nvdSync?.detailed_status || `CVE сохранены (${formatNumber(inserted)} записей).`;
      const transDone = Number(nvdSync?.translation_completed || 0);
      const transFailed = Number(nvdSync?.translation_failed || 0);
      const embedDone = Number(nvdSync?.embedding_completed || 0);
      const extraParts = [];
      if (transDone > 0) extraParts.push(`статей: ${formatNumber(transDone)}`);
      if (transFailed > 0) extraParts.push(`ошибок перевода: ${formatNumber(transFailed)}`);
      if (embedDone > 0) extraParts.push(`embeddings: ${formatNumber(embedDone)}`);
      return extraParts.length > 0
        ? `${detail} ${extraParts.join(', ')}`
        : detail;
    }
    if (nvdStatus === 'success' && inserted === 0) {
      return fetched > 0
        ? `NVD вернул ${formatNumber(fetched)} записей, новых статей не появилось`
        : 'Новых статей для embeddings не было';
    }
    if (nvdStatus === 'success') {
      const failedPart = nvdProgress.failed > 0 ? `, ошибок: ${formatNumber(nvdProgress.failed)}` : '';
      return `Новых статей: ${formatNumber(inserted)}. Embeddings готовы: ${formatNumber(nvdProgress.completed)}${failedPart}`;
    }
    return 'Нажмите Fetch NVD 24h, чтобы запустить новую синхронизацию';
  }, [nvdProgress.completed, nvdProgress.failed, nvdProgress.processed, nvdProgress.total, nvdStatus, nvdSync]);

  return (
    <div className={`${cardBase} p-6`}>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <div className="text-[18px] leading-[22px] tracking-[0.02em] text-white">
            NVD Sync
          </div>
          <div className="text-[14px] text-white/50 mt-1">
            Синхронизация CVE из National Vulnerability Database
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <button
            type="button"
            onClick={onFetch}
            disabled={isNvdBusy}
            className="h-10 px-4 rounded-[12px] bg-white/10 border border-white/10 text-white/80 text-[14px] tracking-[0.04em] transition-colors duration-200 hover:border-[#9B6BFF]/60 hover:text-white disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isRunning
              ? 'Starting...'
              : nvdStatus === 'fetching'
                ? 'Fetching NVD...'
                : nvdStatus === 'embedding'
                  ? 'Embedding...'
                  : 'Fetch NVD 24h'}
          </button>
          <span className="text-[12px] text-white/40">
            Last run: {formatDateTime(nvdSync?.last_fetch_at)}
          </span>
        </div>
      </div>

      {error && (
        <div className="text-[14px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-[12px] px-4 py-2 mb-4">
          {error}
        </div>
      )}

      <div className="rounded-[14px] border border-white/10 bg-white/[0.04] px-3 py-3">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[12px] uppercase tracking-[0.18em] text-white/45">
            {nvdStatusLabel}
          </span>
          <span className="text-[12px] text-white/60 font-mono-figma">
            {nvdStatus === 'embedding' && nvdProgress.total > 0
              ? `${formatNumber(nvdProgress.processed)} / ${formatNumber(nvdProgress.total)}`
              : nvdStatus === 'translating' && nvdProgress.transTotal > 0
                ? `${formatNumber(nvdProgress.transProcessed)} / ${formatNumber(nvdProgress.transTotal)}`
                : nvdStatus === 'partial_success' && nvdProgress.transTotal > 0
                  ? `${formatNumber(nvdProgress.transProcessed)} / ${formatNumber(nvdProgress.transTotal)} (translation)`
                  : nvdStatus === 'success' && nvdProgress.total > 0
                    ? `${formatNumber(nvdProgress.processed)} / ${formatNumber(nvdProgress.total)}`
                    : '—'}
          </span>
        </div>
        <div className="mt-2 h-2 rounded-full bg-white/10 overflow-hidden">
          {nvdStatus === 'fetching' ? (
            <div className="h-full w-1/3 rounded-full bg-[#9B6BFF]/80 animate-pulse" />
          ) : (
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                nvdStatus === 'failed'
                  ? 'bg-rose-400/80'
                  : nvdStatus === 'partial_success'
                    ? 'bg-amber-300/80'
                    : nvdProgress.failed > 0
                      ? 'bg-amber-300/80'
                      : 'bg-emerald-400/80'
              }`}
              style={{
                width: `${nvdStatus === 'translating' ? nvdProgress.transPercent : nvdProgress.percent}%`,
              }}
            />
          )}
        </div>
        <div className="mt-2 text-[12px] leading-[16px] text-white/55">
          {nvdStatusDetail}
        </div>
      </div>
    </div>
  );
}

export default NvdSyncWidget;
