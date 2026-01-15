import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI, userAPI } from '../services/api';

function Profile() {
  const navigate = useNavigate();
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Состояния для редактирования
  const [showPassword, setShowPassword] = useState(false);
  const [showAvatarModal, setShowAvatarModal] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  
  // Временные значения для редактирования
  const [editUsername, setEditUsername] = useState('');
  const [editAvatar, setEditAvatar] = useState(null);
  const [editAvatarPreview, setEditAvatarPreview] = useState(null);
  const [editEmail, setEditEmail] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  
  // Ошибки и успех
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const data = await userAPI.getWelcome();
        setUserData(data);
        setEditUsername(data?.user?.username || '');
        setEditEmail(data?.user?.email || '');
      } catch (err) {
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

  // Обработка выбора файла аватарки
  const handleAvatarChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Проверяем размер (макс 2MB)
    if (file.size > 2 * 1024 * 1024) {
      setError('Файл слишком большой. Максимум 2MB');
      return;
    }

    // Проверяем тип
    if (!file.type.startsWith('image/')) {
      setError('Можно загружать только изображения');
      return;
    }

    setEditAvatar(file);
    
    // Создаём превью
    const reader = new FileReader();
    reader.onload = (e) => {
      setEditAvatarPreview(e.target.result);
    };
    reader.readAsDataURL(file);
    setError('');
  };

  // Сохранение аватарки и никнейма
  const handleSaveAvatar = async () => {
    try {
      setError('');
      // TODO: Отправка на сервер
      // await userAPI.updateProfile({ username: editUsername, avatar: editAvatar });
      
      // Пока просто обновляем локально
      setUserData(prev => ({
        ...prev,
        user: {
          ...prev.user,
          username: editUsername,
          avatar: editAvatarPreview
        }
      }));
      
      setSuccess('Профиль обновлён!');
      setShowAvatarModal(false);
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Ошибка сохранения');
    }
  };

  // Сохранение email
  const handleSaveEmail = async () => {
    try {
      setError('');
      // TODO: Отправка на сервер
      // await userAPI.updateEmail({ email: editEmail });
      
      setUserData(prev => ({
        ...prev,
        user: { ...prev.user, email: editEmail }
      }));
      
      setSuccess('Email обновлён!');
      setShowEmailModal(false);
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Ошибка сохранения');
    }
  };

  // Сохранение пароля
  const handleSavePassword = async () => {
    if (newPassword !== confirmPassword) {
      setError('Пароли не совпадают');
      return;
    }
    if (newPassword.length < 6) {
      setError('Пароль должен быть минимум 6 символов');
      return;
    }
    
    try {
      setError('');
      // TODO: Отправка на сервер
      // await userAPI.changePassword({ currentPassword, newPassword });
      
      setSuccess('Пароль изменён!');
      setShowPasswordModal(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Ошибка смены пароля');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-white text-xl">Загрузка...</div>
      </div>
    );
  }

  const user = userData?.user;
  const avatarUrl = user?.avatar || editAvatarPreview;

  return (
    <div>
      {/* Уведомление об успехе */}
      {success && (
        <div className="fixed top-4 right-4 bg-green-500/20 border border-green-500 text-green-400 px-4 py-3 rounded-lg z-50">
          {success}
        </div>
      )}

      {/* Заголовок страницы */}
      <h1 className="text-white text-3xl font-bold mb-8">Личный кабинет</h1>

      <div className="flex gap-6">
        {/* Левая колонка — Аватар и рейтинг */}
        <div className="w-80">
          <div className="bg-zinc-900 rounded-2xl p-6">
            {/* Аватар с кнопкой редактирования */}
            <div className="relative flex justify-center mb-4">
              {/* Контейнер аватара */}
              <div className="relative">
                <div className="w-40 h-40 bg-zinc-800 rounded-xl flex items-center justify-center overflow-hidden">
                  {avatarUrl ? (
                    <img 
                      src={avatarUrl} 
                      alt="Avatar" 
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <svg className="w-16 h-16 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  )}
                </div>
                
                {/* Кнопка редактирования — СНАРУЖИ аватарки */}
                <button 
                  onClick={() => setShowAvatarModal(true)}
                  className="absolute -top-2 -right-2 p-2 bg-zinc-700 rounded-lg hover:bg-zinc-600 transition-colors border border-zinc-600"
                >
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Имя пользователя */}
            <h2 className="text-white text-xl font-semibold text-center mb-6">
              {user?.username || 'Username'}
            </h2>

            {/* Рейтинг */}
            <div className="space-y-3">
              <h3 className="text-gray-400 text-sm">Рейтинг</h3>
              
              <div className="flex justify-between items-center bg-zinc-800 rounded-xl px-4 py-3">
                <span className="text-gray-300">Чемпионат</span>
                <span className="text-white font-semibold text-lg">522</span>
              </div>
              
              <div className="flex justify-between items-center bg-zinc-800 rounded-xl px-4 py-3">
                <span className="text-gray-300">Обучение</span>
                <span className="text-white font-semibold text-lg">21465</span>
              </div>
            </div>
          </div>
        </div>

        {/* Правая колонка — Настройки */}
        <div className="flex-1">
          <div className="bg-zinc-900 rounded-2xl p-6">
            {/* Управление данными */}
            <h3 className="text-white text-lg font-semibold mb-4">Управление данными</h3>
            
            <div className="grid grid-cols-2 gap-4 mb-8">
              {/* Email */}
              <div>
                <label className="text-gray-400 text-sm mb-2 block">Электронная почта</label>
                <div className="relative">
                  <input
                    type="email"
                    value={user?.email || ''}
                    readOnly
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-xl py-3 px-4 pr-10 text-white"
                  />
                  <button 
                    onClick={() => {
                      setEditEmail(user?.email || '');
                      setShowEmailModal(true);
                    }}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Пароль */}
              <div>
                <label className="text-gray-400 text-sm mb-2 block">Пароль</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value="password123"
                    readOnly
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-xl py-3 px-4 pr-20 text-white"
                  />
                  {/* Кнопка показать/скрыть пароль */}
                  <button 
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-10 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                  >
                    {showPassword ? (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                      </svg>
                    )}
                  </button>
                  {/* Кнопка редактирования пароля */}
                  <button 
                    onClick={() => setShowPasswordModal(true)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            {/* Способы входа */}
            <h3 className="text-white text-lg font-semibold mb-4">Способы входа</h3>
            
            <div className="space-y-3">
              {/* GitHub */}
              <div className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                  </svg>
                  <span className="text-white">Github</span>
                </div>
                <button className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-gray-300 rounded-lg transition-colors border border-zinc-700">
                  Добавить
                </button>
              </div>

              {/* Apple */}
              <div className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <svg className="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
                  </svg>
                  <span className="text-white">Apple</span>
                </div>
                <button className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-gray-300 rounded-lg transition-colors border border-zinc-700">
                  Добавить
                </button>
              </div>

              {/* Google */}
              <div className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <svg className="w-6 h-6" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  <span className="text-white">Google</span>
                </div>
                <button className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-gray-300 rounded-lg transition-colors border border-zinc-700">
                  Добавить
                </button>
              </div>

              {/* Яндекс */}
              <div className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div className="w-6 h-6 bg-red-500 rounded flex items-center justify-center">
                    <span className="text-white text-sm font-bold">Я</span>
                  </div>
                  <span className="text-white">Яндекс</span>
                </div>
                <button className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-gray-300 rounded-lg transition-colors border border-zinc-700">
                  Добавить
                </button>
              </div>

              {/* Телеграм */}
              <div className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <svg className="w-6 h-6 text-[#26A5E4]" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                  </svg>
                  <span className="text-white">Телеграм</span>
                </div>
                <button className="p-2 text-gray-400 hover:text-red-400 transition-colors">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Кнопки выхода и удаления */}
            <div className="flex gap-4 mt-8 pt-6 border-t border-zinc-800">
              <button
                onClick={handleLogout}
                className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-xl transition-colors"
              >
                Выйти
              </button>
              <button className="px-6 py-3 text-red-500 hover:text-red-400 transition-colors">
                Удалить аккаунт
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ===== МОДАЛЬНЫЕ ОКНА ===== */}

      {/* Модалка редактирования аватара и никнейма */}
      {showAvatarModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-zinc-900 rounded-2xl p-6 w-full max-w-md mx-4">
            <h3 className="text-white text-xl font-semibold mb-6">Редактировать профиль</h3>
            
            {error && (
              <div className="bg-red-500/10 border border-red-500 text-red-400 px-4 py-2 rounded-lg mb-4 text-sm">
                {error}
              </div>
            )}

            {/* Превью аватара */}
            <div className="flex justify-center mb-6">
              <div className="relative">
                <div className="w-32 h-32 bg-zinc-800 rounded-xl overflow-hidden flex items-center justify-center">
                  {editAvatarPreview ? (
                    <img src={editAvatarPreview} alt="Preview" className="w-full h-full object-cover" />
                  ) : avatarUrl ? (
                    <img src={avatarUrl} alt="Current" className="w-full h-full object-cover" />
                  ) : (
                    <svg className="w-12 h-12 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  )}
                </div>
                
                {/* Кнопка загрузки */}
                <label className="absolute -bottom-2 -right-2 p-2 bg-purple-500 rounded-lg hover:bg-purple-600 transition-colors cursor-pointer">
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  <input 
                    type="file" 
                    accept="image/*" 
                    onChange={handleAvatarChange}
                    className="hidden" 
                  />
                </label>
              </div>
            </div>
            
            <p className="text-gray-400 text-sm text-center mb-6">Максимум 2MB, JPG или PNG</p>

            {/* Никнейм */}
            <div className="mb-6">
              <label className="text-gray-400 text-sm mb-2 block">Никнейм</label>
              <input
                type="text"
                value={editUsername}
                onChange={(e) => setEditUsername(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-purple-500"
              />
            </div>

            {/* Кнопки */}
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowAvatarModal(false);
                  setEditAvatarPreview(null);
                  setEditAvatar(null);
                  setError('');
                }}
                className="flex-1 px-4 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-xl transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleSaveAvatar}
                className="flex-1 px-4 py-3 bg-purple-500 hover:bg-purple-600 text-white rounded-xl transition-colors"
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка редактирования email */}
      {showEmailModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-zinc-900 rounded-2xl p-6 w-full max-w-md mx-4">
            <h3 className="text-white text-xl font-semibold mb-6">Изменить email</h3>
            
            {error && (
              <div className="bg-red-500/10 border border-red-500 text-red-400 px-4 py-2 rounded-lg mb-4 text-sm">
                {error}
              </div>
            )}

            <div className="mb-6">
              <label className="text-gray-400 text-sm mb-2 block">Новый email</label>
              <input
                type="email"
                value={editEmail}
                onChange={(e) => setEditEmail(e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowEmailModal(false);
                  setError('');
                }}
                className="flex-1 px-4 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-xl transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleSaveEmail}
                className="flex-1 px-4 py-3 bg-purple-500 hover:bg-purple-600 text-white rounded-xl transition-colors"
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модалка смены пароля */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-zinc-900 rounded-2xl p-6 w-full max-w-md mx-4">
            <h3 className="text-white text-xl font-semibold mb-6">Сменить пароль</h3>
            
            {error && (
              <div className="bg-red-500/10 border border-red-500 text-red-400 px-4 py-2 rounded-lg mb-4 text-sm">
                {error}
              </div>
            )}

            <div className="space-y-4 mb-6">
              <div>
                <label className="text-gray-400 text-sm mb-2 block">Текущий пароль</label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-purple-500"
                />
              </div>
              
              <div>
                <label className="text-gray-400 text-sm mb-2 block">Новый пароль</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-purple-500"
                />
              </div>
              
              <div>
                <label className="text-gray-400 text-sm mb-2 block">Подтвердите пароль</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-purple-500"
                />
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowPasswordModal(false);
                  setCurrentPassword('');
                  setNewPassword('');
                  setConfirmPassword('');
                  setError('');
                }}
                className="flex-1 px-4 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-xl transition-colors"
              >
                Отмена
              </button>
              <button
                onClick={handleSavePassword}
                className="flex-1 px-4 py-3 bg-purple-500 hover:bg-purple-600 text-white rounded-xl transition-colors"
              >
                Сменить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Profile;