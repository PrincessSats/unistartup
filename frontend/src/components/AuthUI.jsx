import React from 'react';
import AppIcon from './AppIcon';
import HacknetLogo from './HacknetLogo';

function GithubIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 0C5.37 0 0 5.37 0 12a12 12 0 0 0 8.21 11.39c.6.11.79-.26.79-.58v-2.23c-3.34.73-4.03-1.42-4.03-1.42-.55-1.39-1.33-1.76-1.33-1.76-1.09-.74.08-.73.08-.73 1.21.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.49 1 .11-.78.42-1.31.76-1.61-2.66-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.12-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6.01 0c2.29-1.55 3.3-1.23 3.3-1.23.65 1.66.24 2.88.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.61-2.81 5.62-5.48 5.92.43.37.82 1.1.82 2.22v3.29c0 .32.19.7.8.58A12 12 0 0 0 24 12c0-6.63-5.37-12-12-12Z" />
    </svg>
  );
}

function AppleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83ZM13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11Z" />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09Z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23Z" />
      <path fill="#FBBC05" d="M5.84 14.09A7.03 7.03 0 0 1 5.49 12c0-.73.13-1.43.35-2.09V7.07H2.18A11.97 11.97 0 0 0 1 12c0 1.78.43 3.45 1.18 4.93l3.66-2.84Z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53Z" />
    </svg>
  );
}

function YandexIcon() {
  return (
    <span className="flex h-4 w-4 items-center justify-center rounded-[6px] bg-[#FC3F1D] text-[10px] font-semibold text-white" aria-hidden="true">
      Я
    </span>
  );
}

function TelegramIcon() {
  return (
    <svg className="h-4 w-4 text-[#26A5E4]" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0h-.056Zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635Z" />
    </svg>
  );
}

function SocialButton({ icon, children, onClick, disabled = false, fullWidth = false, accent = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={[
        'flex h-14 items-center justify-center gap-2 rounded-[18px] border text-[15px] font-medium transition',
        fullWidth ? 'w-full' : 'w-full',
        accent
          ? 'border-[#8D63FF] bg-[#181226] text-white hover:border-[#9B6BFF] hover:bg-[#1D1730]'
          : 'border-white/10 bg-white/[0.03] text-white hover:border-white/20 hover:bg-white/[0.06]',
        disabled ? 'cursor-not-allowed opacity-60' : '',
      ].join(' ')}
    >
      {icon}
      <span>{children}</span>
    </button>
  );
}

export function AuthShell({ title, children, className = '', titleClassName = '' }) {
  return (
    <div className="min-h-screen bg-[#0B0A10] bg-[radial-gradient(circle_at_top,_rgba(132,82,255,0.18)_0,_rgba(11,10,16,0)_42%)] px-6 py-16 font-sans-figma text-white">
      <div className={`mx-auto flex min-h-[calc(100vh-8rem)] w-full max-w-[851px] flex-col items-center justify-center ${className}`}>
        <HacknetLogo className="mb-8 h-12 w-12" />
        {title ? (
          <h1 className={`mb-8 text-center text-[44px] font-medium leading-[1] tracking-[-0.03em] text-white ${titleClassName}`}>
            {title}
          </h1>
        ) : null}
        {children}
      </div>
    </div>
  );
}

export function AuthSurface({ children, className = '' }) {
  return (
    <div className={`w-full max-w-[576px] rounded-[28px] border border-white/10 bg-[#14111B]/95 px-12 py-12 shadow-[0_40px_120px_-56px_rgba(0,0,0,0.9)] backdrop-blur ${className}`}>
      {children}
    </div>
  );
}

export function AuthPrimaryButton({ children, disabled = false, className = '', type = 'button', ...props }) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={[
        'h-14 w-full rounded-[18px] text-[15px] font-medium transition',
        disabled
          ? 'cursor-not-allowed border border-white/8 bg-white/[0.03] text-white/35'
          : 'bg-[#8452FF] text-white hover:bg-[#9365FF]',
        className,
      ].join(' ')}
      {...props}
    >
      {children}
    </button>
  );
}

export function PasswordVisibilityButton({ visible, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="absolute right-4 top-1/2 -translate-y-1/2 text-white/45 transition hover:text-white"
      aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'}
    >
      <AppIcon name={visible ? 'eye-off' : 'eye'} className="h-5 w-5" />
    </button>
  );
}

export function AuthDivider({ label }) {
  return (
    <div className="flex items-center gap-4">
      <div className="h-px flex-1 bg-white/10" />
      <span className="text-[12px] leading-4 text-white/45">{label}</span>
      <div className="h-px flex-1 bg-white/10" />
    </div>
  );
}

export function SocialAuthButtons({
  mode = 'login',
  onYandex,
  footerLabel,
  footerActionLabel,
  onFooterAction,
  yandexDisabled = false,
}) {
  const dividerLabel = mode === 'register' ? 'Или зарегистрироваться через' : 'Или войти через';

  return (
    <div className="space-y-4">
      <AuthDivider label={dividerLabel} />

      <div className="space-y-2">
        <SocialButton icon={<GithubIcon />} fullWidth>
          GitHub
        </SocialButton>

        <div className="grid grid-cols-2 gap-2">
          <SocialButton icon={<AppleIcon />}>Apple</SocialButton>
          <SocialButton icon={<GoogleIcon />}>Google</SocialButton>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <SocialButton icon={<YandexIcon />} onClick={onYandex} disabled={yandexDisabled} accent>
            Яндекс
          </SocialButton>
          <SocialButton icon={<TelegramIcon />}>Телеграм</SocialButton>
        </div>
      </div>

      <div className="flex items-center justify-center gap-1 text-[14px] text-white/52">
        <span>{footerLabel}</span>
        <button
          type="button"
          onClick={onFooterAction}
          className="font-medium text-white transition hover:text-[#AB85FF]"
        >
          {footerActionLabel}
        </button>
      </div>
    </div>
  );
}
