import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ratingsAPI } from '../services/api';
import AppIcon from '../components/AppIcon';

const tableColumns =
  'grid min-w-[940px] grid-cols-[82px_minmax(260px,1fr)_66px_126px_148px_148px] items-center';

const formatNumber = (value) => {
  if (value === null || value === undefined) return '0';
  return new Intl.NumberFormat('ru-RU').format(value);
};

function UserAvatar({ entry, sizeClass = 'h-14 w-14', roundedClass = 'rounded-[12px]' }) {
  const username = entry?.username || '—';

  return (
    <div
      className={`${sizeClass} ${roundedClass} overflow-hidden border border-white/[0.12] bg-white/[0.04] shrink-0`}
    >
      {entry?.avatar_url ? (
        <img src={entry.avatar_url} alt={username} className="h-full w-full object-cover" />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-[#9B6BFF]/85 text-white">
          <AppIcon name="person" className="h-4 w-4" />
        </div>
      )}
    </div>
  );
}

function TopPlayerCard({ entry, rank }) {
  const rankTones = {
    1: {
      border: 'border-[#E6C36E]/70',
      shadow: 'shadow-[0_0_130px_-44px_rgba(230,195,110,0.58)]',
    },
    2: {
      border: 'border-[#9B6BFF]/45',
      shadow: 'shadow-[0_0_130px_-44px_rgba(155,107,255,0.52)]',
    },
    3: {
      border: 'border-[#CE8358]/55',
      shadow: 'shadow-[0_0_130px_-44px_rgba(206,131,88,0.52)]',
    },
  };

  const tone = rankTones[rank] || rankTones[2];
  const username = entry?.username || '—';
  const rating = entry?.rating ?? 0;

  return (
    <article
      className={`relative flex min-h-[210px] flex-col items-center justify-center gap-4 rounded-[16px] border bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.08),_rgba(255,255,255,0.01)_46%,_rgba(255,255,255,0.01))] px-6 py-8 ${tone.border} ${tone.shadow}`}
    >
      <UserAvatar
        entry={entry}
        sizeClass="h-[88px] w-[88px]"
        roundedClass={`rounded-[18px] ${rank === 1 ? 'border-[#E6C36E]' : ''}`}
      />
      <div className="font-mono-figma text-[29px] leading-[36px] tracking-[0.58px] text-white">
        {username}
      </div>
      <div className="rounded-[10px] border border-white/[0.08] bg-white/[0.03] px-5 py-2">
        <span className="font-mono-figma text-[29px] leading-[36px] tracking-[0.58px] text-white">
          {formatNumber(rating)}
        </span>
      </div>
    </article>
  );
}

function LeaderboardRow({ entry, className, attachRef }) {
  const showCup = Number(entry?.first_blood || 0) > 0;

  return (
    <div ref={attachRef} className={`${tableColumns} ${className}`}>
      <span className="text-center text-white">{entry?.rank ?? '—'}</span>
      <div className="flex min-w-0 items-center gap-4">
        <UserAvatar entry={entry} sizeClass="h-8 w-8" roundedClass="rounded-[8px]" />
        <span className="truncate font-mono-figma text-[18px] leading-[1.2] tracking-[0.02em] text-white">
          {entry?.username || '—'}
        </span>
      </div>
      <div className="flex items-center justify-center">
        {showCup ? <AppIcon name="cup" className="h-5 w-5 text-[#9B6BFF]" /> : null}
      </div>
      <span className="text-center font-mono-figma text-[23px] leading-[1.2] tracking-[0.02em] text-white">
        {formatNumber(entry?.rating)}
      </span>
      <span className="text-center text-[18px] leading-[1.2] tracking-[0.02em] text-white">
        {formatNumber(entry?.solved)}
      </span>
      <span className="text-center text-[18px] leading-[1.2] tracking-[0.02em] text-white">
        {formatNumber(entry?.first_blood)}
      </span>
    </div>
  );
}

function Rating() {
  const [kind, setKind] = useState('contest');
  const [period, setPeriod] = useState('all');
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isCurrentRowVisible, setIsCurrentRowVisible] = useState(false);
  const scrollContainerRef = useRef(null);
  const currentRowRef = useRef(null);

  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        setError('');
        setLoading(true);
        const data = await ratingsAPI.getLeaderboard(kind);
        setEntries(Array.isArray(data?.entries) ? data.entries : []);
      } catch (err) {
        setError('Не удалось загрузить рейтинг. Попробуйте позже.');
      } finally {
        setLoading(false);
      }
    };

    fetchLeaderboard();
  }, [kind]);

  const sortedEntries = useMemo(() => {
    return [...entries].sort((left, right) => {
      const leftRank = Number(left?.rank ?? Number.MAX_SAFE_INTEGER);
      const rightRank = Number(right?.rank ?? Number.MAX_SAFE_INTEGER);
      return leftRank - rightRank;
    });
  }, [entries]);

  const podiumEntries = useMemo(() => {
    const byRank = new Map();
    sortedEntries.forEach((entry) => {
      const rank = Number(entry?.rank);
      if (Number.isFinite(rank) && !byRank.has(rank)) {
        byRank.set(rank, entry);
      }
    });

    const selected = [1, 2, 3].map((rank) => byRank.get(rank) || null);
    if (selected.some((item) => !item)) {
      return [
        sortedEntries[0] || null,
        sortedEntries[1] || null,
        sortedEntries[2] || null,
      ];
    }
    return selected;
  }, [sortedEntries]);

  const currentEntry = useMemo(
    () => sortedEntries.find((entry) => entry?.is_current_user) || null,
    [sortedEntries]
  );

  useEffect(() => {
    const root = scrollContainerRef.current;
    const target = currentRowRef.current;

    if (!root || !target) {
      setIsCurrentRowVisible(false);
      return undefined;
    }

    const observer = new IntersectionObserver(
      ([observerEntry]) => {
        setIsCurrentRowVisible(Boolean(observerEntry?.isIntersecting));
      },
      { root, threshold: 0.6 }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [sortedEntries, currentEntry?.user_id]);

  const shouldPinCurrentRow =
    Boolean(currentEntry) &&
    Number(currentEntry?.rank) > 10 &&
    !isCurrentRowVisible;

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center font-sans-figma">
        <div className="text-lg text-white/70">Загрузка...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center font-sans-figma">
        <div className="text-lg text-white/70">{error}</div>
      </div>
    );
  }

  return (
    <div className="font-sans-figma text-white">
      <div className="flex flex-col gap-8">
        <div className="flex flex-col gap-5">
          <h1 className="text-[36px] leading-[44px] tracking-[0.02em] font-medium">
            Рейтинг
          </h1>
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-14 items-center gap-3 rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4">
                <select
                  value={period}
                  onChange={(event) => setPeriod(event.target.value)}
                  className="h-full bg-transparent text-[16px] leading-[20px] tracking-[0.04em] text-white/70 focus:outline-none"
                >
                  <option value="all">Период</option>
                  <option value="week">Последняя неделя</option>
                  <option value="month">Последний месяц</option>
                </select>
              </div>
            </div>
            <div className="flex items-center gap-2 rounded-[12px] bg-white/[0.03] p-1">
              <button
                onClick={() => setKind('contest')}
                className={`rounded-[10px] px-5 py-3 text-[16px] leading-[20px] tracking-[0.04em] transition-colors ${
                  kind === 'contest'
                    ? 'bg-[#9B6BFF] text-white'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                Чемпионат
              </button>
              <button
                onClick={() => setKind('practice')}
                className={`rounded-[10px] px-5 py-3 text-[16px] leading-[20px] tracking-[0.04em] transition-colors ${
                  kind === 'practice'
                    ? 'bg-[#9B6BFF] text-white'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                Обучение
              </button>
            </div>
          </div>
        </div>

        <section className="rounded-[20px] border border-white/[0.09] bg-white/[0.02] p-4 sm:p-6">
          <div className="grid gap-4 lg:grid-cols-3">
            <TopPlayerCard entry={podiumEntries[0]} rank={1} />
            <TopPlayerCard entry={podiumEntries[1]} rank={2} />
            <TopPlayerCard entry={podiumEntries[2]} rank={3} />
          </div>
        </section>

        <section className="relative mx-auto w-full max-w-[1074px] overflow-hidden rounded-[20px] border border-white/[0.09] bg-white/[0.03]">
          <div className="px-4 pb-4 pt-5 sm:px-6">
            <div
              className={`${tableColumns} border-b border-white/[0.09] pb-4 text-[14px] leading-[20px] tracking-[0.04em] text-white/60`}
            >
              <span className="text-center">Место</span>
              <span>Пользователь</span>
              <span />
              <span className="text-center">Рейтинг</span>
              <span className="text-center">Собрано флагов</span>
              <span className="text-center">Первая кровь</span>
            </div>

            <div
              ref={scrollContainerRef}
              className={`mt-2 flex max-h-[860px] flex-col gap-0.5 overflow-y-auto pr-1 ${
                shouldPinCurrentRow ? 'pb-[98px]' : ''
              }`}
            >
              {sortedEntries.length === 0 && (
                <div className="py-12 text-center text-white/60">
                  Пока нет данных для отображения рейтинга.
                </div>
              )}

              {sortedEntries.map((entry, index) => {
                const isCurrent = Boolean(entry?.is_current_user);
                const zebraClass = index % 2 === 0 ? 'bg-white/[0.02]' : 'bg-white/[0.045]';
                return (
                  <LeaderboardRow
                    key={entry?.user_id ?? `${entry?.rank}-${entry?.username}-${index}`}
                    entry={entry}
                    attachRef={isCurrent ? currentRowRef : undefined}
                    className={`rounded-[12px] border border-transparent px-4 py-3 ${zebraClass}`}
                  />
                );
              })}
            </div>
          </div>

          {shouldPinCurrentRow && currentEntry && (
            <div className="pointer-events-none absolute inset-x-0 bottom-0 border-t border-[#9B6BFF] bg-[#0F0F18]/95 px-4 py-3 backdrop-blur-[64px] sm:px-6">
              <LeaderboardRow
                entry={currentEntry}
                className="pointer-events-auto rounded-[12px] border border-[#9B6BFF]/35 bg-black/20 px-4 py-3"
              />
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default Rating;
