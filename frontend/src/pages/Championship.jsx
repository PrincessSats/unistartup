import React, { useEffect, useMemo, useState } from 'react';
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
              <button className="h-14 rounded-[10px] bg-white/[0.05] px-6 text-[18px] leading-[24px] tracking-[0.04em] transition-colors duration-300 ease-in-out hover:bg-white/[0.08]">
                Описание
              </button>
              <button className="h-14 rounded-[10px] px-6 text-[18px] leading-[24px] tracking-[0.04em] text-white/60 transition-colors duration-300 ease-in-out hover:text-white">
                Итоги
              </button>
            </div>

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
      </div>
    </div>
  );
}

export default Championship;
