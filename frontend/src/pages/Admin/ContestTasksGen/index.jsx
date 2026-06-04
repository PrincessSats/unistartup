import React, { useMemo, useState } from 'react';
import useContestTaskGen from './useContestTaskGen';

const initialForm = {
  count: 3,
  base_difficulty: 8,
};

const CATEGORY_LABELS = {
  web: 'web', pwn: 'pwn', crypto: 'crypto', re: 're', forensics: 'forensics',
  misc: 'misc', osint: 'osint', mobile: 'mobile', hardware: 'hardware', cloud: 'cloud',
};

function StatusDot({ status }) {
  if (status === 'done') {
    return <span className="flex h-6 w-6 items-center justify-center rounded-full bg-green-500/20 text-green-400">✓</span>;
  }
  if (status === 'failed') {
    return <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-500/20 text-red-400">✕</span>;
  }
  if (status === 'generating') {
    return (
      <span className="flex h-6 w-6 items-center justify-center">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#9B6BFF] border-t-transparent" />
      </span>
    );
  }
  return <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-700 text-slate-500 text-xs">•</span>;
}

function TaskRow({ event, index }) {
  const status = event?.status || 'queued';
  const labels = {
    queued: 'В очереди',
    generating: 'Генерация…',
    done: event?.title || 'Готово',
    failed: event?.error || 'Ошибка',
  };
  return (
    <div
      className={`flex items-center gap-3 rounded-lg border p-3 transition-all duration-300 ${
        status === 'done'
          ? 'border-green-700/40 bg-green-900/10'
          : status === 'failed'
          ? 'border-red-700/40 bg-red-900/10'
          : status === 'generating'
          ? 'border-[#9B6BFF]/40 bg-[#9B6BFF]/5'
          : 'border-slate-700 bg-slate-800/40'
      }`}
    >
      <div className="text-slate-500 text-sm font-mono w-6 shrink-0">#{index + 1}</div>
      <StatusDot status={status} />
      <div className="min-w-0 flex-1">
        <div className={`truncate text-sm ${status === 'failed' ? 'text-red-300' : 'text-white'}`}>
          {labels[status]}
        </div>
        {status === 'generating' && (
          <div className="mt-2 h-2 w-1/2 animate-pulse rounded bg-white/10" />
        )}
      </div>
      {status === 'done' && event?.category && (
        <span className="shrink-0 rounded-md bg-[#9B6BFF]/20 px-2 py-1 text-xs text-[#c4a4ff]">
          {CATEGORY_LABELS[event.category] || event.category}
        </span>
      )}
    </div>
  );
}

export default function ContestTasksGen() {
  const [form, setForm] = useState(initialForm);
  const { job, isRunning, starting, error, start } = useContestTaskGen();

  const setField = (key) => (e) => setForm((p) => ({ ...p, [key]: e.target.value }));

  const handleStart = () => {
    start({
      count: Number(form.count) || 1,
      mode: 'filter',
      base_difficulty: Number(form.base_difficulty) || 8,
    });
  };

  const total = job?.total || 0;
  const done = (job?.completed || 0) + (job?.failed || 0);
  const pct = total ? Math.round((done / total) * 100) : 0;

  // Build a stable list of `total` slots, filling from job.events.
  const slots = useMemo(() => {
    const events = job?.events || [];
    if (!total) return events;
    const arr = [];
    for (let i = 0; i < total; i += 1) {
      arr.push(events[i] || { index: i, status: 'queued' });
    }
    return arr;
  }, [job, total]);

  return (
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">Генерация контестных задач</h1>
          <p className="mt-1 text-slate-400">
            Выберите количество и сложность — остальное на автопилоте.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Левая карточка — форма */}
          <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-6">
            <h2 className="mb-4 text-lg font-semibold text-white">Параметры</h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-sm text-slate-400">Количество (1–5)</label>
                <input
                  type="number" min="1" max="5" value={form.count} onChange={setField('count')}
                  disabled={isRunning || starting}
                  className="h-10 w-full rounded-lg border border-slate-600 bg-slate-800 px-3 text-white focus:border-[#9B6BFF] focus:outline-none disabled:opacity-50"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-slate-400">Сложность (7–10)</label>
                <input
                  type="number" min="7" max="10" value={form.base_difficulty} onChange={setField('base_difficulty')}
                  disabled={isRunning || starting}
                  className="h-10 w-full rounded-lg border border-slate-600 bg-slate-800 px-3 text-white focus:border-[#9B6BFF] focus:outline-none disabled:opacity-50"
                />
              </div>
            </div>

            <p className="mt-4 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-xs text-slate-400">
              Остальное — на автопилоте: CVE подбираются автоматически, темы задач не повторяются.
            </p>

            {error && (
              <div className="mt-4 rounded-lg border border-red-700 bg-red-900/30 px-3 py-2 text-sm text-red-200">
                {error}
              </div>
            )}

            <button
              type="button" onClick={handleStart} disabled={isRunning || starting}
              className="mt-6 h-12 w-full rounded-lg bg-[#9B6BFF] font-medium text-white transition hover:bg-[#8452FF] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {starting ? 'Запуск…' : isRunning ? 'Генерация идёт…' : 'Генерировать'}
            </button>
          </div>

          {/* Правая карточка — прогресс */}
          <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Прогресс</h2>
              {job && (
                <span className="text-sm text-slate-400">
                  {done} из {total || '—'} готово
                </span>
              )}
            </div>

            {!job ? (
              <div className="flex h-48 items-center justify-center text-center text-slate-500">
                Задайте параметры и нажмите «Генерировать» —<br />задачи появятся здесь в реальном времени.
              </div>
            ) : (
              <>
                <div className="mb-4 h-2 w-full overflow-hidden rounded-full bg-slate-700">
                  <div
                    className="h-full rounded-full bg-[#9B6BFF] transition-all duration-500"
                    style={{ width: `${pct}%` }}
                  />
                </div>

                {total === 0 && isRunning && (
                  <div className="mb-3 text-sm text-slate-400">Подбор CVE-кластеров…</div>
                )}

                <div className="space-y-2">
                  {slots.map((event, i) => (
                    <TaskRow key={i} event={event} index={i} />
                  ))}
                </div>

                {!isRunning && job.status === 'completed' && (
                  <div className="mt-4 rounded-lg border border-green-700/50 bg-green-900/20 px-4 py-3 text-sm text-green-200">
                    Готово. Создано задач: {job.created_task_ids?.length || 0}
                    {job.failed ? `, ошибок: ${job.failed}` : ''}. Задачи в черновиках — опубликуйте
                    их в управлении задачами, чтобы добавить в чемпионат.
                  </div>
                )}
                {!isRunning && job.status === 'failed' && (
                  <div className="mt-4 rounded-lg border border-red-700/50 bg-red-900/20 px-4 py-3 text-sm text-red-200">
                    {job.error || 'Генерация завершилась с ошибкой.'}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
