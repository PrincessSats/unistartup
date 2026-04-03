import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authAPI } from '../services/api';
import { AuthShell, AuthSurface, AuthPrimaryButton } from '../components/AuthUI';

export default function ResetPassword() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [tokenValid, setTokenValid] = useState(null);

  useEffect(() => {
    if (!token) {
      setError('Reset token is missing. Please use the link from your email.');
      setTokenValid(false);
      return;
    }
    setTokenValid(true);
  }, [token]);

  const validatePasswords = () => {
    if (newPassword.length < 6) {
      setError('Пароль должен быть не менее 6 символов');
      return false;
    }
    if (newPassword !== confirmPassword) {
      setError('Пароли не совпадают');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!validatePasswords()) {
      return;
    }

    setLoading(true);

    try {
      await authAPI.confirmPasswordReset(token, newPassword);
      setSuccess(true);
      setNewPassword('');
      setConfirmPassword('');

      // Auto-redirect after 3 seconds
      setTimeout(() => {
        navigate('/login');
      }, 3000);
    } catch (err) {
      if (err.response?.status === 400) {
        setError('Ссылка истекла или недействительна. Запросите новую ссылку для восстановления.');
      } else if (err.response?.status === 429) {
        setError('Слишком много попыток. Попробуйте позже.');
      } else {
        setError(err.response?.data?.detail || 'Ошибка при сбросе пароля. Попробуйте снова.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (tokenValid === false) {
    return (
      <AuthShell title="Ошибка" subtitle="">
        <AuthSurface>
          <div className="text-center">
            <p className="text-gray-300 mb-6">{error}</p>
            <AuthPrimaryButton
              onClick={() => navigate('/forgot-password')}
              className="w-full"
            >
              Запросить новую ссылку
            </AuthPrimaryButton>
          </div>
        </AuthSurface>
      </AuthShell>
    );
  }

  if (success) {
    return (
      <AuthShell title="Пароль изменён" subtitle="">
        <AuthSurface>
          <div className="text-center">
            <p className="text-gray-300 mb-6">Пароль успешно сброшен. Вы можете войти с новым паролем.</p>
            <p className="text-gray-400 text-sm mb-6">Перенаправление на страницу входа...</p>
            <AuthPrimaryButton
              onClick={() => navigate('/login')}
              className="w-full"
            >
              Перейти на вход
            </AuthPrimaryButton>
          </div>
        </AuthSurface>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Новый пароль" subtitle="Введите новый пароль для вашего аккаунта">
      <AuthSurface>
        {error && (
          <div className="bg-red-900/20 border border-red-700/30 text-red-400 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-gray-300 font-medium text-sm mb-2">Новый пароль</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className="w-full px-4 py-2.5 bg-white/[0.05] border border-white/[0.1] rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-white/[0.2] focus:ring-1 focus:ring-white/[0.1]"
              placeholder="Минимум 6 символов"
              disabled={loading}
            />
            <p className="text-gray-400 text-xs mt-1">Минимум 6 символов</p>
          </div>

          <div className="mb-6">
            <label className="block text-gray-300 font-medium text-sm mb-2">Подтверждение пароля</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="w-full px-4 py-2.5 bg-white/[0.05] border border-white/[0.1] rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-white/[0.2] focus:ring-1 focus:ring-white/[0.1]"
              placeholder="Введите пароль ещё раз"
              disabled={loading}
            />
          </div>

          <AuthPrimaryButton
            type="submit"
            disabled={loading}
            className="w-full"
          >
            {loading ? 'Изменение пароля...' : 'Изменить пароль'}
          </AuthPrimaryButton>
        </form>

        <div className="mt-6 text-center">
          <p className="text-gray-400 text-sm">
            <button
              onClick={() => navigate('/forgot-password')}
              className="text-blue-400 hover:text-blue-300 font-semibold transition"
            >
              Запросить новую ссылку
            </button>
          </p>
        </div>
      </AuthSurface>
    </AuthShell>
  );
}
