import React from 'react';
import SectionCard from '../Widgets/SectionCard';
import { MessageIcon, FlagIcon } from '../Widgets/Icons';

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

function FeedbackPanel({ feedbacks, onResolve }) {
  return (
    <SectionCard
      title="Последние отзывы"
      subtitle="Свежие сообщения из формы обратной связи"
      action={(
        <div className="w-9 h-9 rounded-full bg-white/10 flex items-center justify-center text-white/60">
          <MessageIcon className="w-4 h-4" />
        </div>
      )}
    >
      <div className="flex flex-col gap-4">
        {feedbacks.length === 0 && (
          <div className="text-[14px] text-white/50">
            Пока нет отзывов
          </div>
        )}
        {feedbacks.map((feedback) => (
          <div key={feedback.id} className="border-b border-white/10 last:border-b-0 pb-4 last:pb-0">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[14px] text-white">
                    {feedback.username || `Пользователь #${feedback.user_id}`}
                  </span>
                  <span className="text-[12px] uppercase tracking-[0.18em] px-2 py-1 rounded-full bg-[#9B6BFF]/15 text-[#CBB6FF] border border-[#9B6BFF]/30">
                    {feedback.topic}
                  </span>
                </div>
                <div className="text-[14px] text-white/60 mt-2">
                  {feedback.message}
                </div>
                <div className="text-[12px] text-white/40 mt-2">
                  {formatRelativeTime(feedback.created_at)}
                </div>
              </div>
              <button
                type="button"
                onClick={() => onResolve(feedback)}
                className="h-8 w-8 rounded-[10px] border border-emerald-400/50 bg-emerald-500/20 text-emerald-300 transition-colors hover:bg-emerald-500/30 flex items-center justify-center"
                title="Отметить как решённый"
                aria-label="Отметить отзыв как решённый"
              >
                <FlagIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

export default FeedbackPanel;
