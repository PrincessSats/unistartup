import React from 'react';
import { NavLink } from 'react-router-dom';

const iconAssets = {
  home: 'https://www.figma.com/api/mcp/asset/5b999686-618b-4b69-a7b0-3bcc1ca8b52c',
  championship: 'https://www.figma.com/api/mcp/asset/c97b5811-3f58-43a6-8440-4066e7758353',
  education: 'https://www.figma.com/api/mcp/asset/1266fbcc-e7b5-423b-ab51-826960891d83',
  rating: 'https://www.figma.com/api/mcp/asset/63d69515-1640-4d7a-a1a7-a1667a8394d7',
  knowledge: 'https://www.figma.com/api/mcp/asset/672fc1c8-5d30-4e84-a6e6-8c1dfdf6d4fb',
  faq: 'https://www.figma.com/api/mcp/asset/714934b3-a071-4ea1-83c2-483949b73670',
  admin: 'https://www.figma.com/api/mcp/asset/7ef5f3be-8d99-4176-8e66-49568e7f8777',
};

const icons = {
  home: <img src={iconAssets.home} alt="" className="w-5 h-5" />,
  championship: <img src={iconAssets.championship} alt="" className="w-5 h-5" />,
  education: <img src={iconAssets.education} alt="" className="w-5 h-5" />,
  rating: <img src={iconAssets.rating} alt="" className="w-5 h-5" />,
  knowledge: <img src={iconAssets.knowledge} alt="" className="w-5 h-5" />,
  faq: <img src={iconAssets.faq} alt="" className="w-5 h-5" />,
  admin: <img src={iconAssets.admin} alt="" className="w-5 h-5" />,
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
