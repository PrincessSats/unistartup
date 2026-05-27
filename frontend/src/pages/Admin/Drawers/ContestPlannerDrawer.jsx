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

const initialGenState = {
  count: 1,
  mode: 'filter',
  base_difficulty: 8,
  cvss_min: '',
  cvss_max: '',
  cwe_ids: '',
  tags: '',
};

function ContestPlannerDrawer({ open, onClose, onCreated, onUpdated, contestId }) {
  const [form, setForm] = useState(initialContestState);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [tasks, setTasks] = useState([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [selectedTasks, setSelectedTasks] = useState([]);
  const [loadingContest, setLoadingContest] = useState(false);
  const [genModalOpen, setGenModalOpen] = useState(false);
  const [genForm, setGenForm] = useState(initialGenState);
  const [genStatus, setGenStatus] = useState('idle');
  const [genResult, setGenResult] = useState(null);

  const isEditMode = Boolean(contestId);

  useEffect(() => {
    if (!open) return;
    setForm(initialContestState);
    setStatus('idle');
    setError('');
    setSelectedTasks([]);
  }, [open]);

  const loadContest = useCallback(async () => {
    if (!contestId) return;
    setLoadingContest(true);
    setError('');
    try {
      const data = await adminAPI.getContest(contestId);
      setForm({
        title: data.title || '',
        description: data.description || '',
        start_at: data.start_at ? new Date(data.start_at).toISOString().slice(0, 16) : '',
        end_at: data.end_at ? new Date(data.end_at).toISOString().slice(0, 16) : '',
        is_public: data.is_public ?? false,
        leaderboard_visible: data.leaderboard_visible ?? true,
      });
      if (data.tasks && Array.isArray(data.tasks)) {
        setSelectedTasks(data.tasks.map((t) => t.task_id));
      }
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось загрузить данные чемпионата'));
    } finally {
      setLoadingContest(false);
    }
  }, [contestId]);

  useEffect(() => {
    if (open && contestId) {
      loadContest();
    }
  }, [open, contestId, loadContest]);

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
      if (isEditMode) {
        await adminAPI.updateContest(contestId, payload);
        if (onUpdated) onUpdated();
      } else {
        await adminAPI.createContest(payload);
        if (onCreated) onCreated();
      }
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, isEditMode ? 'Не удалось обновить чемпионат' : 'Не удалось создать чемпионат'));
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

  const handleGenerateChampionship = async () => {
    setGenStatus('sending');
    setGenResult(null);
    try {
      const payload = {
        count: Number(genForm.count) || 1,
        mode: genForm.mode,
        base_difficulty: Number(genForm.base_difficulty) || 8,
      };
      if (genForm.mode === 'filter') {
        payload.filters = {
          cvss_min: genForm.cvss_min ? parseFloat(genForm.cvss_min) : undefined,
          cvss_max: genForm.cvss_max ? parseFloat(genForm.cvss_max) : undefined,
          cwe_ids: genForm.cwe_ids ? genForm.cwe_ids.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
          tags: genForm.tags ? genForm.tags.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
        };
      }
      const result = await adminAPI.generateChampionshipTasks(contestId, payload);
      setGenResult(result);
      await loadContest();
      await loadTasks();
    } catch (err) {
      setGenResult({ error: getApiErrorMessage(err, 'Ошибка генерации') });
    } finally {
      setGenStatus('idle');
    }
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={isEditMode ? 'Редактирование контеста' : 'Планирование контеста'}
      subtitle={isEditMode ? 'Изменение параметров чемпионата' : 'Создание нового чемпионата'}
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
            disabled={!canSubmit || loadingContest}
            className="flex-1 h-12 bg-[#9B6BFF] hover:bg-[#8452FF] text-white rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loadingContest ? 'Загрузка...' : status === 'sending' ? (isEditMode ? 'Сохранение...' : 'Создание...') : (isEditMode ? 'Сохранить' : 'Создать чемпионат')}
          </button>
        </div>
      }
    >
      {error && (
        <div className="bg-red-500/10 border border-red-500/50 text-red-200 px-4 py-2 rounded-[12px] mb-4 text-sm">
          {error}
        </div>
      )}

      {loadingContest ? (
        <div className="space-y-5">
          <SkeletonBlock className="h-12 w-full rounded-[10px]" />
          <SkeletonBlock className="h-20 w-full rounded-[10px]" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SkeletonBlock className="h-12 w-full rounded-[10px]" />
            <SkeletonBlock className="h-12 w-full rounded-[10px]" />
          </div>
          <SkeletonBlock className="h-14 w-full rounded-[12px]" />
        </div>
      ) : (

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
          <div className="flex items-center justify-between mb-3">
            <div className="text-white text-[16px]">Задачи чемпионата</div>
            {isEditMode && (
              <button
                type="button"
                onClick={() => { setGenModalOpen(true); setGenResult(null); setGenForm(initialGenState); }}
                className="text-[13px] px-3 py-1.5 rounded-[8px] bg-[#9B6BFF]/20 hover:bg-[#9B6BFF]/40 text-[#9B6BFF] transition-colors"
              >
                + Генерировать чемпионатные
              </button>
            )}
          </div>

          {genModalOpen && (
            <div className="mb-4 p-4 rounded-[12px] border border-[#9B6BFF]/40 bg-[#9B6BFF]/5 space-y-3">
              <div className="text-white text-[14px] font-medium">Генерация чемпионатных задач из CVE</div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-white/60 text-[12px] mb-1 block">Количество (1-5)</label>
                  <input
                    type="number" min="1" max="5"
                    value={genForm.count}
                    onChange={(e) => setGenForm((p) => ({ ...p, count: e.target.value }))}
                    className="w-full h-9 bg-white/[0.04] border border-white/[0.09] rounded-[8px] px-3 text-white/80 focus:outline-none focus:border-white/30 text-[13px]"
                  />
                </div>
                <div>
                  <label className="text-white/60 text-[12px] mb-1 block">Сложность (7-10)</label>
                  <input
                    type="number" min="7" max="10"
                    value={genForm.base_difficulty}
                    onChange={(e) => setGenForm((p) => ({ ...p, base_difficulty: e.target.value }))}
                    className="w-full h-9 bg-white/[0.04] border border-white/[0.09] rounded-[8px] px-3 text-white/80 focus:outline-none focus:border-white/30 text-[13px]"
                  />
                </div>
              </div>

              <div>
                <label className="text-white/60 text-[12px] mb-1 block">Источник CVE</label>
                <div className="flex gap-2">
                  {['filter', 'explicit'].map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setGenForm((p) => ({ ...p, mode: m }))}
                      className={`px-3 py-1 rounded-[6px] text-[12px] transition-colors ${genForm.mode === m ? 'bg-[#9B6BFF] text-white' : 'bg-white/[0.05] text-white/50 hover:text-white/80'}`}
                    >
                      {m === 'filter' ? 'По фильтрам' : 'По ID записей'}
                    </button>
                  ))}
                </div>
              </div>

              {genForm.mode === 'filter' && (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-white/60 text-[12px] mb-1 block">CVSS мин</label>
                      <input
                        type="number" min="0" max="10" step="0.1"
                        placeholder="напр. 7.0"
                        value={genForm.cvss_min}
                        onChange={(e) => setGenForm((p) => ({ ...p, cvss_min: e.target.value }))}
                        className="w-full h-9 bg-white/[0.04] border border-white/[0.09] rounded-[8px] px-3 text-white/80 focus:outline-none focus:border-white/30 text-[13px]"
                      />
                    </div>
                    <div>
                      <label className="text-white/60 text-[12px] mb-1 block">CVSS макс</label>
                      <input
                        type="number" min="0" max="10" step="0.1"
                        placeholder="напр. 10.0"
                        value={genForm.cvss_max}
                        onChange={(e) => setGenForm((p) => ({ ...p, cvss_max: e.target.value }))}
                        className="w-full h-9 bg-white/[0.04] border border-white/[0.09] rounded-[8px] px-3 text-white/80 focus:outline-none focus:border-white/30 text-[13px]"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-white/60 text-[12px] mb-1 block">CWE (через запятую)</label>
                    <input
                      type="text"
                      placeholder="напр. CWE-89, CWE-79"
                      value={genForm.cwe_ids}
                      onChange={(e) => setGenForm((p) => ({ ...p, cwe_ids: e.target.value }))}
                      className="w-full h-9 bg-white/[0.04] border border-white/[0.09] rounded-[8px] px-3 text-white/80 focus:outline-none focus:border-white/30 text-[13px]"
                    />
                  </div>
                  <div>
                    <label className="text-white/60 text-[12px] mb-1 block">Теги (через запятую)</label>
                    <input
                      type="text"
                      placeholder="напр. sqli, xss, rce"
                      value={genForm.tags}
                      onChange={(e) => setGenForm((p) => ({ ...p, tags: e.target.value }))}
                      className="w-full h-9 bg-white/[0.04] border border-white/[0.09] rounded-[8px] px-3 text-white/80 focus:outline-none focus:border-white/30 text-[13px]"
                    />
                  </div>
                </div>
              )}

              {genResult && (
                <div className={`text-[13px] px-3 py-2 rounded-[8px] ${genResult.error ? 'bg-red-500/10 text-red-300' : 'bg-green-500/10 text-green-300'}`}>
                  {genResult.error
                    ? genResult.error
                    : `Создано задач: ${genResult.created?.length || 0}${genResult.failed?.length ? `, ошибок: ${genResult.failed.length}` : ''}`}
                </div>
              )}

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => { setGenModalOpen(false); setGenResult(null); }}
                  className="flex-1 h-9 bg-white/[0.04] hover:bg-white/[0.08] text-white/70 rounded-[8px] text-[13px] transition-colors"
                >
                  Закрыть
                </button>
                <button
                  type="button"
                  onClick={handleGenerateChampionship}
                  disabled={genStatus === 'sending'}
                  className="flex-1 h-9 bg-[#9B6BFF] hover:bg-[#8452FF] text-white rounded-[8px] text-[13px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {genStatus === 'sending' ? 'Генерация...' : 'Генерировать'}
                </button>
              </div>
            </div>
          )}
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
      )}
    </Drawer>
  );
}

export default ContestPlannerDrawer;
