// frontend/src/components/Layout.jsx

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { authAPI, profileAPI } from '../services/api';  // ← заменили userAPI на profileAPI

function Layout({ children }) {
  const navigate = useNavigate();
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true);

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
    <div className="min-h-screen bg-[#0B0A10] flex">
      <Sidebar isAdmin={isAdmin} />

      <div className="flex-1 flex flex-col border border-white/[0.09]">
        <Header username={username} avatarUrl={avatarUrl} />  {/* ← передаём avatarUrl */}

        <main className="flex-1 px-8 pt-4 pb-8">
          {children}
        </main>
      </div>
    </div>
  );
}

export default Layout;
