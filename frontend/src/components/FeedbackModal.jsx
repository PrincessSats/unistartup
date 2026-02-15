import React, { useEffect, useState } from 'react';
import { feedbackAPI } from '../services/api';
import AppIcon from './AppIcon';

function FeedbackModal({ open, onClose }) {
  const topics = [
    'Структура платформы',
    'Чемпионат',
    'Начисление баллов',
    'Турнирная таблица',
    'Другое',
  ];

  const [topic, setTopic] = useState('');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setTopic('');
    setMessage('');
    setStatus('idle');
    setError('');
  }, [open]);

  if (!open) return null;

  const trimmedMessage = message.trim();
  const canSubmit = topic && trimmedMessage.length > 0 && trimmedMessage.length <= 123;

  const handleSubmit = async () => {
    if (!canSubmit || status === 'sending') return;
    try {
      setStatus('sending');
      setError('');
      await feedbackAPI.submitFeedback(topic, trimmedMessage);
      setStatus('success');
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Не удалось отправить отзыв');
      setStatus('idle');
    }
  };

  const handleMessageChange = (event) => {
    const value = event.target.value.slice(0, 123);
    setMessage(value);
  };

  const handleOverlayClick = (event) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[6px] px-4"
      onClick={handleOverlayClick}
    >
      {status === 'success' ? (
        <div className="relative w-full max-w-[600px] rounded-[20px] bg-[#9B6BFF]/[0.14] backdrop-blur-[32px] shadow-[0_20px_50px_rgba(11,10,16,0.21)] p-8">
          <button onClick={onClose} className="absolute right-5 top-5">
            <AppIcon name="close" className="w-[22px] h-[22px] text-white/80" />
          </button>
          <div className="flex flex-col gap-4">
            <h3 className="text-[23px] leading-[28px] tracking-[0.02em] text-white">
              Получили твой отзыв! Уже ставим задачки в роадмап
            </h3>
            <p className="text-[16px] leading-[20px] tracking-[0.04em] text-white/60">
              Обещаем улучшить все, что можем, и сделать платформу
              еще удобнее для тебя! Если появятся новые комментарии или
              вопросы — напиши в поддержку
            </p>
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="bg-[#9B6BFF] rounded-[10px] px-6 py-3 text-[16px] leading-[20px] tracking-[0.04em] text-white"
              >
                Понятно
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="relative w-full max-w-[600px] rounded-[20px] bg-[#9B6BFF]/[0.14] backdrop-blur-[32px] shadow-[0_20px_50px_rgba(11,10,16,0.21)] p-8">
          <button onClick={onClose} className="absolute right-5 top-5">
            <AppIcon name="close" className="w-[22px] h-[22px] text-white/80" />
          </button>
          <div className="flex flex-col gap-6">
            <div>
              <h3 className="text-[23px] leading-[28px] tracking-[0.02em] text-white">
                Оцени работу платформы
              </h3>
              <p className="mt-3 text-[16px] leading-[20px] tracking-[0.04em] text-white/60">
                Выбери тему, по которой хочешь оставить обратную связь
              </p>
            </div>

            <div className="flex flex-col gap-2">
              {topics.map((item) => {
                const selected = item === topic;
                return (
                  <button
                    key={item}
                    onClick={() => setTopic(item)}
                    className={`flex items-center justify-between rounded-[12px] px-5 py-4 text-left text-[16px] leading-[20px] tracking-[0.04em] transition-colors ${
                      selected
                        ? 'bg-white/[0.09] text-white'
                        : 'bg-white/[0.05] text-white/80 hover:bg-white/[0.08]'
                    }`}
                  >
                    <span>{item}</span>
                    <span
                      className={`flex h-5 w-5 items-center justify-center rounded-full border ${
                        selected ? 'border-[#9B6BFF]' : 'border-white/20'
                      }`}
                    >
                      {selected && <span className="h-2.5 w-2.5 rounded-full bg-[#9B6BFF]" />}
                    </span>
                  </button>
                );
              })}
            </div>

            {topic && (
              <div className="relative">
                <textarea
                  value={message}
                  onChange={handleMessageChange}
                  placeholder="Здесь можешь оставить свои пожелания, проблемы, с которыми столкнулся, или просто поблагодарить нас:)"
                  className="h-[150px] w-full resize-none rounded-[12px] bg-white/[0.05] p-4 text-[16px] leading-[20px] tracking-[0.04em] text-white placeholder:text-white/40 focus:outline-none"
                />
                <span className="absolute bottom-3 right-4 text-[12px] leading-[16px] text-white/40">
                  {message.length}/123
                </span>
              </div>
            )}

            {error && <div className="text-[14px] text-red-300">{error}</div>}

            <div className="flex justify-end">
              <button
                onClick={handleSubmit}
                disabled={!canSubmit || status === 'sending'}
                className={`rounded-[10px] px-6 py-3 text-[16px] leading-[20px] tracking-[0.04em] ${
                  canSubmit
                    ? 'bg-[#9B6BFF] text-white'
                    : 'bg-white/[0.08] text-white/40'
                }`}
              >
                {status === 'sending' ? 'Отправка...' : 'Отправить'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default FeedbackModal;
