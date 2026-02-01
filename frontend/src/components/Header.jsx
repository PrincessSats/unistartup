// frontend/src/components/Header.jsx

import React from 'react';
import { useNavigate } from 'react-router-dom';

function Header({ username, avatarUrl }) {  // ← добавили avatarUrl
  const navigate = useNavigate();

  return (
    <header className="h-[120px] bg-[#0D0D0D]/10 border-b border-white/[0.09] backdrop-blur-[128px] flex items-center justify-between px-8 font-sans-figma">
      {/* Поле поиска */}
      <div className="flex-1 max-w-[1062px]">
        <div className="flex items-center gap-4 h-14 px-5 rounded-[10px] bg-white/[0.03] border border-white/[0.09]">
          <svg className="w-[22px] h-[22px] text-white/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            placeholder="Ищи задания, обучающие материалы или пользователей..."
            className="w-full bg-transparent text-[18px] leading-[24px] tracking-[0.04em] text-white placeholder:text-white/60 focus:outline-none"
          />
        </div>
      </div>

      {/* Правая часть */}
      <div className="flex items-center gap-6 ml-8">
        {/* Иконка поддержки */}
        <button className="w-14 h-14 rounded-[10px] bg-white/[0.05] text-white/80 hover:text-white transition-colors flex items-center justify-center">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M18 10a6 6 0 10-12 0v1a2 2 0 01-2 2h-.5a1.5 1.5 0 00-1.5 1.5v2A1.5 1.5 0 003.5 18H6a2 2 0 002-2v-1a4 4 0 118 0v1a2 2 0 002 2h2.5a1.5 1.5 0 001.5-1.5v-2A1.5 1.5 0 0020.5 13H20a2 2 0 01-2-2v-1z"
            />
          </svg>
        </button>

        {/* Профиль */}
        <button
          onClick={() => navigate('/profile')}
          className="flex items-center gap-4"
        >
          <span className="font-mono-figma text-white/60 text-[18px] leading-[24px] tracking-[0.02em]">
            {username}
          </span>
          <div className="w-[54px] h-[54px] rounded-[10px] bg-[#9B6BFF] flex items-center justify-center overflow-hidden">
            {avatarUrl ? (
              <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
            ) : (
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
            )}
          </div>
        </button>
      </div>
    </header>
  );
}

export default Header;
