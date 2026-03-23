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

const initialTaskState = {
  title: '',
  category: '',
  difficulty: '',
  points: '',
  tags: '',
  language: 'ru',
  story: '',
  participant_description: '',
  state: 'draft',
  task_kind: 'contest',
  access_type: 'just_flag',
  flag: '',
};

function TaskManagerDrawer({ open, onClose, onCreated, onEditTask }) {
  const [tab, setTab] = useState('create');
  const [form, setForm] = useState(initialTaskState);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [tasks, setTasks] = useState([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [generateForm, setGenerateForm] = useState({ difficulty: 5, tags: '', description: '' });
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTab('create');
    setForm(initialTaskState);
    setStatus('idle');
    setError('');
    setTasks([]);
    setTasksLoading(false);
  }, [open]);

  const loadTasks = useCallback(async () => {
    setTasksLoading(true);
    try {
      const data = await adminAPI.listTasks();
      setTasks(Array.isArray(data) ? data : []);
    } catch {
      setTasks([]);
    } finally {
      setTasksLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    if (tab !== 'edit') return;
    loadTasks();
  }, [open, tab, loadTasks]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError('');
    try {
      const result = await adminAPI.generateTask({
        difficulty: Number.parseInt(generateForm.difficulty, 10) || 5,
        tags: generateForm.tags.split(',').map((t) => t.trim()).filter(Boolean),
        description: generateForm.description,
      });
      if (result.task) {
        setForm({
          title: result.task.title || '',
          category: result.task.category || '',
          difficulty: String(result.task.difficulty || 5),
          points: String(result.task.points || 100),
          tags: Array.isArray(result.task.tags) ? result.task.tags.join(', ') : '',
          language: result.task.language || 'ru',
          story: result.task.story || '',
          participant_description: result.task.participant_description || '',
          state: 'draft',
          task_kind: 'contest',
          access_type: 'just_flag',
          flag: result.task.flags?.[0]?.expected_value || '',
        });
      }
      setGenerating(false);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось сгенерировать задачу'));
      setGenerating(false);
    }
  };

  const handleSubmit = async () => {
    setStatus('sending');
    setError('');
    try {
      const payload = {
        title: form.title,
        category: form.category,
        difficulty: Number.parseInt(form.difficulty, 10) || 1,
        points: Number.parseInt(form.points, 10) || 100,
        tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
        language: form.language,
        story: form.story,
        participant_description: form.participant_description,
        state: form.state,
        task_kind: form.task_kind,
        access_type: form.access_type,
        flags: [{ flag_id: crypto.randomUUID(), format: 'string', expected_value: form.flag }],
        materials: [],
      };
      await adminAPI.createTask(payload);
      if (onCreated) onCreated();
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось создать задачу'));
    } finally {
      setStatus('idle');
    }
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Управление задачами"
      subtitle="Создание и редактирование CTF задач"
      width="960px"
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
            disabled={status === 'sending' || !form.title.trim()}
            className="flex-1 h-12 bg-[#9B6BFF] hover:bg-[#8452FF] text-white rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {status === 'sending' ? 'Сохранение...' : 'Создать задачу'}
          </button>
        </div>
      }
    >
      {error && (
        <div className="bg-red-500/10 border border-red-500/50 text-red-200 px-4 py-2 rounded-[12px] mb-4 text-sm">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => setTab('create')}
          className={`h-9 px-4 rounded-[10px] text-[13px] transition ${
            tab === 'create'
              ? 'bg-[#9B6BFF] text-white'
              : 'border border-white/10 text-white/60 hover:text-white'
          }`}
        >
          Создать задачу
        </button>
        <button
          type="button"
          onClick={() => setTab('edit')}
          className={`h-9 px-4 rounded-[10px] text-[13px] transition ${
            tab === 'edit'
              ? 'bg-[#9B6BFF] text-white'
              : 'border border-white/10 text-white/60 hover:text-white'
          }`}
        >
          Редактировать
        </button>
      </div>

      {tab === 'create' && (
        <>
          <div className="border border-white/[0.08] rounded-[16px] p-5 mb-6">
            <div className="text-[16px] text-white mb-4">AI Генерация</div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="text-white text-sm mb-2 block">Сложность</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={generateForm.difficulty}
                  onChange={(e) => setGenerateForm((prev) => ({ ...prev, difficulty: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                />
              </div>
              <div className="md:col-span-2">
                <label className="text-white text-sm mb-2 block">Теги</label>
                <input
                  type="text"
                  value={generateForm.tags}
                  onChange={(e) => setGenerateForm((prev) => ({ ...prev, tags: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                  placeholder="web, xss, cve-2024-..."
                />
              </div>
            </div>
            <div className="mb-4">
              <label className="text-white text-sm mb-2 block">Описание</label>
              <textarea
                value={generateForm.description}
                onChange={(e) => setGenerateForm((prev) => ({ ...prev, description: e.target.value }))}
                className="w-full min-h-[80px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                placeholder="Опишите идею задачи..."
              />
            </div>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generating || !generateForm.description.trim()}
              className="h-10 px-4 rounded-[10px] bg-[#9B6BFF] hover:bg-[#8452FF] text-white text-[13px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {generating ? 'Генерация...' : 'Сгенерировать через AI'}
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-white text-sm mb-2 block">Название *</label>
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
                className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
              />
            </div>
            <div>
              <label className="text-white text-sm mb-2 block">Категория</label>
              <input
                type="text"
                value={form.category}
                onChange={(e) => setForm((prev) => ({ ...prev, category: e.target.value }))}
                className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
              />
            </div>
            <div>
              <label className="text-white text-sm mb-2 block">Сложность</label>
              <input
                type="number"
                min="1"
                max="10"
                value={form.difficulty}
                onChange={(e) => setForm((prev) => ({ ...prev, difficulty: e.target.value }))}
                className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
              />
            </div>
            <div>
              <label className="text-white text-sm mb-2 block">Баллы</label>
              <input
                type="number"
                value={form.points}
                onChange={(e) => setForm((prev) => ({ ...prev, points: e.target.value }))}
                className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
              />
            </div>
          </div>

          <div className="mt-4">
            <label className="text-white text-sm mb-2 block">Описание для участника</label>
            <textarea
              value={form.participant_description}
              onChange={(e) => setForm((prev) => ({ ...prev, participant_description: e.target.value }))}
              className="w-full min-h-[100px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
            />
          </div>

          <div className="mt-4">
            <label className="text-white text-sm mb-2 block">Флаг</label>
            <input
              type="text"
              value={form.flag}
              onChange={(e) => setForm((prev) => ({ ...prev, flag: e.target.value }))}
              className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
              placeholder="flag{...}"
            />
          </div>
        </>
      )}

      {tab === 'edit' && (
        <div className="border border-white/[0.08] rounded-[16px] p-4">
          {tasksLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <SkeletonBlock key={i} className="h-16 w-full rounded-[12px]" />
              ))}
            </div>
          ) : tasks.length === 0 ? (
            <div className="text-white/50 text-[14px]">Задач пока нет</div>
          ) : (
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  onClick={() => onEditTask?.(task.id)}
                  className="flex items-center justify-between p-3 rounded-[12px] border border-white/10 bg-white/[0.02] hover:border-[#9B6BFF]/40 transition cursor-pointer"
                >
                  <div className="flex-1">
                    <div className="text-white text-[14px] font-medium">{task.title}</div>
                    <div className="text-white/40 text-[12px] mt-1">
                      {task.category} • Сложность: {task.difficulty} • {task.points} баллов • {task.state}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] uppercase tracking-[0.15em] px-2 py-1 rounded-full bg-white/5 border border-white/10 text-white/60">
                      {task.access_type}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
          {tasks.length > 0 && (
            <div className="text-white/50 text-[13px] mt-3">
              Всего задач: {tasks.length}
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}

export default TaskManagerDrawer;
