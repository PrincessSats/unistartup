import React from 'react';

function FeedbackResolver({ feedback, onConfirm, onCancel, isResolving, error }) {
  if (!feedback) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
      <div className="w-full max-w-[520px] rounded-[20px] border border-white/10 bg-[#0B0A10] p-6">
        <div className="text-[22px] leading-[28px] text-white">
          Отметить отзыв как решённый?
        </div>
        <div className="mt-3 text-[14px] text-white/60">
          После подтверждения отзыв исчезнет из блока последних сообщений.
        </div>
        <div className="mt-4 rounded-[12px] border border-white/10 bg-white/[0.03] p-3">
          <div className="text-[13px] text-white/80">
            {feedback.username || `Пользователь #${feedback.user_id}`}
          </div>
          <div className="mt-2 text-[12px] text-white/50">
            {feedback.topic}
          </div>
          <div className="mt-2 text-[14px] text-white/70">
            {feedback.message}
          </div>
        </div>
        {error && (
          <div className="mt-4 rounded-[12px] border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-[13px] text-rose-200">
            {error}
          </div>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isResolving}
            className="h-10 px-4 rounded-[10px] border border-white/10 bg-white/[0.03] text-white/80 hover:bg-white/[0.06] disabled:opacity-60 disabled:cursor-not-allowed"
          >
            Нет
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isResolving}
            className="h-10 px-4 rounded-[10px] border border-emerald-400/50 bg-emerald-500/20 text-emerald-200 hover:bg-emerald-500/30 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isResolving ? 'Сохраняем...' : 'Да'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default FeedbackResolver;
