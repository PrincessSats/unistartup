// frontend/src/components/Header.jsx

import React from 'react';
import { useNavigate } from 'react-router-dom';
import AppIcon from './AppIcon';

function Header({ username, avatarUrl, onSupportClick }) {  // ← добавили avatarUrl
  const navigate = useNavigate();

  return (
    <header className="h-[120px] bg-[#0D0D0D]/10 border-b border-white/[0.09] backdrop-blur-[128px] flex items-center justify-between px-8 font-sans-figma">
      {/* Поле поиска */}
      <div className="flex-1 max-w-[1062px]">
        <div className="flex items-center gap-4 h-14 px-5 rounded-[10px] bg-white/[0.03] border border-white/[0.09]">
          <AppIcon name="search" className="w-[22px] h-[22px] text-white/70" />
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
        <button
          type="button"
          onClick={onSupportClick}
          aria-label="Оставить отзыв"
          className="w-14 h-14 rounded-[10px] bg-white/[0.05] text-white/80 hover:text-white transition-colors flex items-center justify-center"
        >
          <AppIcon name="support" className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-4 border-l border-white/[0.09] pl-4">
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
                <AppIcon name="person" className="w-5 h-5 text-white" />
              )}
            </div>
          </button>
        </div>
      </div>
    </header>
  );
}

export default Header;
