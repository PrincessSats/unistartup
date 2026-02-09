// frontend/src/components/Header.jsx

import React from 'react';
import { useNavigate } from 'react-router-dom';

const iconAssets = {
  search: 'https://www.figma.com/api/mcp/asset/56ed3c84-7b2a-4426-8f44-951d15f32b74',
  support: 'https://www.figma.com/api/mcp/asset/d553112c-67be-4fd0-9438-ca13931560f1',
  person: 'https://www.figma.com/api/mcp/asset/b860bcd5-d904-455c-a685-a2c21ad9e02a',
};

function Header({ username, avatarUrl }) {  // ← добавили avatarUrl
  const navigate = useNavigate();

  return (
    <header className="h-[120px] bg-[#0D0D0D]/10 border-b border-white/[0.09] backdrop-blur-[128px] flex items-center justify-between px-8 font-sans-figma">
      {/* Поле поиска */}
      <div className="flex-1 max-w-[1062px]">
        <div className="flex items-center gap-4 h-14 px-5 rounded-[10px] bg-white/[0.03] border border-white/[0.09]">
          <img src={iconAssets.search} alt="" className="w-[22px] h-[22px]" />
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
          <img src={iconAssets.support} alt="" className="w-5 h-5" />
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
                <img src={iconAssets.person} alt="" className="w-5 h-5" />
              )}
            </div>
          </button>
        </div>
      </div>
    </header>
  );
}

export default Header;
