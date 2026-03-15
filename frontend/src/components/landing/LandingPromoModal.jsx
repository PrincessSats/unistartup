import React, { useEffect, useState } from 'react';

function CopyGlyph({ copied }) {
  if (copied) {
    return (
      <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="m4.75 10.25 3 3 7.5-7.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6">
      <rect x="7" y="4.5" width="8" height="10" rx="1.8" />
      <path d="M4.75 10.75V6.8A1.8 1.8 0 0 1 6.55 5H10" strokeLinecap="round" />
    </svg>
  );
}

export default function LandingPromoModal({ open, promoCode, onClose }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!open) {
      setCopied(false);
    }
  }, [open]);

  if (!open) return null;

  const handleCopy = async () => {
    if (!promoCode) return;
    try {
      await navigator.clipboard.writeText(promoCode);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="landing-figma-modal" role="dialog" aria-modal="true" aria-labelledby="landing-promo-title">
      <div className="landing-figma-modal__backdrop" onClick={onClose} aria-hidden="true" />

      <div className="landing-figma-modal__panel">
        <button
          type="button"
          onClick={onClose}
          className="landing-figma-modal__close"
          aria-label="Закрыть модальное окно"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7">
            <path d="m5 5 10 10M15 5 5 15" strokeLinecap="round" />
          </svg>
        </button>

        <div className="landing-figma-modal__content">
          <div className="landing-figma-modal__heading">
            <h3 id="landing-promo-title">Поздравляем, ты нашел все баги!</h3>
            <p>
              Дарим промокод на 10 баллов в рейтинг обучения. Для активации зарегистрируйся на
              платформе и введи промокод в личном кабинете. Срок действия — 3 дня с момента
              получения
            </p>
          </div>

          <div className="landing-figma-modal__code">
            <span className="landing-figma-modal__code-label">Промокод:</span>
            <span className="landing-figma-modal__code-value">{promoCode || '-----'}</span>
            <button
              type="button"
              onClick={handleCopy}
              className={`landing-figma-modal__copy ${copied ? 'is-copied' : ''}`}
              aria-label="Скопировать промокод"
            >
              <CopyGlyph copied={copied} />
            </button>
          </div>

          <div className="landing-figma-modal__footer">
            <button type="button" onClick={onClose} className="landing-figma-modal__done">
              Спасибо
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
