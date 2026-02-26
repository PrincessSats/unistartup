// frontend/src/components/Layout.jsx

import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import FeedbackModal from './FeedbackModal';
import { authAPI, profileAPI } from '../services/api';  // ← заменили userAPI на profileAPI

function Layout({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  useEffect(() => {
    if (!authAPI.isAuthenticated()) {
      navigate('/login');
      return;
    }

    const fetchUserData = async () => {
      try {
        // Используем profileAPI — он возвращает avatar_url
        const data = await profileAPI.getProfile();
        setUserData(data);
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

  useEffect(() => {
    const handleProfileUpdated = (event) => {
      setUserData((prev) => ({
        ...(prev || {}),
        ...(event?.detail || {}),
      }));
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

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B0A10] flex items-center justify-center">
        <div className="text-white text-xl">Загрузка...</div>
      </div>
    );
  }

  // Структура ответа profileAPI: { id, email, username, role, bio, avatar_url }
  const isAdmin = userData?.role === 'admin';
  const username = userData?.username || 'Пользователь';
  const avatarUrl = userData?.avatar_url;  // ← новое

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
            {children}
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
