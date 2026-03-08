import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ratingsAPI, authAPI } from '../services/api';
import AppIcon from '../components/AppIcon';
import { PageLoader } from '../components/LoadingState';

const TABLE_COLUMNS =
  'grid min-w-[1050px] grid-cols-[82px_minmax(280px,1fr)_66px_148px_148px_148px] items-center';

const PODIUM_ORDER = [2, 1, 3];

const PODIUM_TONES = {
  1: {
    glow: 'shadow-[0_0_220px_64px_rgba(242,201,76,0.16)]',
    pedestalHeight: 'h-[190px]',
    offsetClass: '',
  },
  2: {
    glow: 'shadow-[0_0_220px_64px_rgba(201,204,214,0.16)]',
    pedestalHeight: 'h-[120px]',
    offsetClass: 'pt-[70px]',
  },
  3: {
    glow: 'shadow-[0_0_220px_64px_rgba(184,115,51,0.16)]',
    pedestalHeight: 'h-[120px]',
    offsetClass: 'pt-[70px]',
  },
};

const formatNumber = (value) => {
  if (value === null || value === undefined) return '0';
  return new Intl.NumberFormat('ru-RU').format(value);
};

function UserAvatar({
  entry,
  sizeClass = 'h-14 w-14',
  roundedClass = 'rounded-[10px]',
  iconClass = 'h-5 w-5',
  borderClass = 'border-white/[0.09]',
}) {
  const username = entry?.username || '—';

  return (
    <div
      className={`${sizeClass} ${roundedClass} relative shrink-0 overflow-hidden border ${borderClass} bg-white/[0.03]`}
    >
      {entry?.avatar_url ? (
        <img src={entry.avatar_url} alt={username} className="h-full w-full object-cover" loading="lazy" />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-[#9B6BFF] text-white">
          <AppIcon name="person" className={iconClass} />
        </div>
      )}
    </div>
  );
}

function PodiumColumn({ entry, rank }) {
  const tone = PODIUM_TONES[rank] || PODIUM_TONES[2];
  const username = entry?.username || '—';

  return (
    <article
      className={`relative flex min-w-[320px] flex-1 flex-col items-center justify-end ${tone.offsetClass}`}
    >
      <div className="relative z-[2] mb-6 flex flex-col items-center gap-4">
        <div className={`relative overflow-hidden rounded-[24px] ${tone.glow}`}>
          <UserAvatar
            entry={entry}
            sizeClass="h-[116px] w-[116px]"
            roundedClass="rounded-[24px]"
            iconClass="h-6 w-6"
            borderClass="border-transparent"
          />
        </div>

        <p className="max-w-[157px] truncate text-center font-mono-figma text-[23px] leading-[28px] tracking-[0.02em] text-white">
          {username}
        </p>

        <div className="rounded-[16px] bg-white/[0.03] px-8 py-[10px]">
          <span className="font-mono-figma text-[23px] leading-[28px] tracking-[0.02em] text-white">
            {formatNumber(entry?.rating)}
          </span>
        </div>
      </div>

      <div className="relative w-full overflow-hidden">
        <div
          className="h-[30px] w-full bg-[linear-gradient(180deg,rgba(32,33,47,0.75)_0%,rgba(19,21,34,0.95)_100%)]"
          style={{ clipPath: 'polygon(0% 100%, 8% 0%, 92% 0%, 100% 100%)' }}
        />
        <div
          className={`relative w-full ${tone.pedestalHeight} bg-[linear-gradient(180deg,rgba(12,13,24,0.96)_0%,rgba(11,10,16,1)_100%)]`}
        >
          <span className="absolute inset-0 flex items-center justify-center text-[54px] font-medium leading-[1.2] tracking-[0.02em] text-white">
            {rank}
          </span>
        </div>
      </div>
    </article>
  );
}

function LeaderboardRow({ entry, className = '', attachRef }) {
  const showCup = Number(entry?.first_blood || 0) > 0;

  return (
    <div
      ref={attachRef}
      className={`${TABLE_COLUMNS} min-h-[88px] rounded-[20px] border-b border-white/[0.09] px-4 py-4 ${className}`}
    >
      <span className="text-center text-[18px] leading-[24px] tracking-[0.04em] text-white">
        {entry?.rank ?? '—'}
      </span>

      <div className="flex min-w-0 items-center gap-4">
        <UserAvatar entry={entry} sizeClass="h-14 w-14" roundedClass="rounded-[10px]" iconClass="h-[22px] w-[22px]" />
        <span className="truncate font-mono-figma text-[18px] leading-[24px] tracking-[0.02em] text-white">
          {entry?.username || '—'}
        </span>
      </div>

      <div className="flex items-center justify-center">
        {showCup ? <AppIcon name="cup" className="h-6 w-6 text-[#9B6BFF]" /> : null}
      </div>

      <span className="text-center font-mono-figma text-[23px] leading-[28px] tracking-[0.02em] text-white">
        {formatNumber(entry?.rating)}
      </span>

      <span className="text-center text-[18px] leading-[24px] tracking-[0.04em] text-white">
        {formatNumber(entry?.solved)}
      </span>

      <span className="text-center text-[18px] leading-[24px] tracking-[0.04em] text-white">
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
      } catch (_err) {
        if (_err?.response?.status === 401 && !authAPI.isAuthenticated()) {
          setEntries([]);
        } else {
          setError('Не удалось загрузить рейтинг. Попробуйте позже.');
        }
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

  const podiumEntriesByRank = useMemo(() => {
    const byRank = new Map();

    sortedEntries.forEach((entry) => {
      const rank = Number(entry?.rank);
      if (Number.isFinite(rank) && !byRank.has(rank)) {
        byRank.set(rank, entry);
      }
    });

    const fallback = {
      1: sortedEntries[0] || null,
      2: sortedEntries[1] || sortedEntries[0] || null,
      3: sortedEntries[2] || sortedEntries[1] || sortedEntries[0] || null,
    };

    return {
      1: byRank.get(1) || fallback[1],
      2: byRank.get(2) || fallback[2],
      3: byRank.get(3) || fallback[3],
    };
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
    Boolean(currentEntry) && Number(currentEntry?.rank) > 10 && !isCurrentRowVisible;

  if (loading) {
    return <PageLoader label="Загружаем рейтинг..." variant="rating" />;
  }

  if (error) {
    return (
      <div className="flex h-64 items-center justify-center font-sans-figma">
        <div className="text-lg text-white/70">{error}</div>
      </div>
    );
  }

  return (
    <div className="relative font-sans-figma text-white">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_50%_24%,rgba(120,98,255,0.16),transparent_37%),radial-gradient(circle_at_17%_30%,rgba(92,123,255,0.10),transparent_28%),radial-gradient(circle_at_83%_31%,rgba(255,164,99,0.09),transparent_28%)]" />

      <div className="flex w-full flex-col gap-8">
        <div className="flex flex-col gap-5">
          <h1 className="text-[36px] font-medium leading-[44px] tracking-[0.02em]">Рейтинг</h1>

          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div className="relative h-14 w-full max-w-[342px]">
              <select
                value={period}
                onChange={(event) => setPeriod(event.target.value)}
                className="h-full w-full appearance-none rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 pr-10 text-[16px] leading-[20px] tracking-[0.04em] text-white/60 outline-none focus:border-white/20"
              >
                <option value="all">Период</option>
                <option value="week">Последняя неделя</option>
                <option value="month">Последний месяц</option>
              </select>

              <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-white/60">
                <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2.5 4.5 6 8l3.5-3.5" />
                </svg>
              </span>
            </div>

            <div className="flex items-center gap-1 rounded-[16px]">
              <button
                onClick={() => setKind('contest')}
                className={`rounded-[10px] px-6 py-4 text-[18px] leading-[24px] tracking-[0.04em] transition-colors ${
                  kind === 'contest'
                    ? 'bg-white/[0.03] text-[#9B6BFF]'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                Чемпионат
              </button>

              <button
                onClick={() => setKind('practice')}
                className={`rounded-[10px] px-6 py-4 text-[18px] leading-[24px] tracking-[0.04em] transition-colors ${
                  kind === 'practice'
                    ? 'bg-white/[0.03] text-[#9B6BFF]'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                Обучение
              </button>
            </div>
          </div>
        </div>

        <section className="relative overflow-hidden rounded-[20px]">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_30%,rgba(242,201,76,0.08),transparent_26%),radial-gradient(circle_at_18%_38%,rgba(155,107,255,0.09),transparent_30%),radial-gradient(circle_at_82%_38%,rgba(184,115,51,0.09),transparent_30%)]" />

          <div className="relative flex min-h-[480px] items-end overflow-x-auto">
            {PODIUM_ORDER.map((rank) => (
              <PodiumColumn
                key={rank}
                rank={rank}
                entry={podiumEntriesByRank[rank]}
              />
            ))}
          </div>

          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[62px] bg-[radial-gradient(85%_120%_at_50%_0%,rgba(255,255,255,0.12),rgba(255,255,255,0))]" />
        </section>

        <section className="relative mx-auto w-full max-w-[1114px] rounded-[20px] bg-white/[0.03] pb-8 pt-12">
          <div className="overflow-x-auto px-8">
            <div className="min-w-[1050px]">
              <div className={`${TABLE_COLUMNS} rounded-[20px] px-4 py-[10px] text-[16px] leading-[20px] tracking-[0.04em] text-white/60`}>
                <span className="text-center">Место</span>
                <span>Пользователь</span>
                <span />
                <span className="text-center">Очки</span>
                <span className="text-center">Собрано флагов</span>
                <span className="text-center">First blood</span>
              </div>

              <div
                ref={scrollContainerRef}
                className={`mt-4 max-h-[880px] overflow-y-auto pr-1 ${
                  shouldPinCurrentRow ? 'pb-[120px]' : ''
                }`}
              >
                {sortedEntries.length === 0 ? (
                  <div className="py-12 text-center text-white/60">
                    Пока нет данных для отображения рейтинга.
                  </div>
                ) : (
                  sortedEntries.map((entry, index) => {
                    const isCurrent = Boolean(entry?.is_current_user);
                    const baseClass = isCurrent
                      ? 'bg-[linear-gradient(90deg,rgba(155,107,255,0.18),rgba(155,107,255,0.08))]'
                      : '';

                    return (
                      <LeaderboardRow
                        key={entry?.user_id ?? `${entry?.rank}-${entry?.username}-${index}`}
                        entry={entry}
                        attachRef={isCurrent ? currentRowRef : undefined}
                        className={baseClass}
                      />
                    );
                  })
                )}
              </div>
            </div>
          </div>

          {shouldPinCurrentRow && currentEntry ? (
            <div className="pointer-events-none absolute inset-x-8 bottom-8 hidden lg:block">
              <LeaderboardRow
                entry={currentEntry}
                className="pointer-events-auto border border-[#9B6BFF]/35 bg-[linear-gradient(90deg,rgba(155,107,255,0.32),rgba(155,107,255,0.16))] shadow-[0_16px_50px_rgba(11,10,16,0.56)]"
              />
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

export default Rating;
