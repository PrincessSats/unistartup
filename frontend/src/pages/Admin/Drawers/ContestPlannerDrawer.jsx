import React, { useEffect, useState, useCallback } from 'react';
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

const initialContestState = {
  title: '',
  description: '',
  start_at: '',
  end_at: '',
  is_public: false,
  leaderboard_visible: true,
};

function ContestPlannerDrawer({ open, onClose, onCreated }) {
  const [form, setForm] = useState(initialContestState);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [tasks, setTasks] = useState([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [selectedTasks, setSelectedTasks] = useState([]);

  useEffect(() => {
    if (!open) return;
    setForm(initialContestState);
    setStatus('idle');
    setError('');
    setSelectedTasks([]);
  }, [open]);

  const loadTasks = useCallback(async () => {
    setTasksLoading(true);
    try {
      const data = await adminAPI.listTasks({ task_kind: 'contest', state: 'ready' });
      setTasks(Array.isArray(data) ? data : []);
    } catch {
      setTasks([]);
    } finally {
      setTasksLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      loadTasks();
    }
  }, [open, loadTasks]);

  const handleSubmit = async () => {
    setStatus('sending');
    setError('');
    try {
      const payload = {
        title: form.title,
        description: form.description || null,
        start_at: new Date(form.start_at).toISOString(),
        end_at: new Date(form.end_at).toISOString(),
        is_public: form.is_public,
        leaderboard_visible: form.leaderboard_visible,
        tasks: selectedTasks.map((taskId, index) => ({
          task_id: taskId,
          order_index: index,
        })),
      };
      await adminAPI.createContest(payload);
      if (onCreated) onCreated();
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось создать чемпионат'));
    } finally {
      setStatus('idle');
    }
  };

  const toggleTaskSelection = (taskId) => {
    setSelectedTasks((prev) =>
      prev.includes(taskId)
        ? prev.filter((id) => id !== taskId)
        : [...prev, taskId]
    );
  };

  const canSubmit = form.title.trim() && form.start_at && form.end_at && status !== 'sending';

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Планирование контеста"
      subtitle="Создание нового чемпионата"
      width="640px"
      footer={
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 h-12 bg-white/[0.03] hover:bg-white/[0.06] text-white rounded-[10px] transition-colors"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="flex-1 h-12 bg-[#9B6BFF] hover:bg-[#8452FF] text-white rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {status === 'sending' ? 'Создание...' : 'Создать чемпионат'}
          </button>
        </div>
      }
    >
      {error && (
        <div className="bg-red-500/10 border border-red-500/50 text-red-200 px-4 py-2 rounded-[12px] mb-4 text-sm">
          {error}
        </div>
      )}

      <div className="space-y-5">
        <div>
          <label className="text-white text-sm mb-2 block">Название *</label>
          <input
            type="text"
            value={form.title}
            onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
            className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
            placeholder="Например: HackNet CTF #1"
          />
        </div>

        <div>
          <label className="text-white text-sm mb-2 block">Описание</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
            className="w-full min-h-[80px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
            placeholder="Описание чемпионата..."
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-white text-sm mb-2 block">Начало *</label>
            <input
              type="datetime-local"
              value={form.start_at}
              onChange={(e) => setForm((prev) => ({ ...prev, start_at: e.target.value }))}
              className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30 [&::-webkit-calendar-picker-indicator]:invert"
            />
          </div>
          <div>
            <label className="text-white text-sm mb-2 block">Окончание *</label>
            <input
              type="datetime-local"
              value={form.end_at}
              onChange={(e) => setForm((prev) => ({ ...prev, end_at: e.target.value }))}
              className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30 [&::-webkit-calendar-picker-indicator]:invert"
            />
          </div>
        </div>

        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.is_public}
              onChange={(e) => setForm((prev) => ({ ...prev, is_public: e.target.checked }))}
              className="w-4 h-4 rounded border-white/20 bg-white/[0.03] text-[#9B6BFF] focus:ring-[#9B6BFF]/50"
            />
            <span className="text-white text-[14px]">Публичный</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.leaderboard_visible}
              onChange={(e) => setForm((prev) => ({ ...prev, leaderboard_visible: e.target.checked }))}
              className="w-4 h-4 rounded border-white/20 bg-white/[0.03] text-[#9B6BFF] focus:ring-[#9B6BFF]/50"
            />
            <span className="text-white text-[14px]">Показывать лидерборд</span>
          </label>
        </div>

        <div className="border-t border-white/[0.08] pt-5">
          <div className="text-white text-[16px] mb-3">Задачи чемпионата</div>
          {tasksLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <SkeletonBlock key={i} className="h-14 w-full rounded-[12px]" />
              ))}
            </div>
          ) : tasks.length === 0 ? (
            <div className="text-white/50 text-[14px]">Нет готовых задач для добавления</div>
          ) : (
            <div className="space-y-2 max-h-[240px] overflow-y-auto">
              {tasks.map((task) => (
                <label
                  key={task.id}
                  className="flex items-center gap-3 p-3 rounded-[12px] border border-white/10 bg-white/[0.02] cursor-pointer hover:border-[#9B6BFF]/40 transition"
                >
                  <input
                    type="checkbox"
                    checked={selectedTasks.includes(task.id)}
                    onChange={() => toggleTaskSelection(task.id)}
                    className="w-4 h-4 rounded border-white/20 bg-white/[0.03] text-[#9B6BFF] focus:ring-[#9B6BFF]/50"
                  />
                  <div className="flex-1">
                    <div className="text-white text-[14px]">{task.title}</div>
                    <div className="text-white/40 text-[12px]">
                      {task.category} • Сложность: {task.difficulty} • {task.points} баллов
                    </div>
                  </div>
                </label>
              ))}
            </div>
          )}
          {selectedTasks.length > 0 && (
            <div className="text-white/50 text-[13px] mt-3">
              Выбрано задач: {selectedTasks.length}
            </div>
          )}
        </div>
      </div>
    </Drawer>
  );
}

export default ContestPlannerDrawer;
