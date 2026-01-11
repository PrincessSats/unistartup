import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../services/api';

function Login() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authAPI.login(formData.email, formData.password);
      navigate('/welcome');
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка входа');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Логотип */}
        <div className="flex justify-center mb-8">
          <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center">
            <span className="text-black text-2xl font-bold">+</span>
          </div>
        </div>

        {/* Заголовок */}
        <h1 className="text-white text-3xl font-semibold text-center mb-8">
          Вход
        </h1>

        {/* Форма */}
        <form onSubmit={handleSubmit} className="bg-zinc-900 rounded-2xl p-8 space-y-6">
          {/* Ошибка */}
          {error && (
            <div className="bg-red-500/10 border border-red-500 text-red-500 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Email */}
          <div>
            <label className="text-gray-400 text-sm mb-2 block">
              Электронная почта
            </label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="example@gmail.com"
              required
              className="w-full bg-zinc-800 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 placeholder-gray-500"
            />
          </div>

          {/* Password */}
          <div>
            <label className="text-gray-400 text-sm mb-2 block">
              Пароль
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="Введите пароль"
              required
              className="w-full bg-zinc-800 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 placeholder-gray-500"
            />
          </div>

          {/* Забыли пароль */}
          <div className="text-right">
            <button
              type="button"
              className="text-gray-400 hover:text-white text-sm transition-colors"
            >
              Забыли пароль?
            </button>
          </div>

          {/* Кнопка */}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-zinc-800 hover:bg-zinc-700 text-gray-400 hover:text-white py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Загрузка...' : 'Войти'}
          </button>

          {/* Разделитель */}
          <div className="flex items-center gap-4 my-6">
            <div className="flex-1 h-px bg-zinc-700"></div>
            <span className="text-gray-500 text-sm">Или войти через</span>
            <div className="flex-1 h-px bg-zinc-700"></div>
          </div>

          {/* OAuth кнопки */}
          <div className="space-y-3">
            <button
              type="button"
              className="w-full bg-zinc-800 hover:bg-zinc-700 text-white py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <span>🐙</span> Github
            </button>
            <div className="grid grid-cols-2 gap-3">
              <button type="button" className="bg-zinc-800 hover:bg-zinc-700 text-white py-3 rounded-lg transition-colors">
                 Apple
              </button>
              <button type="button" className="bg-zinc-800 hover:bg-zinc-700 text-white py-3 rounded-lg transition-colors">
                🔍 Google
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button type="button" className="bg-zinc-800 hover:bg-zinc-700 text-white py-3 rounded-lg transition-colors">
                🔴 Яндекс
              </button>
              <button type="button" className="bg-zinc-800 hover:bg-zinc-700 text-white py-3 rounded-lg transition-colors">
                ✈️ Telegram
              </button>
            </div>
          </div>

          {/* Ссылка на регистрацию */}
          <div className="text-center pt-4">
            <span className="text-gray-500">Еще нет аккаунта? </span>
            <button
              type="button"
              onClick={() => navigate('/register')}
              className="text-white hover:text-purple-400 transition-colors"
            >
              Зарегистрироваться
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default Login;