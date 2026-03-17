import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  AuthPrimaryButton,
  AuthShell,
  AuthSurface,
  PasswordVisibilityButton,
  SocialAuthButtons,
} from '../components/AuthUI';
import { authAPI, profileAPI } from '../services/api';

function mapAuthNotice(search) {
  const params = new URLSearchParams(search);
  const reason = String(params.get('reason') || '').trim();
  const error = String(params.get('error') || '').trim();

  if (reason === 'account_blocked' || error === 'account_blocked') {
    return { error: 'Аккаунт заблокирован. Обратитесь к администратору.', notice: '' };
  }
  if (reason === 'session_expired') {
    return { error: '', notice: 'Сессия завершена. Войдите снова, чтобы продолжить.' };
  }
  if (reason === 'account_deleted') {
    return { error: '', notice: 'Аккаунт удалён.' };
  }
  if (reason === 'network_timeout') {
    return { error: '', notice: 'Не удалось быстро подтвердить сессию. Просто войдите снова.' };
  }
  if (error === 'yandex_access_denied') {
    return { error: '', notice: 'Вход через Яндекс был отменен.' };
  }
  if (error === 'yandex_missing_code' || error === 'yandex_state_invalid') {
    return { error: 'Сессия входа через Яндекс устарела. Начни вход заново.', notice: '' };
  }
  if (error === 'yandex_oauth_failed') {
    return { error: 'Не удалось завершить вход через Яндекс. Попробуй еще раз.', notice: '' };
  }
  return { error: '', notice: '' };
}

function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    authAPI.warmup();
    const messageState = mapAuthNotice(location.search);
    setError(messageState.error);
    setNotice(messageState.notice);
  }, [location.search]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setNotice('');
    setLoading(true);

    let lastErr;
    for (let attempt = 0; attempt <= 1; attempt += 1) {
      if (attempt > 0) {
        await new Promise((resolve) => {
          window.setTimeout(resolve, 1500);
        });
      }

      try {
        await authAPI.login(formData.email, formData.password);
        let redirectTo = '/home';
        try {
          const profile = await profileAPI.getProfile();
          if (profile?.role === 'admin') {
            redirectTo = '/admin';
          }
        } catch {
          // Ignore profile lookup failure and keep /home fallback.
        }
        navigate(redirectTo, { replace: true });
        return;
      } catch (err) {
        lastErr = err;
        if (err?.response || err?.message === 'API base URL is not configured') {
          break;
        }
      }
    }

    if (lastErr?.message === 'API base URL is not configured') {
      setError('Не настроен REACT_APP_API_BASE_URL для production-сборки.');
    } else if (!lastErr?.response) {
      setError('Не удалось подключиться к серверу. Попробуйте снова.');
    } else {
      setError(lastErr.response?.data?.detail || 'Ошибка входа');
    }
    setLoading(false);
  };

  return (
    <AuthShell title="Вход">
      <AuthSurface>
        <form onSubmit={handleSubmit} className="space-y-8">
          {notice && !error ? (
            <div className="rounded-[18px] border border-sky-400/25 bg-sky-400/10 px-4 py-3 text-[14px] leading-6 text-sky-50">
              {notice}
            </div>
          ) : null}
          {error ? (
            <div className="rounded-[18px] border border-[#FF5A6E]/35 bg-[#FF5A6E]/10 px-4 py-3 text-[14px] leading-6 text-[#FFD6DB]">
              {error}
            </div>
          ) : null}

          <div className="space-y-4">
            <label className="block">
              <span className="mb-2 block text-[14px] leading-5 text-white/56">Электронная почта</span>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="Твой адрес электронной почты"
                autoComplete="email"
                required
                className="h-14 w-full rounded-[18px] border border-white/10 bg-[#0D0B13] px-4 text-[15px] text-white outline-none transition placeholder:text-white/28 focus:border-[#8452FF]"
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-[14px] leading-5 text-white/56">Пароль</span>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Твой пароль от этой учетной записи"
                  autoComplete="current-password"
                  required
                  className="h-14 w-full rounded-[18px] border border-white/10 bg-[#0D0B13] px-4 pr-14 text-[15px] text-white outline-none transition placeholder:text-white/28 focus:border-[#8452FF]"
                />
                <PasswordVisibilityButton visible={showPassword} onToggle={() => setShowPassword((current) => !current)} />
              </div>
            </label>
          </div>

          <div className="flex items-center justify-between gap-4 text-[13px] leading-5">
            <span className="text-white/38">Если забыл пароль, восстановление добавим позже.</span>
            <button type="button" className="text-white/60 transition hover:text-white">
              Не помнишь пароль?
            </button>
          </div>

          <AuthPrimaryButton type="submit" disabled={loading || !formData.email || !formData.password}>
            {loading ? 'Загрузка...' : 'Войти'}
          </AuthPrimaryButton>

          <SocialAuthButtons
            mode="login"
            onYandex={() => authAPI.startYandexLogin()}
            yandexDisabled={loading}
            footerLabel="Еще не с нами?"
            footerActionLabel="Зарегистрироваться"
            onFooterAction={() => navigate('/register')}
          />
        </form>
      </AuthSurface>
    </AuthShell>
  );
}

export default Login;
