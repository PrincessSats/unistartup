import React, { useEffect, useMemo, useState } from 'react';
import { ratingsAPI } from '../services/api';

const assets = {
  podiumSecond: 'https://www.figma.com/api/mcp/asset/f1318dcd-ecae-4de1-a32a-341e9b954dd1',
  podiumFirst: 'https://www.figma.com/api/mcp/asset/7131acba-a9db-4608-8b65-83f10d39c2c1',
  podiumThird: 'https://www.figma.com/api/mcp/asset/c0a7fd71-4f66-4992-9ab7-5df21b49bf66',
  podiumBaseTopLeft: 'https://www.figma.com/api/mcp/asset/43f80541-b8d5-4493-9a5a-781fa44dfedf',
  podiumBaseBottomLeft: 'https://www.figma.com/api/mcp/asset/f80d7ca1-7683-4844-a3e9-ea5b6b1ff67a',
  podiumBaseTopCenter: 'https://www.figma.com/api/mcp/asset/b083242b-9367-4958-9ef9-ec679b64f221',
  podiumBaseBottomCenter: 'https://www.figma.com/api/mcp/asset/73605180-5962-48ad-a7cc-fbdce6d2a9ce',
  podiumBaseTopRight: 'https://www.figma.com/api/mcp/asset/6c869ad4-b102-4e0d-b10b-aa31439fba1b',
  podiumBaseBottomRight: 'https://www.figma.com/api/mcp/asset/bbfd0429-14e9-45c1-9808-cbc3a2aba635',
  podiumShelf: 'https://www.figma.com/api/mcp/asset/09ae3d93-d7fa-4bd2-8776-92329daf0629',
  cup: 'https://www.figma.com/api/mcp/asset/87fe4da5-bf19-4aaf-b43c-1191616297ec',
};

const formatNumber = (value) => {
  if (value === null || value === undefined) return '0';
  return new Intl.NumberFormat('ru-RU').format(value);
};

function PodiumCard({ entry, rank, fallbackAvatar, shadowColor, offsetClass }) {
  const avatarUrl = entry?.avatar_url || fallbackAvatar;
  const username = entry?.username || '—';
  const rating = entry?.rating ?? 0;

  return (
    <div className={`flex flex-col items-center gap-4 ${offsetClass}`}>
      <div
        className={`relative h-[116px] w-[116px] overflow-hidden rounded-[24px] border border-white/[0.08] bg-white/[0.03] shadow-[0px_0px_220px_64px_${shadowColor}]`}
      >
        {avatarUrl ? (
          <img
            src={avatarUrl}
            alt={username}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-white/60">
            <svg className="h-10 w-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
        )}
      </div>
      <div className="font-mono-figma text-[23px] leading-[28px] tracking-[0.02em] text-white">
        {username}
      </div>
      <div className="rounded-[16px] bg-white/[0.03] px-8 py-2">
        <span className="font-mono-figma text-[23px] leading-[28px] tracking-[0.02em] text-white">
          {formatNumber(rating)}
        </span>
      </div>
    </div>
  );
}

function PodiumBase({ topImage, bottomImage, heightClass, rank }) {
  return (
    <div className={`relative w-full ${heightClass}`}>
      <div className="absolute inset-0 flex flex-col">
        <img src={topImage} alt="" className="h-[30px] w-full object-cover" />
        <img src={bottomImage} alt="" className="flex-1 w-full object-cover" />
      </div>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[54px] leading-[1.2] tracking-[0.02em] text-white">
          {rank}
        </span>
      </div>
    </div>
  );
}

function Rating() {
  const [kind, setKind] = useState('contest');
  const [period, setPeriod] = useState('all');
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        setError('');
        setLoading(true);
        const data = await ratingsAPI.getLeaderboard(kind);
        setEntries(data?.entries || []);
      } catch (err) {
        setError('Не удалось загрузить рейтинг. Попробуйте позже.');
      } finally {
        setLoading(false);
      }
    };

    fetchLeaderboard();
  }, [kind]);

  const paddedEntries = useMemo(() => {
    const next = [...entries];
    while (next.length < 3) {
      next.push(null);
    }
    return next;
  }, [entries]);

  const [firstEntry, secondEntry, thirdEntry] = paddedEntries;

  const tableColumns =
    'grid min-w-[940px] grid-cols-[82px_minmax(240px,1fr)_66px_148px_148px_148px] items-center';

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 font-sans-figma">
        <div className="text-white/70 text-lg">Загрузка...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 font-sans-figma">
        <div className="text-white/70 text-lg">{error}</div>
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
            <div className="flex items-center gap-2 rounded-[16px] bg-white/[0.03] p-1">
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

        <section className="relative overflow-hidden rounded-[24px] border border-white/[0.09] bg-[#0B0A10]/60 px-8 py-10">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(155,107,255,0.08),_rgba(11,10,16,0)_55%)]" />
          <div className="relative">
            <div className="flex flex-col items-center gap-8 lg:flex-row lg:items-end">
              <div className="flex flex-1 flex-col items-center gap-8 lg:flex-row lg:items-end">
                <div className="flex-1">
                  <PodiumCard
                    entry={secondEntry}
                    rank={2}
                    fallbackAvatar={assets.podiumSecond}
                    shadowColor="rgba(201,204,214,0.16)"
                    offsetClass="pt-8"
                  />
                  <PodiumBase
                    topImage={assets.podiumBaseTopLeft}
                    bottomImage={assets.podiumBaseBottomLeft}
                    heightClass="h-[150px]"
                    rank={2}
                  />
                </div>
                <div className="flex-1">
                  <PodiumCard
                    entry={firstEntry}
                    rank={1}
                    fallbackAvatar={assets.podiumFirst}
                    shadowColor="rgba(242,201,76,0.16)"
                    offsetClass="pt-0"
                  />
                  <PodiumBase
                    topImage={assets.podiumBaseTopCenter}
                    bottomImage={assets.podiumBaseBottomCenter}
                    heightClass="h-[220px]"
                    rank={1}
                  />
                </div>
                <div className="flex-1">
                  <PodiumCard
                    entry={thirdEntry}
                    rank={3}
                    fallbackAvatar={assets.podiumThird}
                    shadowColor="rgba(184,115,51,0.16)"
                    offsetClass="pt-8"
                  />
                  <PodiumBase
                    topImage={assets.podiumBaseTopRight}
                    bottomImage={assets.podiumBaseBottomRight}
                    heightClass="h-[150px]"
                    rank={3}
                  />
                </div>
              </div>
            </div>
            <img
              src={assets.podiumShelf}
              alt=""
              className="pointer-events-none absolute bottom-0 left-1/2 w-full max-w-[1592px] -translate-x-1/2"
            />
          </div>
        </section>

        <section className="rounded-[20px] border border-white/[0.09] bg-white/[0.03] px-8 pb-8 pt-10">
          <div className="overflow-x-auto">
            <div className={`${tableColumns} border-b border-white/[0.09] pb-4 text-[14px] leading-[20px] tracking-[0.04em] text-white/60`}>
              <span className="text-center">Место</span>
              <span>Пользователь</span>
              <span />
              <span className="text-center">Очки</span>
              <span className="text-center">Собрано флагов</span>
              <span className="text-center">First blood</span>
            </div>
            <div className="mt-2 flex max-h-[880px] flex-col gap-2 overflow-y-auto pr-2">
              {entries.length === 0 && (
                <div className="py-12 text-center text-white/60">
                  Пока нет данных для отображения рейтинга.
                </div>
              )}
              {entries.map((entry) => {
                const showCup = entry.first_blood > 0;
                const isCurrent = entry.is_current_user;
                return (
                  <div
                    key={entry.user_id}
                    className={`${tableColumns} rounded-[16px] border border-white/[0.08] bg-white/[0.02] px-4 py-3 text-[18px] leading-[24px] tracking-[0.04em] ${
                      isCurrent ? 'sticky bottom-8 z-10 border-[#9B6BFF]/40 bg-[#1A1426]' : ''
                    }`}
                  >
                    <span className="text-center text-white/80">{entry.rank}</span>
                    <div className="flex items-center gap-4 min-w-0">
                      <div className="h-14 w-14 overflow-hidden rounded-[10px] bg-white/[0.05]">
                        {entry.avatar_url ? (
                          <img src={entry.avatar_url} alt={entry.username} className="h-full w-full object-cover" />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-white/60">
                            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                            </svg>
                          </div>
                        )}
                      </div>
                      <span className="font-mono-figma truncate text-white">
                        {entry.username}
                      </span>
                    </div>
                    <div className="flex items-center justify-center">
                      {showCup && <img src={assets.cup} alt="" className="h-5 w-5" />}
                    </div>
                    <span className="font-mono-figma text-center text-white">
                      {formatNumber(entry.rating)}
                    </span>
                    <span className="text-center text-white/90">
                      {formatNumber(entry.solved)}
                    </span>
                    <span className="text-center text-white/90">
                      {formatNumber(entry.first_blood)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default Rating;
