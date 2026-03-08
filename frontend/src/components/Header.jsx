// frontend/src/components/Header.jsx

import React from 'react';
import { useNavigate } from 'react-router-dom';
import AppIcon from './AppIcon';
import { SkeletonBlock } from './LoadingState';

function Header({
  username,
  avatarUrl,
  isAuthenticated,
  loading,
  onSupportClick,
  onOnboardingClick,
  isAdmin = false,
  onMenuToggle,
}) {
  const navigate = useNavigate();

  return (
    <header className="bg-[#0D0D0D]/10 border-b border-white/[0.09] backdrop-blur-[64px] font-sans-figma">
      <div className="flex items-center justify-between gap-3 px-3 py-3 sm:px-6 sm:py-4 lg:px-8 lg:py-8">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <button
            type="button"
            onClick={onMenuToggle}
            className="inline-flex h-11 w-11 items-center justify-center rounded-[10px] border border-white/[0.09] bg-white/[0.03] text-white/80 xl:hidden"
            aria-label="Открыть меню"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 7h16M4 12h16M4 17h16" />
            </svg>
          </button>

          <div className="min-w-0 flex-1 max-w-[1062px]">
            <div className="flex h-12 items-center gap-4 rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-3 sm:h-14 sm:px-5">
              <AppIcon name="search" className="h-5 w-5 text-white/70 sm:h-[22px] sm:w-[22px]" />
              <input
                type="text"
                placeholder="Ищи задания, материалы или пользователей..."
                className="w-full min-w-0 bg-transparent text-[14px] leading-[20px] tracking-[0.04em] text-white placeholder:text-white/60 focus:outline-none sm:text-[16px] sm:leading-[22px] lg:text-[18px] lg:leading-[24px]"
              />
            </div>
          </div>
        </div>

        <div className="ml-1 flex shrink-0 items-center gap-2 sm:ml-4 sm:gap-4 lg:gap-6">
          {loading ? (
            <div className="flex items-center gap-2 sm:gap-3">
              <SkeletonBlock className="h-11 w-24 rounded-[10px] sm:h-14 sm:w-28" />
              <SkeletonBlock className="h-11 w-11 rounded-[10px] sm:h-[54px] sm:w-[54px]" />
            </div>
          ) : isAuthenticated ? (
            <>
              {isAdmin && (
                <button
                  type="button"
                  onClick={onOnboardingClick}
                  className="inline-flex h-11 items-center gap-2 rounded-lg border border-white/[0.09] bg-white/[0.03] px-3 text-[14px] leading-[20px] tracking-[0.04em] text-white/60 transition-colors hover:bg-white/[0.05] hover:text-white sm:h-14 sm:px-5 sm:text-[16px]"
                >
                  <AppIcon name="education" className="h-5 w-5" />
                  Онбординг
                </button>
              )}
              <button
                type="button"
                onClick={onSupportClick}
                aria-label="Оставить отзыв"
                className="flex h-11 w-11 items-center justify-center rounded-[10px] bg-white/[0.05] text-white/80 transition-colors hover:text-white sm:h-14 sm:w-14"
              >
                <AppIcon name="support" className="h-6 w-6" />
              </button>

              <div className="flex items-center gap-2 border-l border-white/[0.09] pl-2 sm:gap-4 sm:pl-4">
                <button onClick={() => navigate('/profile')} className="flex min-w-0 items-center gap-2 sm:gap-4">
                  <span className="hidden max-w-[220px] truncate font-mono-figma text-[18px] leading-[24px] tracking-[0.02em] text-white/60 md:block">
                    {username}
                  </span>
                  <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-[10px] bg-[#9B6BFF] sm:h-[54px] sm:w-[54px]">
                    {avatarUrl ? (
                      <img src={avatarUrl} alt="Avatar" className="h-full w-full object-cover" />
                    ) : (
                      <AppIcon name="person" className="h-[22px] w-[22px] text-white" />
                    )}
                  </div>
                </button>
              </div>
            </>
          ) : (
            <div className="flex items-center gap-2 sm:gap-3">
              <button
                onClick={() => navigate('/login')}
                className="rounded-[10px] border border-white/[0.09] bg-white/[0.05] px-4 py-2 font-sans-figma text-[14px] leading-[20px] tracking-[0.04em] text-white/80 transition-colors hover:bg-white/[0.1] hover:text-white sm:px-5 sm:py-2.5 sm:text-[16px]"
              >
                Войти
              </button>
              <button
                onClick={() => navigate('/register')}
                className="rounded-[10px] bg-[#9B6BFF] px-4 py-2 font-sans-figma text-[14px] leading-[20px] tracking-[0.04em] text-white transition-colors hover:bg-[#8B5CF6] sm:px-5 sm:py-2.5 sm:text-[16px]"
              >
                Регистрация
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

export default Header;
