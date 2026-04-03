import React, { useState } from 'react';
import ContestCreateModal from '../../../components/ContestCreateModal';
import { adminAPI } from '../../../services/api';

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
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-white">{contest.title}</h3>
            <p className={`text-sm font-medium ${status.color}`}>{status.label}</p>
          </div>

          {/* Action menu */}
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
                    // TODO: View submissions modal
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

        {/* Details grid */}
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

        {/* Flags */}
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

      {/* Edit Modal */}
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
    </>
  );
}
