import React from 'react';
import { NavLink } from 'react-router-dom';
import AppIcon from './AppIcon';
import HacknetLogo from './HacknetLogo';

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

function Sidebar({ isAdmin, mobile = false, onNavigate }) {
  const handleNavigate = () => {
    if (mobile && typeof onNavigate === 'function') {
      onNavigate();
    }
  };

  return (
    <aside
      className={`w-[264px] bg-[#0B0A10] flex flex-col font-sans-figma ${
        mobile ? 'h-full border-r border-white/[0.09] overflow-y-auto' : 'min-h-screen'
      }`}
    >
      <div className="flex flex-col gap-12 px-6 py-6 sm:gap-20 sm:px-8 sm:py-8">
        {mobile && (
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleNavigate}
              className="inline-flex h-10 w-10 items-center justify-center rounded-[10px] border border-white/[0.09] bg-white/[0.03] text-white/70"
              aria-label="Закрыть меню"
            >
              <AppIcon name="close" className="h-5 w-5" />
            </button>
          </div>
        )}

        {/* Логотип */}
        <div className="flex items-center gap-4">
          <HacknetLogo className="w-12 h-12" />
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
                  onClick={handleNavigate}
                  className={({ isActive }) =>
                    `flex items-center gap-3 h-11 px-4 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                      isActive
                        ? 'bg-[#9B6BFF]/[0.15] text-[#9B6BFF]'
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
                  onClick={handleNavigate}
                  className={({ isActive }) =>
                    `flex items-center gap-3 h-11 px-4 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                      isActive
                        ? 'bg-[#9B6BFF]/[0.15] text-[#9B6BFF]'
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
