import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { contestAPI } from '../services/api';

const formatDate = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const formatted = new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
  return formatted.replace('.', '');
};

const formatDaysLeft = (daysLeft) => {
  if (daysLeft <= 0) return 'Срок завершен';
  const mod10 = daysLeft % 10;
  const mod100 = daysLeft % 100;
  let noun = 'дней';
  if (mod10 === 1 && mod100 !== 11) noun = 'день';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) noun = 'дня';
  return `Осталось ${daysLeft} ${noun}`;
};

const formatDateTime = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

function Championship() {
  const [contest, setContest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [joined, setJoined] = useState(false);
  const [contestInactive, setContestInactive] = useState(false);
  const [taskState, setTaskState] = useState(null);
  const [flagValues, setFlagValues] = useState({});
  const [submittingFlagId, setSubmittingFlagId] = useState(null);
  const [submitMessage, setSubmitMessage] = useState('');
  const [activeTab, setActiveTab] = useState('description');
  const [leaderboardRows, setLeaderboardRows] = useState([]);
  const [leaderboardMe, setLeaderboardMe] = useState(null);
  const [leaderboardLoading, setLeaderboardLoading] = useState(false);
  const [leaderboardError, setLeaderboardError] = useState('');
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailsItems, setDetailsItems] = useState([]);
  const [detailsTotal, setDetailsTotal] = useState(0);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState('');
  const leaderboardScrollRef = useRef(null);
  const leaderboardMyRowRef = useRef(null);
  const [isMyRowVisible, setIsMyRowVisible] = useState(false);

  useEffect(() => {
    const fetchContest = async () => {
      try {
        setError('');
        const data = await contestAPI.getActiveContest();
        setContest(data);
        setContestInactive(false);
        if (data?.id) {
          try {
            const current = await contestAPI.getCurrentTask(data.id);
            setTaskState(current);
            setJoined(true);
          } catch (err) {
            if (err?.response?.status === 400) {
              setContestInactive(true);
              setJoined(false);
              setTaskState(null);
            } else if (err?.response?.status === 403) {
              setJoined(false);
            } else {
              setError('Не удалось загрузить текущую задачу.');
            }
          }
        }
      } catch (err) {
        setError('Не удалось загрузить чемпионат. Попробуйте позже.');
      } finally {
        setLoading(false);
      }
    };

    fetchContest();
  }, []);

  const refreshLeaderboard = useCallback(async (contestId) => {
    if (!contestId) return;
    setLeaderboardLoading(true);
    setLeaderboardError('');
    try {
      const data = await contestAPI.getLeaderboard(contestId);
      setLeaderboardRows(data?.rows || []);
      setLeaderboardMe(data?.me || null);
    } catch (err) {
      setLeaderboardRows([]);
      setLeaderboardMe(null);
      const detail = err?.response?.data?.detail;
      setLeaderboardError(typeof detail === 'string' ? detail : 'Не удалось загрузить итоги контеста.');
    } finally {
      setLeaderboardLoading(false);
    }
  }, []);

  const refreshMyResults = useCallback(async (contestId) => {
    if (!contestId) return;
    setDetailsLoading(true);
    setDetailsError('');
    try {
      const data = await contestAPI.getMyResults(contestId);
      setDetailsItems(data?.items || []);
      setDetailsTotal(data?.total_points || 0);
    } catch (err) {
      setDetailsItems([]);
      setDetailsTotal(0);
      const detail = err?.response?.data?.detail;
      setDetailsError(typeof detail === 'string' ? detail : 'Не удалось загрузить детализацию.');
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab !== 'results' || !contest?.id || contestInactive) return;
    refreshLeaderboard(contest.id);
  }, [activeTab, contest?.id, contestInactive, refreshLeaderboard]);

  useEffect(() => {
    if (!detailsOpen || !contest?.id || contestInactive) return;
    refreshMyResults(contest.id);
  }, [detailsOpen, contest?.id, contestInactive, refreshMyResults]);

  useEffect(() => {
    if (activeTab !== 'results') {
      setIsMyRowVisible(false);
      return;
    }
    const root = leaderboardScrollRef.current;
    const target = leaderboardMyRowRef.current;
    if (!root || !target) {
      setIsMyRowVisible(false);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => setIsMyRowVisible(entry.isIntersecting),
      { root, threshold: 0.35 },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [activeTab, leaderboardRows]);

  const daysLeftLabel = useMemo(() => {
    return formatDaysLeft(contest?.days_left ?? 0);
  }, [contest?.days_left]);

  const startLabel = useMemo(() => formatDate(contest?.start_at), [contest?.start_at]);
  const endLabel = useMemo(() => formatDate(contest?.end_at), [contest?.end_at]);

  const tasksTotal = taskState?.tasks_total ?? contest?.tasks_total ?? 0;
  const tasksSolved = taskState?.solved_task_ids?.length ?? contest?.tasks_solved ?? 0;
  const taskProgressPercent = tasksTotal ? Math.round((tasksSolved / tasksTotal) * 100) : 0;
  const deadlineProgressPercent = useMemo(() => {
    const start = contest?.start_at ? new Date(contest.start_at).getTime() : NaN;
    const end = contest?.end_at ? new Date(contest.end_at).getTime() : NaN;
    if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return 0;
    const now = Date.now();
    const ratio = (now - start) / (end - start);
    const percent = Math.round(ratio * 100);
    return Math.min(100, Math.max(0, percent));
  }, [contest?.start_at, contest?.end_at]);

  const currentTask = taskState?.task;
  const requiredFlags = useMemo(() => {
    return currentTask?.required_flags || [];
  }, [currentTask]);

  useEffect(() => {
    if (!joined || !currentTask) {
      setFlagValues({});
      return;
    }
    setFlagValues((prev) => {
      const next = {};
      requiredFlags.forEach((flag) => {
        next[flag.flag_id] = prev[flag.flag_id] || '';
      });
      return next;
    });
  }, [joined, currentTask, requiredFlags]);

  const knowledgeAreas = contest?.knowledge_areas?.length
    ? contest.knowledge_areas
    : currentTask?.tags?.length
      ? currentTask.tags
      : ['Стеганография', 'Реверс-инжиниринг'];

  const taskDescription = currentTask?.participant_description || contest?.description || '';

  const handleJoin = async () => {
    if (!contest?.id) return;
    try {
      await contestAPI.joinContest(contest.id);
      try {
        const refreshedContest = await contestAPI.getActiveContest();
        setContest(refreshedContest);
      } catch {
        // Keep join flow resilient even if summary refresh fails.
      }
      const current = await contestAPI.getCurrentTask(contest.id);
      setTaskState(current);
      setJoined(true);
      setFlagValues({});
      setSubmitMessage('');
      if (activeTab === 'results') {
        await refreshLeaderboard(contest.id);
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setSubmitMessage(typeof detail === 'string' ? detail : 'Не удалось вступить в контест');
    }
  };

  const handleSubmit = async (flagId) => {
    const submittedValue = (flagValues?.[flagId] || '').trim();
    if (!contest?.id || !submittedValue) return;
    setSubmittingFlagId(flagId);
    setSubmitMessage('');
    try {
      const previousTaskId = currentTask?.id;
      const result = await contestAPI.submitFlag(contest.id, {
        task_id: currentTask?.id,
        flag_id: flagId,
        flag: submittedValue,
      });
      if (result.is_correct) {
        const current = await contestAPI.getCurrentTask(contest.id);
        setTaskState(current);
        if (result.finished || current?.finished) {
          setSubmitMessage('Контест завершён!');
        } else if (current?.task?.id === previousTaskId) {
          const remaining = Math.max(
            0,
            (current?.task?.required_flags_count || 0) - (current?.task?.solved_flags_count || 0),
          );
          setSubmitMessage(
            remaining > 0
              ? `Флаг принят. Осталось флагов для задачи: ${remaining}.`
              : 'Флаг принят.',
          );
        } else {
          setSubmitMessage('Флаг принят. Следующая задача готова.');
        }
        setFlagValues((prev) => ({ ...prev, [flagId]: '' }));
        if (activeTab === 'results') {
          await refreshLeaderboard(contest.id);
        }
        if (detailsOpen) {
          await refreshMyResults(contest.id);
        }
      } else {
        setSubmitMessage('Неверный флаг. Попробуйте ещё раз.');
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setSubmitMessage(typeof detail === 'string' ? detail : 'Не удалось отправить флаг');
    } finally {
      setSubmittingFlagId(null);
    }
  };

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

  const isPublic = contest?.is_public !== false;
  const shouldBlurContent = !isPublic || contestInactive;
  const leaderboardCurrentUser = leaderboardMe || leaderboardRows.find((row) => row.is_me) || null;
  const shouldShowStickyCurrentUser = Boolean(
    activeTab === 'results'
      && leaderboardCurrentUser
      && leaderboardCurrentUser.rank > 9
      && !isMyRowVisible,
  );

  const renderTitleCell = (row) => {
    if (!row?.first_blood_count) return <span className="text-white/30">—</span>;
    return (
      <span className="inline-flex items-center gap-2 text-[#FF4D7A]">
        <svg className="h-[18px] w-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M12 3c3.5 4.2 5.4 7.1 5.4 9.7A5.4 5.4 0 116.6 12.7C6.6 10.1 8.5 7.2 12 3z" />
        </svg>
        {row.first_blood_count}
      </span>
    );
  };

  const renderLeaderboardRow = (row, { attachCurrentUserRef = false, sticky = false } = {}) => (
    <div
      key={`${sticky ? 'sticky-' : ''}${row.user_id}-${row.rank}`}
      ref={attachCurrentUserRef ? leaderboardMyRowRef : null}
      className={[
        'grid grid-cols-[82px_minmax(260px,1fr)_96px_126px_148px_148px] items-center gap-4 rounded-[12px] px-4 py-3',
        sticky
          ? 'border border-[#9B6BFF]/25 bg-[linear-gradient(90deg,rgba(155,107,255,0.22),rgba(155,107,255,0.08))]'
          : row.is_me
            ? 'border border-[#9B6BFF]/20 bg-[linear-gradient(90deg,rgba(155,107,255,0.2),rgba(155,107,255,0.06))]'
            : 'bg-white/[0.03]',
      ].join(' ')}
    >
      <div className="font-mono-figma text-[23px] leading-[28px] tracking-[0.02em]">{row.rank}</div>
      <div className="flex items-center gap-3 overflow-hidden">
        <div className="relative h-11 w-11 shrink-0 overflow-hidden rounded-[10px] bg-[#9B6BFF]">
          {row.avatar_url ? (
            <img
              src={row.avatar_url}
              alt={row.username}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center">
              <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 12a4 4 0 100-8 4 4 0 000 8z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 21a7 7 0 0114 0" />
              </svg>
            </div>
          )}
        </div>
        <div className="min-w-0">
          <div className="truncate font-mono-figma text-[18px] leading-[24px] tracking-[0.02em]">{row.username}</div>
          <div className="text-[12px] leading-[16px] tracking-[0.02em] text-white/45">
            {formatDateTime(row.last_submission_at)}
          </div>
        </div>
      </div>
      <div className="text-center text-[18px] leading-[24px] tracking-[0.02em]">
        {renderTitleCell(row)}
      </div>
      <div className="text-center font-mono-figma text-[23px] leading-[28px] tracking-[0.02em]">{row.points}</div>
      <div className="text-center text-[18px] leading-[24px] tracking-[0.02em]">{row.flags_collected}</div>
      <div className="flex items-center justify-center text-white/55">
        <svg className="h-[18px] w-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M9 7h6M9 11h6M9 15h4M7 3h8l4 4v14H7z" />
        </svg>
      </div>
    </div>
  );

  return (
    <div className="font-sans-figma text-white">
      <div className="relative">
        <div className={shouldBlurContent ? 'blur-[6px] pointer-events-none select-none' : ''}>
          <div className="flex flex-col gap-6">
            <section className="relative overflow-hidden rounded-[16px] border border-white/[0.06] px-8 pt-8 pb-6">
              <div className="pointer-events-none absolute inset-0">
                <div className="absolute left-0 top-0 h-[301px] w-[492px] bg-[radial-gradient(ellipse_at_top_left,_rgba(155,107,255,0.18),_rgba(11,10,16,0)_70%)]" />
                <div className="absolute right-0 top-0 h-[375px] w-[551px] bg-[radial-gradient(ellipse_at_top_right,_rgba(155,107,255,0.12),_rgba(11,10,16,0)_70%)]" />
              </div>

              <div className="relative flex justify-end">
                <button className="inline-flex h-11 items-center gap-2 rounded-[8px] bg-white/[0.05] px-4 text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out hover:bg-white/[0.08]">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h8m-8 0l4-4m-4 4l4 4M14 6h4a2 2 0 012 2v10a2 2 0 01-2 2h-4" />
                  </svg>
                  Поделиться
                </button>
              </div>

              <div className="relative mt-6 flex flex-col items-center gap-4 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-[16px] bg-white/[0.03]">
                  <svg className="h-10 w-10 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 4h12v3a6 6 0 01-12 0V4z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4H2v2a4 4 0 004 4" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 4h2v2a4 4 0 01-4 4" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 14h4v4h-4z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 22h8" />
                  </svg>
                </div>

                <span className="inline-flex items-center rounded-[8px] border border-[#3FD18A]/10 bg-[#3FD18A]/10 px-3 py-1 text-[14px] leading-[20px] tracking-[0.04em] text-[#3FD18A]">
                  {daysLeftLabel}
                </span>

                <h2 className="text-[36px] leading-[44px] tracking-[0.02em] font-medium">
                  {contest?.title || 'Чемпионат'}
                </h2>
                <p className="max-w-[560px] text-[20px] leading-[24px] tracking-[0.02em] text-white/60">
                  {contest?.description || 'Описание чемпионата скоро появится.'}
                </p>
              </div>

              <div className="relative mt-6 flex flex-col items-center justify-between gap-6 md:flex-row">
                <button
                  className="inline-flex h-11 items-center gap-2 rounded-[8px] bg-white/[0.05] px-4 text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out hover:bg-white/[0.08]"
                  disabled={!contest?.prev_contest_id}
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 19l-7-7 7-7" />
                  </svg>
                  Предыдущий чемпионат
                </button>
                <button
                  className="inline-flex h-11 items-center gap-2 rounded-[8px] bg-white/[0.05] px-4 text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out hover:bg-white/[0.08]"
                  disabled={!contest?.next_contest_id}
                >
                  Следующий чемпионат
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            </section>

            <div className="flex items-center gap-2 rounded-[12px] border border-white/[0.06] bg-white/[0.02] px-3 py-2">
              <button
                onClick={() => setActiveTab('description')}
                className={`h-14 rounded-[10px] px-6 text-[18px] leading-[24px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                  activeTab === 'description'
                    ? 'bg-white/[0.05] text-white'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                Описание
              </button>
              <button
                onClick={() => setActiveTab('results')}
                className={`h-14 rounded-[10px] px-6 text-[18px] leading-[24px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                  activeTab === 'results'
                    ? 'bg-white/[0.05] text-white'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                Итоги
              </button>
            </div>

            {activeTab === 'description' ? (
              <div className="flex flex-col gap-16 xl:flex-row">
                <div className="flex-1">
                  <div className="flex flex-col gap-8">
                    <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
                      <div className="max-w-[944px]">
                        <h3 className="text-[26px] leading-[32px] tracking-[0.02em]">Описание</h3>
                        <p className="mt-4 text-[18px] leading-[24px] tracking-[0.04em] text-white/60">
                          {taskDescription || 'Описание задания появится позже.'}
                        </p>
                      </div>

                      <div className="flex flex-col items-center gap-3">
                        <div
                          className="relative h-[76px] w-[76px] rounded-full p-[6px]"
                          style={{
                            background: `conic-gradient(#9B6BFF 0deg, #9B6BFF ${taskProgressPercent * 3.6}deg, rgba(255,255,255,0.03) ${taskProgressPercent * 3.6}deg, rgba(255,255,255,0.03) 360deg)`,
                          }}
                        >
                          <div className="flex h-full w-full items-center justify-center rounded-full bg-[#0B0A10] text-[14px] leading-[16px] text-white">
                            {tasksSolved} / {tasksTotal || '?'}
                          </div>
                        </div>
                        <p className="max-w-[258px] text-center text-[12px] leading-[16px] text-white/60">
                          Текущее Задание
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-col gap-4">
                      <div className="flex items-center justify-between text-[16px] leading-[20px] tracking-[0.04em] text-white/60">
                        <div>
                          <div className="text-white/60">Начало</div>
                          <div className="text-white">{startLabel || '—'}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-white/60">Конец</div>
                          <div className="text-white">{endLabel || '—'}</div>
                        </div>
                      </div>

                      <div className="relative h-2 rounded-full bg-white/[0.09]">
                        <div
                          className="absolute left-0 top-0 h-2 rounded-full bg-[#9B6BFF]"
                          style={{ width: `${deadlineProgressPercent}%` }}
                        />
                        <div
                          className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full border border-[#9B6BFF] bg-[#0B0A10]"
                          style={{ left: `calc(${deadlineProgressPercent}% - 6px)` }}
                        />
                      </div>

                      <div className="text-[16px] leading-[20px] tracking-[0.04em] text-white/60">Дедлайн</div>
                    </div>

                    {!joined ? (
                      <div className="flex flex-col gap-2">
                        <button
                          onClick={handleJoin}
                          className="inline-flex h-14 items-center justify-center rounded-[12px] bg-[#9B6BFF] px-8 text-[20px] leading-[24px] tracking-[0.02em] text-white transition-colors duration-300 ease-in-out hover:bg-[#8452FF] md:self-start"
                        >
                          Вступить
                        </button>
                        {submitMessage ? (
                          <span className="text-[14px] leading-[20px] tracking-[0.04em] text-white/60">
                            {submitMessage}
                          </span>
                        ) : null}
                      </div>
                    ) : (
                      <div className="flex flex-col gap-2">
                        {requiredFlags.length ? (
                          <div className="flex flex-col gap-3">
                            {requiredFlags.map((flag) => {
                              const flagId = flag.flag_id;
                              const fieldValue = flagValues?.[flagId] || '';
                              const isSubmittingThisFlag = submittingFlagId === flagId;
                              const isBusy = submittingFlagId !== null;
                              const isSolved = Boolean(flag.is_solved);

                              return (
                                <div key={flagId} className="flex flex-col gap-2 lg:flex-row lg:items-center">
                                  <input
                                    type="text"
                                    placeholder={flag.description || `Введи флаг (${flagId})`}
                                    value={fieldValue}
                                    onChange={(event) => {
                                      const value = event.target.value;
                                      setFlagValues((prev) => ({ ...prev, [flagId]: value }));
                                    }}
                                    disabled={!currentTask || isSolved || isBusy}
                                    className="h-14 w-full rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 text-[16px] leading-[20px] tracking-[0.04em] text-white placeholder:text-white/60 focus:outline-none focus:border-white/30 disabled:opacity-60"
                                  />
                                  <button
                                    onClick={() => handleSubmit(flagId)}
                                    disabled={!currentTask || isSolved || isBusy || !fieldValue.trim()}
                                    className="inline-flex h-14 shrink-0 items-center gap-2 rounded-[10px] bg-white/[0.06] px-6 text-[18px] leading-[24px] tracking-[0.04em] text-white transition-colors duration-300 ease-in-out hover:bg-white/[0.1] disabled:text-white/50 disabled:opacity-60"
                                  >
                                    <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 4h12v3a6 6 0 01-12 0V4z" />
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4H2v2a4 4 0 004 4" />
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 4h2v2a4 4 0 01-4 4" />
                                    </svg>
                                    {isSolved ? 'Принято' : isSubmittingThisFlag ? 'Отправка...' : 'Сдать флаг'}
                                  </button>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="text-[14px] leading-[20px] tracking-[0.04em] text-white/60">
                            У текущей задачи пока нет настроенных флагов.
                          </div>
                        )}
                        <span className="text-[14px] leading-[20px] tracking-[0.04em] text-white/60">
                          {submitMessage || (taskState?.finished ? 'Контест завершён' : 'Не могу решить')}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <aside className="flex w-full flex-col gap-8 xl:w-[420px]">
                  <button className="inline-flex h-[54px] w-full items-center justify-center gap-2 rounded-[12px] bg-white/[0.03] text-[18px] leading-[22px] tracking-[0.04em] transition-colors duration-300 ease-in-out hover:bg-white/[0.06]">
                    <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 4h12v3a6 6 0 01-12 0V4z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4H2v2a4 4 0 004 4" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 4h2v2a4 4 0 01-4 4" />
                    </svg>
                    Отправить решение
                  </button>

                  <div className="rounded-[12px] bg-white/[0.03] p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <div className="text-[18px] leading-[24px] tracking-[0.04em]">Оцени задание</div>
                        <div className="text-[14px] leading-[20px] tracking-[0.04em] text-white/60">Оцени задание</div>
                      </div>
                      <div className="flex items-center gap-2 text-white/60">
                        {[...Array(5)].map((_, index) => (
                          <svg key={index} className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={1.5}
                              d="M11.48 3.499a.562.562 0 011.04 0l2.125 6.496a.563.563 0 00.535.385h6.65a.562.562 0 01.328 1.017l-5.381 3.91a.563.563 0 00-.203.62l2.125 6.496a.562.562 0 01-.862.63l-5.381-3.91a.563.563 0 00-.66 0l-5.381 3.91a.562.562 0 01-.862-.63l2.125-6.496a.563.563 0 00-.203-.62l-5.381-3.91a.562.562 0 01.328-1.017h6.65a.563.563 0 00.535-.385L11.48 3.5z"
                            />
                          </svg>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[20px] leading-[24px] tracking-[0.02em]">
                    <span>Награда</span>
                    <span className="flex items-center gap-2 font-mono-figma text-[18px] leading-[24px] text-white/60">
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={1.5}
                          d="M11.48 3.499a.562.562 0 011.04 0l2.125 6.496a.563.563 0 00.535.385h6.65a.562.562 0 01.328 1.017l-5.381 3.91a.563.563 0 00-.203.62l2.125 6.496a.562.562 0 01-.862.63l-5.381-3.91a.563.563 0 00-.66 0l-5.381 3.91a.562.562 0 01-.862-.63l2.125-6.496a.563.563 0 00-.203-.62l-5.381-3.91a.562.562 0 01.328-1.017h6.65a.563.563 0 00.535-.385L11.48 3.5z"
                        />
                      </svg>
                      {contest?.reward_points ?? 0}
                    </span>
                  </div>

                  <div className="flex flex-col gap-3">
                    <div className="text-[20px] leading-[24px] tracking-[0.02em]">Область знаний</div>
                    <div className="flex flex-wrap gap-3">
                      {knowledgeAreas.map((area) => (
                        <span
                          key={area}
                          className="inline-flex items-center rounded-[8px] border border-white/[0.09] bg-white/[0.05] px-3 py-1 text-[14px] leading-[20px] tracking-[0.04em] text-white"
                        >
                          {area}
                        </span>
                      ))}
                    </div>
                  </div>

                  {taskState?.previous_tasks?.length ? (
                    <div className="flex flex-col gap-3">
                      <div className="text-[20px] leading-[24px] tracking-[0.02em]">Решенные задачи</div>
                      <div className="flex flex-col gap-2">
                        {taskState.previous_tasks.map((task) => (
                          <div key={task.id} className="rounded-[10px] bg-white/[0.03] px-3 py-2 text-[14px] text-white/70">
                            {task.title}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <div className="flex items-center justify-between text-[20px] leading-[24px] tracking-[0.02em]">
                    <span>Участники</span>
                    <span className="text-[18px] leading-[24px] tracking-[0.04em] text-white/60">
                      {contest?.participants_count ?? 0}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[20px] leading-[24px] tracking-[0.02em]">
                    <span>Первая кровь</span>
                    <span className="text-[18px] leading-[24px] tracking-[0.04em] text-white/60">
                      {contest?.first_blood_username || '—'}
                    </span>
                  </div>
                </aside>
              </div>
            ) : (
              <section className="rounded-[16px] border border-white/[0.06] bg-white/[0.01] p-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-[32px] leading-[36px] tracking-[0.02em]">Итоги</h3>
                  <button
                    onClick={() => setDetailsOpen(true)}
                    className="inline-flex h-11 items-center rounded-[10px] bg-white/[0.05] px-4 text-[16px] leading-[20px] tracking-[0.04em] text-white/80 transition-colors duration-300 ease-in-out hover:bg-white/[0.09]"
                  >
                    Детализация
                  </button>
                </div>

                <div className="mt-6 grid grid-cols-[82px_minmax(260px,1fr)_96px_126px_148px_148px] items-center gap-4 px-4 text-[12px] leading-[16px] tracking-[0.08em] text-white/55">
                  <div>Место</div>
                  <div>Пользователь</div>
                  <div className="text-center">Титул</div>
                  <div className="text-center">Баллы</div>
                  <div className="text-center">Собрано флагов</div>
                  <div className="text-center">Решение</div>
                </div>

                <div ref={leaderboardScrollRef} className="mt-3 max-h-[620px] space-y-1.5 overflow-y-auto pr-1">
                  {leaderboardLoading ? (
                    <div className="rounded-[12px] bg-white/[0.03] px-4 py-5 text-[16px] text-white/60">
                      Загружаем рейтинг...
                    </div>
                  ) : leaderboardRows.length ? (
                    leaderboardRows.map((row) => renderLeaderboardRow(row, { attachCurrentUserRef: row.is_me }))
                  ) : (
                    <div className="rounded-[12px] bg-white/[0.03] px-4 py-5 text-[16px] text-white/60">
                      Пока нет участников с результатами.
                    </div>
                  )}
                </div>

                {shouldShowStickyCurrentUser && leaderboardCurrentUser ? (
                  <div className="mt-3">
                    {renderLeaderboardRow(leaderboardCurrentUser, { sticky: true })}
                  </div>
                ) : null}

                {leaderboardError ? (
                  <div className="mt-3 text-[14px] leading-[20px] text-[#FF8A8A]">{leaderboardError}</div>
                ) : null}
              </section>
            )}
          </div>
        </div>

        {shouldBlurContent && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="rounded-[20px] border border-white/[0.12] bg-white/[0.04] px-6 py-5 text-center backdrop-blur-[64px] transition-opacity duration-300 ease-in-out">
              <h2 className="text-[24px] leading-[32px] font-medium">
                Мы тут пока придумываем новые задания
              </h2>
              <p className="mt-2 text-[16px] leading-[20px] tracking-[0.04em] text-white/60">
                Скоро покажем свежий контент и новые испытания.
              </p>
            </div>
          </div>
        )}

        {detailsOpen && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-[#0B0A10]/70 px-4 backdrop-blur-[10px]">
            <div className="relative w-full max-w-[600px] overflow-hidden rounded-[20px] border border-white/[0.08] bg-[linear-gradient(112deg,rgba(155,107,255,0.16),rgba(255,255,255,0.03))] p-8 shadow-[0_20px_50px_rgba(11,10,16,0.42)]">
              <button
                onClick={() => setDetailsOpen(false)}
                className="absolute right-5 top-5 inline-flex h-8 w-8 items-center justify-center rounded-[8px] text-white/60 transition-colors hover:bg-white/[0.06] hover:text-white"
                aria-label="Закрыть"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>

              <h4 className="pr-10 text-[23px] leading-[28px] tracking-[0.02em]">Детализация</h4>
              <p className="mt-2 max-w-[520px] text-[16px] leading-[20px] tracking-[0.04em] text-white/60">
                Расписали все найденные тобой флаги за чемпионат и начисленные за них баллы
              </p>

              <div className="mt-10 text-[16px] leading-[20px] tracking-[0.04em] text-white/60">
                <div className="grid grid-cols-[minmax(0,1fr)_110px] items-center gap-4 pb-3">
                  <span>Флаг</span>
                  <span className="text-right">Баллы</span>
                </div>

                {detailsLoading ? (
                  <div className="rounded-[12px] bg-white/[0.03] px-4 py-5 text-[16px] text-white/60">
                    Загружаем детализацию...
                  </div>
                ) : detailsItems.length ? (
                  detailsItems.map((item) => (
                    <div
                      key={`${item.task_id}-${item.flag}-${item.submitted_at}`}
                      className="grid grid-cols-[minmax(0,1fr)_110px] items-center gap-4 border-t border-white/[0.08] py-3"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-[18px] leading-[24px] tracking-[0.02em] text-white">{item.flag}</div>
                        <div className="mt-1 truncate text-[12px] leading-[16px] tracking-[0.02em] text-white/45">
                          {item.task_title}
                        </div>
                      </div>
                      <div className="text-right text-[18px] leading-[24px] tracking-[0.02em] text-white">{item.points}</div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-[12px] bg-white/[0.03] px-4 py-5 text-[16px] text-white/60">
                    Пока нет найденных флагов.
                  </div>
                )}

                <div className="grid grid-cols-[minmax(0,1fr)_110px] items-center gap-4 border-t border-white/[0.12] py-3">
                  <span className="text-[23px] leading-[28px] tracking-[0.02em] text-white">Итог</span>
                  <span className="text-right text-[23px] leading-[28px] tracking-[0.02em] text-white">{detailsTotal}</span>
                </div>
              </div>

              {detailsError ? (
                <div className="mt-2 text-[14px] leading-[20px] text-[#FF8A8A]">{detailsError}</div>
              ) : null}

              <div className="mt-8 flex justify-end">
                <button
                  onClick={() => setDetailsOpen(false)}
                  className="inline-flex h-11 items-center rounded-[10px] bg-[#9B6BFF] px-8 text-[16px] leading-[20px] tracking-[0.04em] text-white transition-colors hover:bg-[#8452FF]"
                >
                  Понятно
                </button>
              </div>

              <p className="mt-5 text-center text-[13px] leading-[16px] tracking-[0.04em] text-white/45">
                Список всех флагов чемпионата ищи в Базе знаний
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Championship;
