import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AuthShell, AuthSurface } from '../components/AuthUI';
import { authAPI, profileAPI } from '../services/api';

function AuthBridge() {
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const finishBridge = async () => {
      try {
        const params = new URLSearchParams(location.search);
        const flowToken = params.get('flow_token');

        if (flowToken) {
          // OAuth callback - exchange flow_token for access token and session
          await authAPI.finalizeOAuth(flowToken);
        } else {
          // Session refresh fallback (shouldn't normally happen)
          await authAPI.refresh({ timeoutMs: 8000 });
        }

        const profile = await profileAPI.getProfile();
        if (cancelled) return;
        navigate(profile?.role === 'admin' ? '/admin' : '/home', { replace: true });
      } catch {
        if (cancelled) return;
        authAPI.logout({ remote: false, redirect: false });
        setError('Не удалось завершить вход через внешний аккаунт. Попробуй еще раз.');
        window.setTimeout(() => {
          navigate('/login?reason=session_expired', { replace: true });
        }, 1200);
      }
    };

    finishBridge();
    return () => {
      cancelled = true;
    };
  }, [navigate, location.search]);

  return (
    <AuthShell title={error ? 'Вход не завершен' : 'Завершаем вход'}>
      <AuthSurface className="max-w-[420px] px-10 py-10 text-center">
        <div className="space-y-3">
          <p className="text-[15px] leading-6 text-white/70">
            {error || 'Подтверждаем сессию и загружаем профиль после входа через внешний аккаунт.'}
          </p>
          {!error ? (
            <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-white/15 border-t-[#8452FF]" aria-hidden="true" />
          ) : null}
        </div>
      </AuthSurface>
    </AuthShell>
  );
}

export default AuthBridge;
