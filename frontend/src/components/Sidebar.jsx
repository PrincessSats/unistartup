import React from 'react';
import { NavLink } from 'react-router-dom';
import AppIcon from './AppIcon';

const icons = {
  home: <AppIcon name="home" className="w-5 h-5" />,
  championship: <AppIcon name="championship" className="w-5 h-5" />,
  education: <AppIcon name="education" className="w-5 h-5" />,
  rating: <AppIcon name="rating" className="w-5 h-5" />,
  knowledge: <AppIcon name="knowledge" className="w-5 h-5" />,
  faq: <AppIcon name="faq" className="w-5 h-5" />,
  admin: <AppIcon name="admin" className="w-5 h-5" />,
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
