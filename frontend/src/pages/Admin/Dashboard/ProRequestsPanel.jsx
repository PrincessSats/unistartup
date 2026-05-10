import React, { useState, useEffect, useCallback } from 'react';
import SectionCard from '../Widgets/SectionCard';
import { ProRequestIcon } from '../Widgets/Icons';

function formatRelativeTime(value) {
  if (!value) return 'Без даты';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Без даты';
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60000) return 'Только что';
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return `${diffMin} мин назад`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours} ч назад`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} дн назад`;
}

function ProRequestsPanel() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { adminAPI } = await import('../../../services/api');
      const data = await adminAPI.getProRequests();
      setRequests(Array.isArray(data) ? data : []);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <SectionCard
      title="Заявки на Pro"
      subtitle={`${requests.length} заявок`}
      action={(
        <div className="w-9 h-9 rounded-full bg-white/10 flex items-center justify-center text-white/60">
          <ProRequestIcon className="w-4 h-4" />
        </div>
      )}
    >
      <div className="flex flex-col gap-4 max-h-[460px] overflow-y-auto pr-1">
        {requests.length === 0 && !loading && (
          <div className="text-[14px] text-white/50">Пока нет заявок</div>
        )}
        {requests.map((req) => (
          <div key={req.user_id} className="border-b border-white/10 last:border-b-0 pb-4 last:pb-0">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] text-white truncate">
                    {req.username || `Пользователь #${req.user_id}`}
                  </span>
                </div>
                {req.email && (
                  <div className="text-[13px] text-white/60 mt-1 truncate">{req.email}</div>
                )}
                <div className="text-[12px] text-white/40 mt-1">{formatRelativeTime(req.created_at)}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={load}
        disabled={loading}
        className="mt-4 w-full h-8 rounded-[10px] border border-white/10 text-white/50 text-[13px] hover:border-white/20 hover:text-white/70 transition-colors disabled:opacity-40"
      >
        {loading ? 'Загрузка...' : 'Обновить'}
      </button>
    </SectionCard>
  );
}

export default ProRequestsPanel;
