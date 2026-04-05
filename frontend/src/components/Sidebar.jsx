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
  pipeline: <AppIcon name="pipeline" className="w-5 h-5" />,
  nvdSync: <AppIcon name="knowledge" className="w-5 h-5" />,
  cvePipeline: <AppIcon name="pipeline" className="w-5 h-5" />,
  onboarding: <AppIcon name="education" className="w-5 h-5" />,
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

function Sidebar({
  isAdmin,
  isAuthenticated = false,
  onboardingStatus = null,
  onOnboardingClick,
  mobile = false,
  onNavigate,
}) {
  const handleNavigate = () => {
    if (mobile && typeof onNavigate === 'function') {
      onNavigate();
    }
  };
  const showOnboardingShortcut = isAuthenticated && !isAdmin && (onboardingStatus == null || onboardingStatus === 'dismissed');
  const handleOnboardingClick = () => {
    if (typeof onOnboardingClick === 'function') {
      onOnboardingClick();
    }
    handleNavigate();
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
        <NavLink to="/home" className="flex items-center gap-4">
          <HacknetLogo className="w-12 h-12" />
          <span className="text-white text-[20px] leading-[24px] tracking-[0.02em]">
            Hacknet
          </span>
        </NavLink>

        {/* Навигация */}
        <nav className="flex flex-1 flex-col">
          <ul className="flex flex-col gap-4">
            {menuItems.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  onClick={handleNavigate}
                  data-onboarding-target={item.path === '/faq' ? 'sidebar-faq' : undefined}
                  className={({ isActive }) =>
                    `flex items-center gap-2 h-12 px-4 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                      isActive
                        ? 'text-white [background:linear-gradient(88deg,#563BA6_1.28%,#57389E_15.3%,#593C9E_35.4%,#8359DD_62.97%,#9F63FF_98.48%)]'
                        : 'text-white/60 hover:text-white hover:bg-white/[0.05]'
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
                    `flex items-center gap-2 h-12 px-4 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                      isActive
                        ? 'text-white [background:linear-gradient(88deg,#563BA6_1.28%,#57389E_15.3%,#593C9E_35.4%,#8359DD_62.97%,#9F63FF_98.48%)]'
                        : 'text-white/60 hover:text-white hover:bg-white/[0.05]'
                    }`
                  }
                >
                  {icons.admin}
                  <span>Админка</span>
                </NavLink>
              </li>
            )}
            {isAdmin && (
              <li>
                <NavLink
                  to="/pipeline"
                  onClick={handleNavigate}
                  className={({ isActive }) =>
                    `flex items-center gap-2 h-12 px-4 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                      isActive
                        ? 'text-white [background:linear-gradient(88deg,#563BA6_1.28%,#57389E_15.3%,#593C9E_35.4%,#8359DD_62.97%,#9F63FF_98.48%)]'
                        : 'text-white/60 hover:text-white hover:bg-white/[0.05]'
                    }`
                  }
                >
                  {icons.pipeline}
                  <span>Pipeline</span>
                </NavLink>
              </li>
            )}
            {isAdmin && (
              <li>
                <NavLink
                  to="/cve-pipeline"
                  onClick={handleNavigate}
                  className={({ isActive }) =>
                    `flex items-center gap-2 h-12 px-4 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                      isActive
                        ? 'text-white [background:linear-gradient(88deg,#563BA6_1.28%,#57389E_15.3%,#593C9E_35.4%,#8359DD_62.97%,#9F63FF_98.48%)]'
                        : 'text-white/60 hover:text-white hover:bg-white/[0.05]'
                    }`
                  }
                >
                  {icons.cvePipeline}
                  <span>1 CVE PL</span>
                </NavLink>
              </li>
            )}
            {isAdmin && (
              <li>
                <NavLink
                  to="/nvd-sync"
                  onClick={handleNavigate}
                  className={({ isActive }) =>
                    `flex items-center gap-2 h-12 px-4 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                      isActive
                        ? 'text-white [background:linear-gradient(88deg,#563BA6_1.28%,#57389E_15.3%,#593C9E_35.4%,#8359DD_62.97%,#9F63FF_98.48%)]'
                        : 'text-white/60 hover:text-white hover:bg-white/[0.05]'
                    }`
                  }
                >
                  {icons.nvdSync}
                  <span>NVD Sync</span>
                </NavLink>
              </li>
            )}
            {isAdmin && (
              <li>
                <NavLink
                  to="/admin/contests"
                  onClick={handleNavigate}
                  className={({ isActive }) =>
                    `flex items-center gap-2 h-12 px-4 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] transition-colors duration-300 ease-in-out ${
                      isActive
                        ? 'text-white [background:linear-gradient(88deg,#563BA6_1.28%,#57389E_15.3%,#593C9E_35.4%,#8359DD_62.97%,#9F63FF_98.48%)]'
                        : 'text-white/60 hover:text-white hover:bg-white/[0.05]'
                    }`
                  }
                >
                  {icons.championship}
                  <span>Чемпионаты</span>
                </NavLink>
              </li>
            )}
          </ul>

          {showOnboardingShortcut && (
            <div className="mt-auto pt-4">
              <button
                type="button"
                onClick={handleOnboardingClick}
                className="flex w-full items-center gap-2 h-12 px-4 rounded-lg text-[16px] leading-[20px] tracking-[0.04em] text-white/60 transition-colors duration-300 ease-in-out hover:text-white hover:bg-white/[0.05]"
              >
                {icons.onboarding}
                <span>Онбординг</span>
              </button>
            </div>
          )}
        </nav>
      </div>
    </aside>
  );
}

export default Sidebar;
