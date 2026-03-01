// frontend/src/components/Layout.jsx

import React, { useMemo, useState, useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import FeedbackModal from './FeedbackModal';
import { FullScreenLoader } from './LoadingState';
import { authAPI, profileAPI } from '../services/api';

// Кэш профиля нужен, чтобы отрисовывать интерфейс сразу при повторных переходах.
const PROFILE_CACHE_KEY = 'layout:profile:v1';
const PROFILE_CACHE_TTL_MS = 2 * 60 * 1000;

function readProfileCache() {
  try {
    const raw = sessionStorage.getItem(PROFILE_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;

    // Обратная совместимость со старым форматом: в кеше лежал сам профиль без метаданных.
    if (parsed && !parsed.profile) {
      return parsed;
    }

    const profile = parsed.profile && typeof parsed.profile === 'object' ? parsed.profile : null;
    const savedAt = Number(parsed.savedAt) || 0;
    if (!profile || !savedAt) return null;
    if (Date.now() - savedAt > PROFILE_CACHE_TTL_MS) {
      return null;
    }
    return profile;
  } catch {
    return null;
  }
}

function writeProfileCache(profile) {
  try {
    if (!profile) {
      sessionStorage.removeItem(PROFILE_CACHE_KEY);
      return;
    }
    sessionStorage.setItem(PROFILE_CACHE_KEY, JSON.stringify({ profile, savedAt: Date.now() }));
  } catch {
    // Ошибки кэша не должны ломать основной поток страницы.
  }
}

function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const initialCachedProfile = useMemo(() => readProfileCache(), []);
  // Берем профиль из кэша, чтобы не показывать "Загрузка..." на каждом переходе.
  const [userData, setUserData] = useState(initialCachedProfile);
  const [loading, setLoading] = useState(() => !initialCachedProfile);
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  useEffect(() => {
    if (!authAPI.isAuthenticated()) {
      navigate('/login?reason=session_expired', { replace: true });
      return;
    }

    // Если профиль в session cache еще свежий, не дергаем API сразу после загрузки.
    if (initialCachedProfile) {
      setLoading(false);
      return;
    }

    const fetchUserData = async () => {
      try {
        const data = await profileAPI.getProfile();
        setUserData(data);
        writeProfileCache(data);
      } catch (err) {
        const status = Number(err?.response?.status || 0);
        const code = String(err?.code || '').toUpperCase();
        const isTimeout = code === 'ECONNABORTED' || String(err?.message || '').toLowerCase().includes('timeout');
        if (status === 401 || isTimeout) {
          // При невалидной/зависшей сессии очищаем кэш и быстро уходим в логин.
          writeProfileCache(null);
          const reason = status === 401 ? 'session_expired' : 'network_timeout';
          authAPI.logout({ remote: false, redirect: false });
          navigate(`/login?reason=${encodeURIComponent(reason)}`, { replace: true });
        }
      } finally {
        setLoading(false);
      }
    };

    fetchUserData();
  }, [initialCachedProfile, navigate]);

  useEffect(() => {
    const handleProfileUpdated = (event) => {
      // Используем функциональный setState, чтобы не пересоздавать подписку при каждом обновлении профиля.
      setUserData((prev) => {
        const next = {
          ...(prev || {}),
          ...(event?.detail || {}),
        };
        writeProfileCache(next);
        return next;
      });
    };

    window.addEventListener('profile-updated', handleProfileUpdated);
    return () => window.removeEventListener('profile-updated', handleProfileUpdated);
  }, []);

  useEffect(() => {
    setIsSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!isSidebarOpen) return undefined;

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsSidebarOpen(false);
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isSidebarOpen]);

  // Полный блокирующий экран показываем только при самом первом заходе без кэша.
  if (loading && !userData) {
    return <FullScreenLoader label="Загружаем профиль..." />;
  }

  // Структура ответа profileAPI: { id, email, username, role, bio, avatar_url }
  const isAdmin = userData?.role === 'admin';
  const username = userData?.username || 'Пользователь';
  const avatarUrl = userData?.avatar_url;

  return (
    <div className="min-h-screen bg-[#0B0A10] overflow-x-hidden">
      <FeedbackModal open={isFeedbackOpen} onClose={() => setIsFeedbackOpen(false)} />

      <div className="flex min-h-screen">
        <div className="hidden xl:block">
          <Sidebar isAdmin={isAdmin} />
        </div>

        <div className="flex min-w-0 flex-1 flex-col border border-white/[0.09]">
          <Header
            username={username}
            avatarUrl={avatarUrl}
            onSupportClick={() => setIsFeedbackOpen(true)}
            onMenuToggle={() => setIsSidebarOpen((prev) => !prev)}
          />

          <main className="flex-1 min-w-0 px-4 pb-6 pt-4 sm:px-6 lg:px-8 lg:pb-8">
            {/* Передаем текущего пользователя вниз через Outlet, чтобы страницы не дублировали запрос профиля. */}
            <Outlet context={{ currentUser: userData }} />
          </main>
        </div>
      </div>

      <div
        className={`fixed inset-0 z-40 xl:hidden ${isSidebarOpen ? '' : 'pointer-events-none'}`}
        aria-hidden={!isSidebarOpen}
      >
        <button
          type="button"
          className={`absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity ${
            isSidebarOpen ? 'opacity-100' : 'opacity-0'
          }`}
          aria-label="Закрыть меню"
          onClick={() => setIsSidebarOpen(false)}
        />
        <div
          className={`absolute inset-y-0 left-0 w-[264px] max-w-[85vw] transform transition-transform duration-300 ${
            isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <Sidebar isAdmin={isAdmin} mobile onNavigate={() => setIsSidebarOpen(false)} />
        </div>
      </div>
    </div>
  );
}

export default Layout;
