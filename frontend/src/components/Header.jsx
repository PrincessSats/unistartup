// frontend/src/components/Header.jsx

import React from 'react';
import { useNavigate } from 'react-router-dom';

function Header({ username, avatarUrl }) {  // ← добавили avatarUrl
  const navigate = useNavigate();

  return (
    <header className="h-16 bg-[#0B0A10] border-b border-zinc-800 flex items-center justify-between px-6">
      {/* Поле поиска */}
      <div className="flex-1 max-w-2xl">
        <div className="relative">
          <svg
            className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
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
            className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-3 pl-12 pr-4 text-white placeholder-gray-500 focus:outline-none focus:border-zinc-700 transition-colors"
          />
        </div>
      </div>

      {/* Правая часть */}
      <div className="flex items-center gap-4 ml-6">
        {/* Иконка чата */}
        <button className="p-2 text-gray-400 hover:text-white transition-colors">
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        </button>

        {/* Профиль */}
        <button
          onClick={() => navigate('/profile')}
          className="flex items-center gap-3 hover:bg-zinc-800 rounded-lg px-3 py-2 transition-colors"
        >
          <span className="text-white font-medium">{username}</span>
          
          {/* Аватар — картинка или заглушка */}
          <div className="w-10 h-10 bg-zinc-800 rounded-full flex items-center justify-center border border-zinc-700 overflow-hidden">
            {avatarUrl ? (
              <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
            ) : (
              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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