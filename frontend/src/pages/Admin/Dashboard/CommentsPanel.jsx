import React, { useState, useEffect, useCallback } from 'react';
import SectionCard from '../Widgets/SectionCard';

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

const LIMIT = 20;

function CommentsPanel() {
  const [comments, setComments] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (off, replace) => {
    setLoading(true);
    try {
      const { adminAPI } = await import('../../../services/api');
      const data = await adminAPI.getComments({ limit: LIMIT, offset: off });
      setComments((prev) => replace ? data : [...prev, ...data]);
      setHasMore(data.length === LIMIT);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(0, true);
  }, [load]);

  const handleLoadMore = () => {
    const next = offset + LIMIT;
    setOffset(next);
    load(next, false);
  };

  return (
    <SectionCard
      title="Комментарии к статьям"
      subtitle="Все комментарии пользователей в базе знаний"
      action={(
        <div className="w-9 h-9 rounded-full bg-white/10 flex items-center justify-center text-white/60">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-3.133a1.2 1.2 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" />
          </svg>
        </div>
      )}
    >
      <div className="flex flex-col gap-4 max-h-[500px] overflow-y-auto pr-1">
        {comments.length === 0 && !loading && (
          <div className="text-[14px] text-white/50">Нет комментариев</div>
        )}
        {comments.map((comment) => (
          <div key={comment.id} className="border-b border-white/10 last:border-b-0 pb-4 last:pb-0">
            <div className="flex items-start gap-3">
              {comment.avatar_url ? (
                <img
                  src={comment.avatar_url}
                  alt=""
                  className="w-8 h-8 rounded-full object-cover flex-shrink-0 mt-0.5"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-[#9B6BFF]/20 flex items-center justify-center flex-shrink-0 mt-0.5 text-[#CBB6FF] text-[13px] font-medium">
                  {(comment.username || '?')[0].toUpperCase()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] text-white">
                    {comment.username || `Пользователь #${comment.user_id}`}
                  </span>
                  {comment.entry_title && (
                    <span className="text-[12px] text-white/40 truncate max-w-[200px]">
                      → {comment.entry_title}
                    </span>
                  )}
                </div>
                <div className="text-[14px] text-white/60 mt-1 line-clamp-3">{comment.body}</div>
                <div className="text-[12px] text-white/40 mt-1">{formatRelativeTime(comment.created_at)}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {hasMore && (
        <button
          type="button"
          onClick={handleLoadMore}
          disabled={loading}
          className="mt-4 w-full h-8 rounded-[10px] border border-white/10 text-white/50 text-[13px] hover:border-white/20 hover:text-white/70 transition-colors disabled:opacity-40"
        >
          {loading ? 'Загрузка...' : 'Загрузить ещё'}
        </button>
      )}
    </SectionCard>
  );
}

export default CommentsPanel;
