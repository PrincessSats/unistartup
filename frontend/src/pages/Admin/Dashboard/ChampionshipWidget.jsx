import React, { useMemo } from 'react';
import SectionCard from '../Widgets/SectionCard';

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' });
}

function ChampionshipWidget({ contest, submissions }) {
  const contestStatus = useMemo(() => {
    if (!contest) {
      return { label: 'Нет данных', tone: 'bg-white/10 text-white/70' };
    }
    const now = Date.now();
    const start = new Date(contest.start_at).getTime();
    const end = new Date(contest.end_at).getTime();
    if (Number.isNaN(start) || Number.isNaN(end)) {
      return { label: 'Неизвестно', tone: 'bg-white/10 text-white/70' };
    }
    if (now < start) {
      return { label: 'Скоро', tone: 'bg-[#9B6BFF]/20 text-[#CBB6FF]' };
    }
    if (now > end) {
      return { label: 'Завершен', tone: 'bg-white/10 text-white/70' };
    }
    return { label: 'Активен', tone: 'bg-emerald-500/20 text-emerald-300' };
  }, [contest]);

  return (
    <SectionCard
      title="Текущий чемпионат"
      subtitle={contest?.title || 'Нет активного чемпионата'}
      action={(
        <span className={`text-[12px] uppercase tracking-[0.24em] px-3 py-1 rounded-full ${contestStatus.tone}`}>
          {contestStatus.label}
        </span>
      )}
    >
      <div className="flex flex-col gap-3 text-[14px] text-white/70">
        <div className="flex items-center justify-between">
          <span className="text-white/50">Даты проведения</span>
          <span className="text-white">
            {contest ? `${formatDate(contest.start_at)} — ${formatDate(contest.end_at)}` : '—'}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-white/50">Сабмиты</span>
          <span className="text-white">
            {formatNumber(submissions)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-white/50">Публичный</span>
          <span className="text-white">
            {contest ? (contest.is_public ? 'Да' : 'Нет') : '—'}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-white/50">Лидерборд</span>
          <span className="text-white">
            {contest ? (contest.leaderboard_visible ? 'Виден' : 'Скрыт') : '—'}
          </span>
        </div>
      </div>
    </SectionCard>
  );
}

function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  if (Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('ru-RU');
}

export default ChampionshipWidget;
