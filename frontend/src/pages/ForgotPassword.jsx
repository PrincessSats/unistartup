import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AuthShell,
  AuthSurface,
  AuthPrimaryButton,
} from '../components/AuthUI';
import { authAPI } from '../services/api';

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authAPI.requestPasswordReset(email);
      setSuccess(true);

      // Auto-redirect after 5 seconds
      setTimeout(() => {
        navigate('/login');
      }, 5000);
    } catch (err) {
      if (err.response?.status === 429) {
        setError('Too many requests. Please try again in a few minutes.');
      } else {
        setError(err.response?.data?.detail || 'Failed to send reset link. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <AuthShell title="Ссылка отправлена">
        <AuthSurface className="text-center">
          <p className="mb-6 text-[16px] leading-6 tracking-[0.04em] text-white/70">
            Проверьте ваш email <strong className="text-white">{email}</strong>. Ссылка для восстановления пароля действительна 1 час.
          </p>
          <p className="mb-6 text-[14px] leading-5 tracking-[0.04em] text-white/50">
            Вы будете перенаправлены на страницу входа через несколько секунд...
          </p>
          <AuthPrimaryButton onClick={() => navigate('/login')}>
            Вернуться на вход
          </AuthPrimaryButton>
        </AuthSurface>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Восстановление пароля">
      <AuthSurface>
        <p className="mb-6 text-[16px] leading-6 tracking-[0.04em] text-white/70">
          Введите адрес электронной почты, и мы отправим ссылку для восстановления
        </p>

        {error && (
          <div className="mb-6 rounded-[10px] border border-red-500/30 bg-red-500/10 px-4 py-3 text-[14px] leading-5 tracking-[0.04em] text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-3 block text-[14px] font-medium leading-5 tracking-[0.04em] text-white/70">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="h-14 w-full rounded-[10px] border border-white/[0.14] bg-white/[0.03] px-4 text-[16px] tracking-[0.04em] text-white placeholder-white/40 focus:outline-none focus:ring-1 focus:ring-white/[0.24]"
              placeholder="you@example.com"
              disabled={loading}
            />
          </div>

          <AuthPrimaryButton type="submit" disabled={loading}>
            {loading ? 'Отправка...' : 'Отправить ссылку'}
          </AuthPrimaryButton>
        </form>

        <div className="mt-6 text-center">
          <p className="text-[14px] tracking-[0.04em] text-white/60">
            Вспомнили пароль?{' '}
            <button
              onClick={() => navigate('/login')}
              className="text-white transition hover:text-[#AB85FF]"
            >
              Вернуться на вход
            </button>
          </p>
        </div>
      </AuthSurface>
    </AuthShell>
  );
}
