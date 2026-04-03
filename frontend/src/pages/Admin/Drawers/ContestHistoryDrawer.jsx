import React, { useEffect, useState, useCallback, useMemo } from 'react';
import Drawer from '../Widgets/Drawer';
import { adminAPI } from '../../../services/api';
import { SkeletonBlock } from '../../../components/LoadingState';

function getApiErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  const responseData = err?.response?.data;
  if (typeof responseData === 'string' && responseData.trim()) return responseData;
  if (typeof detail === 'string' && detail.trim()) return detail;
  return fallback;
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function ContestHistoryDrawer({ open, onClose, onEditContest }) {
  const [contests, setContests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    if (!open) return;
    setContests([]);
    setError('');
    setSearchQuery('');
    setStatusFilter('all');
  }, [open]);

  const loadContests = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await adminAPI.listContests();
      setContests(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось загрузить список чемпионатов'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      loadContests();
    }
  }, [open, loadContests]);

  const filteredContests = useMemo(() => {
    const now = Date.now();
    return contests.filter((contest) => {
      const matchesSearch = searchQuery
        ? contest.title.toLowerCase().includes(searchQuery.toLowerCase())
        : true;

      const start = new Date(contest.start_at).getTime();
      const end = new Date(contest.end_at).getTime();
      let matchesStatus = true;

      if (statusFilter === 'active') {
        matchesStatus = now >= start && now <= end;
      } else if (statusFilter === 'upcoming') {
        matchesStatus = now < start;
      } else if (statusFilter === 'completed') {
        matchesStatus = now > end;
      }

      return matchesSearch && matchesStatus;
    });
  }, [contests, searchQuery, statusFilter]);

  const getContestStatus = useCallback((contest) => {
    const now = Date.now();
    const start = new Date(contest.start_at).getTime();
    const end = new Date(contest.end_at).getTime();

    if (now < start) {
      return { label: 'Скоро', tone: 'bg-[#9B6BFF]/20 text-[#CBB6FF]' };
    }
    if (now > end) {
      return { label: 'Завершен', tone: 'bg-white/10 text-white/70' };
    }
    return { label: 'Активен', tone: 'bg-emerald-500/20 text-emerald-300' };
  }, []);

  const handleEdit = (contest) => {
    if (onEditContest) {
      onEditContest(contest);
      onClose();
    }
  };

  const handleDelete = async (contestId, contestTitle) => {
    const confirmed = window.confirm(
      `Вы уверены, что хотите удалить чемпионат "${contestTitle}"? Это действие нельзя отменить.`
    );
    if (!confirmed) return;

    try {
      await adminAPI.deleteContest(contestId);
      setContests((prev) => prev.filter((c) => c.id !== contestId));
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось удалить чемпионат'));
    }
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="История чемпионатов"
      subtitle="Просмотр и управление всеми чемпионатами"
      width="960px"
    >
      {error && (
        <div className="bg-red-500/10 border border-red-500/50 text-red-200 px-4 py-2 rounded-[12px] mb-4 text-sm">
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-5">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="flex-1 h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
          placeholder="Поиск по названию..."
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
        >
          <option value="all">Все</option>
          <option value="active">Активные</option>
          <option value="upcoming">Предстоящие</option>
          <option value="completed">Завершенные</option>
        </select>
      </div>

      {/* Contest List */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <SkeletonBlock key={i} className="h-20 w-full rounded-[12px]" />
          ))}
        </div>
      ) : filteredContests.length === 0 ? (
        <div className="text-white/50 text-[14px] text-center py-12">
          {searchQuery || statusFilter !== 'all'
            ? 'Чемпионаты не найдены'
            : 'Список чемпионатов пуст'}
        </div>
      ) : (
        <div className="space-y-3 max-h-[calc(100vh-280px)] overflow-y-auto pr-2">
          {filteredContests.map((contest) => {
            const status = getContestStatus(contest);
            return (
              <div
                key={contest.id}
                className="p-4 rounded-[12px] border border-white/10 bg-white/[0.02] hover:border-[#9B6BFF]/40 transition"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-white text-[16px] font-medium">
                        {contest.title}
                      </h3>
                      <span
                        className={`text-[12px] uppercase tracking-[0.24em] px-3 py-1 rounded-full ${status.tone}`}
                      >
                        {status.label}
                      </span>
                    </div>
                    <div className="text-white/50 text-[13px] space-y-1">
                      <div>
                        {formatDate(contest.start_at)} — {formatDate(contest.end_at)}
                      </div>
                      <div className="flex items-center gap-4">
                        <span>Задач: {contest.tasks_count || 0}</span>
                        <span>
                          {contest.is_public ? 'Публичный' : 'Приватный'}
                        </span>
                        <span>
                          {contest.leaderboard_visible
                            ? 'Лидерборд виден'
                            : 'Лидерборд скрыт'}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col gap-2">
                    <button
                      type="button"
                      onClick={() => handleEdit(contest)}
                      className="h-9 px-4 bg-[#9B6BFF]/20 hover:bg-[#9B6BFF]/30 text-[#CBB6FF] text-[13px] rounded-[10px] transition-colors"
                    >
                      Редактировать
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(contest.id, contest.title)}
                      className="h-9 px-4 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-[13px] rounded-[10px] transition-colors"
                    >
                      Удалить
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Drawer>
  );
}

export default ContestHistoryDrawer;
