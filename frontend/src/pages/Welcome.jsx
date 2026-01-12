import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI, userAPI } from '../services/api';

function Welcome() {
  const navigate = useNavigate();
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    // Проверяем авторизацию
    if (!authAPI.isAuthenticated()) {
      navigate('/login');
      return;
    }

    // Загружаем данные пользователя
    const fetchUserData = async () => {
      try {
        const data = await userAPI.getWelcome();
        setUserData(data);
      } catch (err) {
        setError('Ошибка загрузки данных');
        // Если токен невалидный - на страницу входа
        if (err.response?.status === 401) {
          authAPI.logout();
          navigate('/login');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchUserData();
  }, [navigate]);

  const handleLogout = () => {
    authAPI.logout();
    navigate('/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B0A10] flex items-center justify-center">
        <div className="text-white text-xl">Загрузка...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#0B0A10] flex items-center justify-center">
        <div className="text-red-500 text-xl">{error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0B0A10] text-white">
      {/* Header с кнопкой выхода */}
      <header className="bg-zinc-900 border-b border-zinc-800">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          {/* Логотип */}
          <div className="flex items-center gap-3">
            <div className="flex justify-center mb-8">
          <img src="/logo.png" alt="HackNet" className="w-12 h-12" />
        </div>
            <span className="text-xl font-semibold">HackNet</span>
          </div>

          {/* Информация о пользователе и кнопка выхода */}
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="font-medium">{userData?.user?.username}</div>
              <div className="text-sm text-gray-400">{userData?.user?.role}</div>
            </div>
            <button
              onClick={handleLogout}
              className="bg-red-500/10 hover:bg-red-500/20 text-red-500 px-4 py-2 rounded-lg transition-colors border border-red-500/30"
            >
              Выйти
            </button>
          </div>
        </div>
      </header>

      {/* Основной контент */}
      <main className="max-w-7xl mx-auto px-4 py-12">
        <div className="bg-zinc-900 rounded-2xl p-8 text-center">
          {/* Иконка успеха */}
          <div className="flex justify-center mb-6">
            <div className="w-20 h-20 bg-green-500/10 rounded-full flex items-center justify-center border-2 border-green-500">
              <svg className="w-10 h-10 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          </div>

          {/* Сообщение */}
          <h1 className="text-3xl font-bold mb-4">
            {userData?.message || 'Молодец, БД работает, добро пожаловать!'}
          </h1>

          {/* Информация о пользователе */}
          <div className="mt-8 bg-zinc-800 rounded-xl p-6 max-w-md mx-auto">
            <h2 className="text-xl font-semibold mb-4">Информация о пользователе</h2>
            <div className="space-y-2 text-left">
              <div className="flex justify-between">
                <span className="text-gray-400">Username:</span>
                <span className="font-medium">{userData?.user?.username}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Email:</span>
                <span className="font-medium">{userData?.user?.email}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Роль:</span>
                <span className="font-medium capitalize">{userData?.user?.role}</span>
              </div>
            </div>
          </div>

          {/* Дополнительные кнопки */}
          <div className="mt-8 flex gap-4 justify-center">
            {userData?.user?.role === 'admin' && (
              <button
                onClick={() => navigate('/admin')}
                className="bg-purple-500 hover:bg-purple-600 text-white px-6 py-3 rounded-lg transition-colors"
              >
                Админ панель
              </button>
            )}
            <button
              className="bg-zinc-800 hover:bg-zinc-700 text-white px-6 py-3 rounded-lg transition-colors"
            >
              Перейти к задачам
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default Welcome;