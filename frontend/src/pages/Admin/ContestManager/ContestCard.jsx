import React, { useState } from 'react';
import ContestCreateModal from '../../../components/ContestCreateModal';
import { adminAPI } from '../../../services/api';

const initialGenState = {
  count: 1,
  mode: 'filter',
  base_difficulty: 8,
  cvss_min: '',
  cvss_max: '',
  cwe_ids: '',
  tags: '',
};

function ChampionshipGenModal({ contestId, onClose, onSuccess }) {
  const [form, setForm] = useState(initialGenState);
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);

  const handleSubmit = async () => {
    setStatus('sending');
    setResult(null);
    try {
      const payload = {
        count: Number(form.count) || 1,
        mode: form.mode,
        base_difficulty: Number(form.base_difficulty) || 8,
      };
      if (form.mode === 'filter') {
        payload.filters = {
          cvss_min: form.cvss_min ? parseFloat(form.cvss_min) : undefined,
          cvss_max: form.cvss_max ? parseFloat(form.cvss_max) : undefined,
          cwe_ids: form.cwe_ids ? form.cwe_ids.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
          tags: form.tags ? form.tags.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
        };
      }
      const res = await adminAPI.generateChampionshipTasks(contestId, payload);
      setResult(res);
      if (res.created?.length > 0) onSuccess?.();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setResult({ error: typeof detail === 'string' ? detail : 'Ошибка генерации' });
    } finally {
      setStatus('idle');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="text-white font-semibold text-lg">Генерация чемпионатных задач</div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition text-xl leading-none">✕</button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-slate-400 text-xs mb-1 block">Количество (1–5)</label>
            <input type="number" min="1" max="5" value={form.count}
              onChange={(e) => setForm((p) => ({ ...p, count: e.target.value }))}
              className="w-full h-9 bg-slate-800 border border-slate-600 rounded-lg px-3 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label className="text-slate-400 text-xs mb-1 block">Сложность (7–10)</label>
            <input type="number" min="7" max="10" value={form.base_difficulty}
              onChange={(e) => setForm((p) => ({ ...p, base_difficulty: e.target.value }))}
              className="w-full h-9 bg-slate-800 border border-slate-600 rounded-lg px-3 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
        </div>

        <div>
          <label className="text-slate-400 text-xs mb-1 block">Источник CVE</label>
          <div className="flex gap-2">
            {[['filter', 'По фильтрам'], ['explicit', 'По ID записей']].map(([m, label]) => (
              <button key={m} type="button" onClick={() => setForm((p) => ({ ...p, mode: m }))}
                className={`px-3 py-1.5 rounded-lg text-xs transition ${form.mode === m ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}>
                {label}
              </button>
            ))}
          </div>
        </div>

        {form.mode === 'filter' && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-slate-400 text-xs mb-1 block">CVSS мин</label>
                <input type="number" min="0" max="10" step="0.1" placeholder="напр. 7.0"
                  value={form.cvss_min} onChange={(e) => setForm((p) => ({ ...p, cvss_min: e.target.value }))}
                  className="w-full h-9 bg-slate-800 border border-slate-600 rounded-lg px-3 text-white text-sm focus:outline-none focus:border-blue-500" />
              </div>
              <div>
                <label className="text-slate-400 text-xs mb-1 block">CVSS макс</label>
                <input type="number" min="0" max="10" step="0.1" placeholder="напр. 10.0"
                  value={form.cvss_max} onChange={(e) => setForm((p) => ({ ...p, cvss_max: e.target.value }))}
                  className="w-full h-9 bg-slate-800 border border-slate-600 rounded-lg px-3 text-white text-sm focus:outline-none focus:border-blue-500" />
              </div>
            </div>
            <div>
              <label className="text-slate-400 text-xs mb-1 block">CWE (через запятую)</label>
              <input type="text" placeholder="напр. CWE-89, CWE-79" value={form.cwe_ids}
                onChange={(e) => setForm((p) => ({ ...p, cwe_ids: e.target.value }))}
                className="w-full h-9 bg-slate-800 border border-slate-600 rounded-lg px-3 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="text-slate-400 text-xs mb-1 block">Теги (через запятую)</label>
              <input type="text" placeholder="напр. sqli, xss, rce" value={form.tags}
                onChange={(e) => setForm((p) => ({ ...p, tags: e.target.value }))}
                className="w-full h-9 bg-slate-800 border border-slate-600 rounded-lg px-3 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
          </div>
        )}

        {result && (
          <div className={`text-sm px-3 py-2 rounded-lg ${result.error ? 'bg-red-900/30 text-red-300 border border-red-700/50' : 'bg-green-900/30 text-green-300 border border-green-700/50'}`}>
            {result.error
              ? result.error
              : `✓ Создано задач: ${result.created?.length || 0}${result.failed?.length ? ` · ошибок: ${result.failed.length}` : ''}`}
          </div>
        )}

        <div className="flex gap-3 pt-1">
          <button type="button" onClick={onClose}
            className="flex-1 h-10 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition">
            Закрыть
          </button>
          <button type="button" onClick={handleSubmit} disabled={status === 'sending'}
            className="flex-1 h-10 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm transition disabled:opacity-60 disabled:cursor-not-allowed">
            {status === 'sending' ? 'Генерация...' : 'Генерировать'}
          </button>
        </div>
      </div>
    </div>
  );
}

const getStatusBadge = (contest) => {
  const now = new Date();
  const startAt = new Date(contest.start_at);
  const endAt = new Date(contest.end_at);

  if (now < startAt) {
    return { label: '◷ СКОРО', color: 'text-amber-400' };
  } else if (now > endAt) {
    return { label: '● ЗАВЕРШЕН', color: 'text-slate-400' };
  } else {
    return { label: '● АКТИВЕН', color: 'text-green-400' };
  }
};

export default function ContestCard({ contest, isCurrent, onEditSuccess, onDeleteSuccess }) {
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isGenModalOpen, setIsGenModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showActionMenu, setShowActionMenu] = useState(false);
  const status = getStatusBadge(contest);

  const handleDelete = async () => {
    if (!window.confirm(`Удалить чемпионат "${contest.title}"? Это необратимо.`)) {
      return;
    }

    try {
      setIsDeleting(true);
      await adminAPI.deleteContest(contest.id);
      onDeleteSuccess?.();
    } catch (err) {
      console.error('Delete failed:', err);
      alert(err.response?.data?.detail || 'Ошибка удаления');
    } finally {
      setIsDeleting(false);
      setShowActionMenu(false);
    }
  };

  const handleEndNow = async () => {
    if (!window.confirm(`Завершить чемпионат "${contest.title}" прямо сейчас?`)) {
      return;
    }

    try {
      await adminAPI.endContestNow(contest.id);
      onEditSuccess?.();
    } catch (err) {
      console.error('End contest failed:', err);
      alert(err.response?.data?.detail || 'Ошибка завершения');
    }
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const isActive = new Date(contest.start_at) <= new Date() && new Date(contest.end_at) >= new Date();

  return (
    <>
      <div className={`p-4 rounded-lg border transition ${
        isCurrent
          ? 'bg-slate-800 border-blue-500 shadow-lg shadow-blue-500/20'
          : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
      }`}>
        {/* Заголовок */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-white">{contest.title}</h3>
            <p className={`text-sm font-medium ${status.color}`}>{status.label}</p>
          </div>

          {/* Меню действий */}
          <div className="relative">
            <button
              onClick={() => setShowActionMenu(!showActionMenu)}
              className="p-2 hover:bg-slate-700 rounded text-slate-300 transition"
            >
              ⋮
            </button>

            {showActionMenu && (
              <div className="absolute right-0 mt-1 w-48 bg-slate-900 border border-slate-700 rounded-lg shadow-lg z-10">
                <button
                  onClick={() => {
                    setIsEditModalOpen(true);
                    setShowActionMenu(false);
                  }}
                  className="w-full text-left px-4 py-2 hover:bg-slate-800 text-slate-200 transition"
                >
                  ✏️ Редактировать
                </button>

                <button
                  onClick={() => {
                    setIsGenModalOpen(true);
                    setShowActionMenu(false);
                  }}
                  className="w-full text-left px-4 py-2 hover:bg-slate-800 text-blue-300 transition border-t border-slate-700"
                >
                  ⚡ Генерировать задачи
                </button>

                {isActive && (
                  <button
                    onClick={handleEndNow}
                    className="w-full text-left px-4 py-2 hover:bg-slate-800 text-slate-200 transition border-t border-slate-700"
                  >
                    ⏹️ Завершить
                  </button>
                )}

                <button
                  onClick={() => {
                    // TODO: Модальное окно просмотра отправок
                    setShowActionMenu(false);
                  }}
                  className="w-full text-left px-4 py-2 hover:bg-slate-800 text-slate-200 transition border-t border-slate-700"
                >
                  📋 Просмотр отправок
                </button>

                <button
                  onClick={handleDelete}
                  disabled={isDeleting}
                  className="w-full text-left px-4 py-2 hover:bg-red-900/20 text-red-400 transition border-t border-slate-700 disabled:opacity-50"
                >
                  🗑️ Удалить
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Сетка деталей */}
        <div className="grid grid-cols-2 gap-3 mb-3 text-sm text-slate-300">
          <div>
            <span className="text-slate-400">Начало:</span> {formatDate(contest.start_at)}
          </div>
          <div>
            <span className="text-slate-400">Конец:</span> {formatDate(contest.end_at)}
          </div>
          <div>
            <span className="text-slate-400">Задания:</span> {contest.tasks_count || 0}
          </div>
          <div>
            <span className="text-slate-400">Участники:</span> {contest.participant_count || 0}
          </div>
        </div>

        {/* Флаги */}
        <div className="flex gap-2 text-xs text-slate-400">
          {contest.is_public ? (
            <span className="px-2 py-1 bg-slate-700 rounded">🔓 Публичный</span>
          ) : (
            <span className="px-2 py-1 bg-slate-700 rounded">🔒 Приватный</span>
          )}
          {contest.leaderboard_visible ? (
            <span className="px-2 py-1 bg-slate-700 rounded">📊 Лидерборд видим</span>
          ) : (
            <span className="px-2 py-1 bg-slate-700 rounded">📊 Лидерборд скрыт</span>
          )}
        </div>
      </div>

      {/* Модальное окно редактирования */}
      {isEditModalOpen && (
        <ContestCreateModal
          isOpen={isEditModalOpen}
          contestId={contest.id}
          onClose={() => setIsEditModalOpen(false)}
          onSuccess={() => {
            setIsEditModalOpen(false);
            onEditSuccess?.();
          }}
        />
      )}

      {/* Модальное окно генерации чемпионатных задач */}
      {isGenModalOpen && (
        <ChampionshipGenModal
          contestId={contest.id}
          onClose={() => setIsGenModalOpen(false)}
          onSuccess={() => onEditSuccess?.()}
        />
      )}
    </>
  );
}
