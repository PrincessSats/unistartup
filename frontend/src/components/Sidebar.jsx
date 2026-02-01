import React from 'react';
import { NavLink } from 'react-router-dom';

// Иконки для меню (используем простые SVG)
const icons = {
  home: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10.5l9-7.5 9 7.5" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 9.5V20h14V9.5" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20v-6h6v6" />
    </svg>
  ),
  championship: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 4h12v3a6 6 0 01-12 0V4z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4H2v2a4 4 0 004 4" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 4h2v2a4 4 0 01-4 4" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 14h4v4h-4z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 22h8" />
    </svg>
  ),
  education: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v16" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5h11l-1.5 3L15 11H4" />
    </svg>
  ),
  rating: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 3l1.5 2M16 3l-1.5 2" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 7h10a4 4 0 014 4v2a6 6 0 01-6 6H9a6 6 0 01-6-6v-2a4 4 0 014-4z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 11h8M10 15h4" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2 11h3M19 11h3" />
    </svg>
  ),
  knowledge: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14 2H7a2 2 0 00-2 2v16a2 2 0 002 2h10a2 2 0 002-2V8z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14 2v6h6" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 13h6M9 17h6" />
    </svg>
  ),
  faq: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.09 9a3 3 0 115.82 1c0 2-3 2-3 4" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 17h.01" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  admin: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
};

// Пункты меню
const menuItems = [
  { path: '/home', label: 'Главная', icon: icons.home },
  { path: '/championship', label: 'Чемпионат', icon: icons.championship },
  { path: '/education', label: 'Обучение', icon: icons.education },
  { path: '/rating', label: 'Рейтинг', icon: icons.rating },
  { path: '/knowledge', label: 'База знаний', icon: icons.knowledge },
  { path: '/faq', label: 'FAQ', icon: icons.faq },
];

function Sidebar({ isAdmin }) {
  return (
    <aside className="w-[264px] bg-[#0B0A10] min-h-screen flex flex-col font-sans-figma">
      <div className="flex flex-col gap-20 px-8 py-8">
        {/* Логотип */}
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-[12px] bg-white flex items-center justify-center">
            <img src="/logo.png" alt="HackNet" className="w-8 h-8" />
          </div>
          <span className="text-white text-[20px] leading-[24px] tracking-[0.02em]">
            Hacknet
          </span>
        </div>

        {/* Навигация */}
        <nav className="flex-1">
          <ul className="flex flex-col gap-4">
            {menuItems.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 h-11 px-3 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                      isActive
                        ? 'bg-white/[0.05] text-white'
                        : 'text-white/60 hover:text-[#9B6BFF] hover:bg-[#9B6BFF]/[0.12]'
                    }`
                  }
                >
                  {item.icon}
                  <span>{item.label}</span>
                </NavLink>
              </li>
            ))}

            {/* Кнопка Админки — только для админов */}
            {isAdmin && (
              <li>
                <NavLink
                  to="/admin"
                  className={({ isActive }) =>
                    `flex items-center gap-3 h-11 px-3 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                      isActive
                        ? 'bg-white/[0.05] text-white'
                        : 'text-white/60 hover:text-[#9B6BFF] hover:bg-[#9B6BFF]/[0.12]'
                    }`
                  }
                >
                  {icons.admin}
                  <span>Админка</span>
                </NavLink>
              </li>
            )}
          </ul>
        </nav>
      </div>
    </aside>
  );
}

export default Sidebar;
