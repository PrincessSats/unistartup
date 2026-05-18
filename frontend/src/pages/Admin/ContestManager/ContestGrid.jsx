import React, { useMemo } from 'react';
import ContestCard from './ContestCard';

export default function ContestGrid({ contests, pageSize, onPageSizeChange, onEditSuccess, onDeleteSuccess }) {
  // Найти текущий/активный чемпионат
  const currentContest = useMemo(() => {
    const now = new Date();
    return contests.find(c => new Date(c.start_at) <= now && new Date(c.end_at) >= now);
  }, [contests]);

  // Другие чемпионаты
  const otherContests = useMemo(() => {
    return contests.filter(c => c.id !== currentContest?.id);
  }, [contests, currentContest]);

  // Переместить другие чемпионаты
  const paginatedOther = useMemo(() => {
    return otherContests.slice(0, pageSize);
  }, [otherContests, pageSize]);

  const hasMore = otherContests.length > pageSize;

  return (
    <div className="space-y-6">
      {/* Текущий чемпионат - выделено */}
      {currentContest && (
        <div>
          <h2 className="text-sm uppercase tracking-wide text-slate-400 font-semibold mb-3">
            Активный чемпионат
          </h2>
          <ContestCard
            contest={currentContest}
            isCurrent={true}
            onEditSuccess={onEditSuccess}
            onDeleteSuccess={onDeleteSuccess}
          />
        </div>
      )}

      {/* Другие чемпионаты */}
      {otherContests.length > 0 && (
        <div>
          <h2 className="text-sm uppercase tracking-wide text-slate-400 font-semibold mb-3">
            Остальные чемпионаты
          </h2>
          <div className="space-y-3">
            {paginatedOther.map(contest => (
              <ContestCard
                key={contest.id}
                contest={contest}
                isCurrent={false}
                onEditSuccess={onEditSuccess}
                onDeleteSuccess={onDeleteSuccess}
              />
            ))}
          </div>

          {/* Загрузить ещё / Пагинация */}
          {hasMore && (
            <button
              onClick={() => onPageSizeChange(prev => prev + 6)}
              className="mt-4 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded font-medium transition"
            >
              Загрузить ещё ({otherContests.length - pageSize} осталось)
            </button>
          )}
        </div>
      )}

      {/* Пустое состояние */}
      {contests.length === 0 && (
        <div className="p-8 text-center bg-slate-800 rounded-lg border border-slate-700">
          <p className="text-slate-400">Чемпионатов не найдено. Создайте новый чемпионат.</p>
        </div>
      )}
    </div>
  );
}
