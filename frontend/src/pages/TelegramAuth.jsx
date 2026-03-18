import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AuthShell, AuthSurface, AuthPrimaryButton } from '../components/AuthUI';
import { authAPI } from '../services/api';

const TELEGRAM_WIDGET_SRC = 'https://telegram.org/js/telegram-widget.js?22';
const TELEGRAM_BOT_USERNAME = String(process.env.REACT_APP_TELEGRAM_BOT_USERNAME || 'hacknet_team_bot').trim();
const TELEGRAM_WIDGET_CALLBACK = '__hacknetTelegramWidgetAuth';

function parseBool(value) {
  return String(value || '').trim().toLowerCase() === 'true';
}

function TelegramAuth() {
  const navigate = useNavigate();
  const location = useLocation();
  const widgetContainerRef = useRef(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');

  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const intent = params.get('intent') === 'register' ? 'register' : 'login';
  const termsAccepted = parseBool(params.get('terms_accepted'));
  const marketingOptIn = parseBool(params.get('marketing_opt_in'));

  useEffect(() => {
    if (!widgetContainerRef.current) return undefined;
    if (!TELEGRAM_BOT_USERNAME) {
      setError('Не задан username Telegram-бота для login widget.');
      return undefined;
    }

    const container = widgetContainerRef.current;
    container.innerHTML = '';
    setStatus('ready');
    setError('');

    window[TELEGRAM_WIDGET_CALLBACK] = async (telegramUser) => {
      setStatus('verifying');
      setError('');
      try {
        const result = await authAPI.completeTelegramAuth({
          intent,
          termsAccepted,
          marketingOptIn,
          telegramUser,
        });

        if (result?.status === 'authenticated') {
          navigate('/auth/bridge?provider=telegram', { replace: true });
          return;
        }

        if (result?.status === 'registration_required' && result?.flow_token) {
          navigate(`/register?flow_token=${encodeURIComponent(result.flow_token)}`, { replace: true });
          return;
        }

        throw new Error('Unexpected Telegram auth response');
      } catch (err) {
        const detail = err?.response?.data?.detail;
        setStatus('error');
        setError(typeof detail === 'string' ? detail : 'Не удалось завершить вход через Telegram. Попробуй еще раз.');
      }
    };

    const script = document.createElement('script');
    script.async = true;
    script.src = TELEGRAM_WIDGET_SRC;
    script.setAttribute('data-telegram-login', TELEGRAM_BOT_USERNAME);
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-radius', '10');
    script.setAttribute('data-userpic', 'false');
    script.setAttribute('data-onauth', `${TELEGRAM_WIDGET_CALLBACK}(user)`);
    container.appendChild(script);

    return () => {
      container.innerHTML = '';
      delete window[TELEGRAM_WIDGET_CALLBACK];
    };
  }, [intent, marketingOptIn, navigate, termsAccepted]);

  return (
    <AuthShell title={intent === 'register' ? 'Telegram' : 'Вход через Telegram'}>
      <AuthSurface className="max-w-[520px] text-center">
        <div className="space-y-8">
          <div className="space-y-3">
            <p className="text-[16px] leading-7 text-white/70">
              {intent === 'register'
                ? 'Подтверди аккаунт через официальный Telegram Login Widget. Если аккаунт новый, после этого попросим email для завершения регистрации.'
                : 'Подтверди аккаунт через официальный Telegram Login Widget. Если аккаунт уже связан, вход завершится автоматически.'}
            </p>
            {error ? (
              <div className="rounded-[18px] border border-[#FF5A6E]/35 bg-[#FF5A6E]/10 px-4 py-3 text-[14px] leading-6 text-[#FFD6DB]">
                {error}
              </div>
            ) : null}
          </div>

          <div className="flex min-h-[64px] items-center justify-center rounded-[18px] border border-white/10 bg-white/[0.03] px-4 py-5">
            <div ref={widgetContainerRef} />
            {status === 'verifying' ? (
              <div className="space-y-3">
                <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-white/15 border-t-[#8452FF]" aria-hidden="true" />
                <p className="text-[14px] leading-6 text-white/60">Проверяем данные Telegram и создаем сессию.</p>
              </div>
            ) : null}
          </div>

          <AuthPrimaryButton
            type="button"
            className="bg-white/[0.05] text-white hover:bg-white/[0.07]"
            onClick={() => navigate(intent === 'register' ? '/register' : '/login', { replace: true })}
          >
            Вернуться назад
          </AuthPrimaryButton>
        </div>
      </AuthSurface>
    </AuthShell>
  );
}

export default TelegramAuth;
