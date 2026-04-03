import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageLoader } from '../../components/LoadingState';

// Dashboard Components
import StatCard from './Widgets/StatCard';
import NvdSyncWidget from './Widgets/NvdSyncWidget';
import FeedbackPanel from './Dashboard/FeedbackPanel';
import ChampionshipWidget from './Dashboard/ChampionshipWidget';
import RecentArticleCard from './Dashboard/RecentArticleCard';
import FeedbackResolver from './Widgets/FeedbackResolver';

// Drawers
import KnowledgeBaseDrawer from './Drawers/KnowledgeBaseDrawer';
import TaskManagerDrawer from './Drawers/TaskManagerDrawer';
import TaskEditDrawer from './Drawers/TaskEditDrawer';
import ContestPlannerDrawer from './Drawers/ContestPlannerDrawer';
import ContestHistoryDrawer from './Drawers/ContestHistoryDrawer';
import PromptManagerDrawer from './Drawers/PromptManagerDrawer';

// Icons
import { UsersIcon, ActivityIcon, CreditIcon, TrophyIcon } from './Widgets/Icons';

// Hooks
import { useAdminDashboard } from './hooks/useAdminDashboard';

function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  if (Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('ru-RU');
}

function Admin() {
  const navigate = useNavigate();
  const { loading, dashboard, error, refresh, refreshQuiet, setDashboard } = useAdminDashboard(navigate);

  // Drawer states
  const [isKbOpen, setIsKbOpen] = useState(false);
  const [isTaskOpen, setIsTaskOpen] = useState(false);
  const [isTaskEditOpen, setIsTaskEditOpen] = useState(false);
  const [taskEditId, setTaskEditId] = useState(null);
  const [isContestPlanningOpen, setIsContestPlanningOpen] = useState(false);
  const [isContestHistoryOpen, setIsContestHistoryOpen] = useState(false);
  const [editingContestId, setEditingContestId] = useState(null);
  const [isPromptManagerOpen, setIsPromptManagerOpen] = useState(false);

  // Feedback resolution state
  const [feedbackToResolve, setFeedbackToResolve] = useState(null);
  const [isResolvingFeedback, setIsResolvingFeedback] = useState(false);
  const [feedbackResolveError, setFeedbackResolveError] = useState('');

  // NVD sync state
  const [isNvdRunning, setIsNvdRunning] = useState(false);
  const [nvdError, setNvdError] = useState('');

  const stats = dashboard?.stats || {};
  const contest = dashboard?.current_championship || null;
  const lastArticle = dashboard?.last_article || null;
  const feedbacks = dashboard?.latest_feedbacks || [];
  const nvdSync = dashboard?.nvd_sync || null;

  const paidConversion = stats.total_users
    ? ((stats.paid_users / stats.total_users) * 100).toFixed(1)
    : '0.0';

  // NVD polling
  const nvdStatus = nvdSync?.status || null;
  const isNvdBackgroundRunning = useMemo(() => {
    const NVD_ACTIVE_STATUSES = new Set(['fetching', 'embedding']);
    return NVD_ACTIVE_STATUSES.has(nvdStatus);
  }, [nvdStatus]);

  useEffect(() => {
    if (!isNvdBackgroundRunning) return undefined;
    const interval = setInterval(() => {
      refreshQuiet();
    }, 2500);
    return () => clearInterval(interval);
  }, [isNvdBackgroundRunning, refreshQuiet]);

  const handleFetchNvd = useCallback(async () => {
    const NVD_ACTIVE_STATUSES = new Set(['fetching', 'embedding']);
    const nvdStatus = nvdSync?.status || null;
    if (isNvdRunning || NVD_ACTIVE_STATUSES.has(nvdStatus)) return;

    setIsNvdRunning(true);
    setNvdError('');
    try {
      const { adminAPI } = await import('../../services/api');
      const data = await adminAPI.fetchNvd24h();
      setDashboard((prev) => ({
        ...(prev || {}),
        nvd_sync: data,
      }));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const responseData = err?.response?.data;
      let msg = 'Не удалось выполнить синхронизацию NVD';
      if (typeof responseData === 'string' && responseData.trim()) msg = responseData;
      else if (typeof detail === 'string' && detail.trim()) msg = detail;
      setNvdError(msg);
    } finally {
      setIsNvdRunning(false);
    }
  }, [isNvdRunning, nvdSync, setDashboard]);

  const handleEditTask = useCallback((taskId) => {
    setTaskEditId(taskId);
    setIsTaskEditOpen(true);
  }, []);

  const handleEditContest = useCallback((contest) => {
    setEditingContestId(contest.id);
    setIsContestPlanningOpen(true);
  }, []);

  const handleStartResolveFeedback = useCallback((feedback) => {
    setFeedbackResolveError('');
    setFeedbackToResolve(feedback);
  }, []);

  const handleCancelResolveFeedback = useCallback(() => {
    if (isResolvingFeedback) return;
    setFeedbackResolveError('');
    setFeedbackToResolve(null);
  }, [isResolvingFeedback]);

  const handleConfirmResolveFeedback = useCallback(async () => {
    if (!feedbackToResolve || isResolvingFeedback) return;
    setIsResolvingFeedback(true);
    setFeedbackResolveError('');
    try {
      const { adminAPI } = await import('../../services/api');
      await adminAPI.resolveFeedback(feedbackToResolve.id);
      setDashboard((prev) => {
        if (!prev) return prev;
        const nextFeedbacks = (prev.latest_feedbacks || []).filter(
          (item) => item.id !== feedbackToResolve.id
        );
        return { ...prev, latest_feedbacks: nextFeedbacks };
      });
      setFeedbackToResolve(null);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const responseData = err?.response?.data;
      let msg = 'Не удалось отметить отзыв как решённый';
      if (typeof responseData === 'string' && responseData.trim()) msg = responseData;
      else if (typeof detail === 'string' && detail.trim()) msg = detail;
      setFeedbackResolveError(msg);
    } finally {
      setIsResolvingFeedback(false);
    }
  }, [feedbackToResolve, isResolvingFeedback, setDashboard]);

  if (loading) {
    return <PageLoader label="Загрузка админки..." variant="admin" />;
  }

  return (
    <div className="font-sans-figma text-white flex flex-col gap-6 pb-12">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[28px] leading-[32px] tracking-[0.02em]">
            Админка
          </h1>
          <p className="text-[16px] leading-[20px] text-white/60 mt-2">
            Сводка по пользователям, чемпионатам и контенту платформы
          </p>
        </div>
        <div className="flex flex-col items-end gap-3">
          <div className="flex flex-wrap items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => setIsContestHistoryOpen(true)}
              className="h-10 px-4 rounded-[12px] bg-white/10 border border-white/10 text-white/80 text-[14px] tracking-[0.04em] transition-colors duration-200 hover:border-[#9B6BFF]/60 hover:text-white"
            >
              История контестов
            </button>
            <button
              type="button"
              onClick={() => setIsContestPlanningOpen(true)}
              className="h-10 px-4 rounded-[12px] bg-white/10 border border-white/10 text-white/80 text-[14px] tracking-[0.04em] transition-colors duration-200 hover:border-[#9B6BFF]/60 hover:text-white"
            >
              Планирование контеста
            </button>
            <button
              type="button"
              onClick={() => setIsPromptManagerOpen(true)}
              className="h-10 px-4 rounded-[12px] bg-white/10 border border-white/10 text-white/80 text-[14px] tracking-[0.04em] transition-colors duration-200 hover:border-[#9B6BFF]/60 hover:text-white"
            >
              Prompt Manager
            </button>
            <button
              type="button"
              onClick={() => setIsTaskOpen(true)}
              className="h-10 px-4 rounded-[12px] bg-[#9B6BFF] text-white text-[14px] tracking-[0.04em] transition-colors duration-200 hover:bg-[#8452FF]"
            >
              Задачи
            </button>
            <button
              type="button"
              onClick={() => setIsKbOpen(true)}
              className="h-10 px-4 rounded-[12px] border border-[#9B6BFF]/60 text-[#CBB6FF] text-[14px] tracking-[0.04em] transition-colors duration-200 hover:bg-[#9B6BFF]/10"
            >
              База знаний
            </button>
          </div>
          {(nvdError || error) && (
            <div className="text-[14px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-[12px] px-4 py-2">
              {nvdError || error}
            </div>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Всего пользователей"
          value={formatNumber(stats.total_users)}
          hint="Все зарегистрированные аккаунты"
          icon={<UsersIcon className="w-4 h-4" />}
          tone="bg-white/10 text-white"
        />
        <StatCard
          label="Активные 24ч"
          value={formatNumber(stats.active_users_24h)}
          hint="Входили в систему за последние 24 часа"
          icon={<ActivityIcon className="w-4 h-4" />}
          tone="bg-emerald-500/15 text-emerald-300"
        />
        <StatCard
          label="Платные пользователи"
          value={formatNumber(stats.paid_users)}
          hint={`${paidConversion}% конверсия`}
          icon={<CreditIcon className="w-4 h-4" />}
          tone="bg-[#9B6BFF]/15 text-[#CBB6FF]"
        />
        <StatCard
          label="Сабмиты в чемпионате"
          value={formatNumber(stats.current_championship_submissions)}
          hint="Количество отправок в текущем чемпионате"
          icon={<TrophyIcon className="w-4 h-4" />}
          tone="bg-amber-400/15 text-amber-200"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <FeedbackPanel
          feedbacks={feedbacks}
          onResolve={handleStartResolveFeedback}
        />
        <ChampionshipWidget
          contest={contest}
          submissions={stats.current_championship_submissions}
          onEditContest={() => handleEditContest(contest)}
          onViewHistory={() => setIsContestHistoryOpen(true)}
        />
      </div>

      {/* NVD Sync Widget */}
      <NvdSyncWidget
        nvdSync={nvdSync}
        onFetch={handleFetchNvd}
        isRunning={isNvdRunning}
        error={nvdError}
      />

      {/* Recent Article */}
      <RecentArticleCard article={lastArticle} />

      {/* Feedback Resolver Modal */}
      <FeedbackResolver
        feedback={feedbackToResolve}
        onConfirm={handleConfirmResolveFeedback}
        onCancel={handleCancelResolveFeedback}
        isResolving={isResolvingFeedback}
        error={feedbackResolveError}
      />

      {/* Drawers */}
      <KnowledgeBaseDrawer
        open={isKbOpen}
        onClose={() => setIsKbOpen(false)}
        onCreated={refresh}
        onUpdated={refresh}
      />
      <TaskManagerDrawer
        open={isTaskOpen}
        onClose={() => setIsTaskOpen(false)}
        onCreated={refresh}
        onEditTask={handleEditTask}
      />
      <TaskEditDrawer
        open={isTaskEditOpen}
        taskId={taskEditId}
        onClose={() => {
          setIsTaskEditOpen(false);
          setTaskEditId(null);
        }}
        onUpdated={refresh}
      />
      <ContestPlannerDrawer
        open={isContestPlanningOpen}
        onClose={() => {
          setIsContestPlanningOpen(false);
          setEditingContestId(null);
        }}
        onCreated={refresh}
        onUpdated={refresh}
        contestId={editingContestId}
      />
      <ContestHistoryDrawer
        open={isContestHistoryOpen}
        onClose={() => setIsContestHistoryOpen(false)}
        onEditContest={handleEditContest}
      />
      <PromptManagerDrawer
        open={isPromptManagerOpen}
        onClose={() => setIsPromptManagerOpen(false)}
      />
    </div>
  );
}

export default Admin;
