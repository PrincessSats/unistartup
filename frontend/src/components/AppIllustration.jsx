import React, { useId } from 'react';

const trainingThemes = {
  web: { from: '#3E2B95', to: '#7A4FFF', accent: '#A88CFF' },
  forensics: { from: '#215D48', to: '#2F9E75', accent: '#88F2C7' },
  pentest: { from: '#5D2C1F', to: '#C56D3F', accent: '#FFBE8F' },
};

export function TrainingIllustration({ variant = 'web', className }) {
  const theme = trainingThemes[variant] || trainingThemes.web;
  const id = useId();
  const gradientId = `${id}-g`;
  const glowId = `${id}-glow`;

  return (
    <svg viewBox="0 0 304 173" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={theme.from} />
          <stop offset="100%" stopColor={theme.to} />
        </linearGradient>
        <radialGradient id={glowId} cx="0.2" cy="0.2" r="0.8">
          <stop offset="0%" stopColor="rgba(255,255,255,0.55)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </radialGradient>
      </defs>
      <rect x="2" y="2" width="300" height="169" rx="14" fill={`url(#${gradientId})`} />
      <rect x="2" y="2" width="300" height="169" rx="14" fill={`url(#${glowId})`} />
      <circle cx="58" cy="46" r="28" fill="rgba(255,255,255,0.1)" />
      <circle cx="240" cy="46" r="20" fill="rgba(255,255,255,0.1)" />
      <rect x="30" y="90" width="244" height="54" rx="12" fill="rgba(10,10,18,0.28)" />
      <path d="M48 116h84" stroke={theme.accent} strokeWidth="6" strokeLinecap="round" />
      <path d="M48 130h50" stroke="rgba(255,255,255,0.52)" strokeWidth="4" strokeLinecap="round" />
      <rect x="188" y="102" width="72" height="30" rx="8" fill="rgba(255,255,255,0.18)" />
      <rect x="194" y="108" width="24" height="18" rx="4" fill="rgba(255,255,255,0.24)" />
      <rect x="222" y="108" width="32" height="6" rx="3" fill="rgba(255,255,255,0.3)" />
      <rect x="222" y="118" width="22" height="6" rx="3" fill="rgba(255,255,255,0.2)" />
    </svg>
  );
}

export function GlassPanelIllustration({ className }) {
  const id = useId();
  const grad = `${id}-panel-grad`;
  const blur = `${id}-panel-blur`;

  return (
    <svg viewBox="0 0 554 315" className={className} aria-hidden="true">
      <defs>
        <radialGradient id={grad} cx="0.32" cy="0.36" r="0.72">
          <stop offset="0%" stopColor="rgba(255,255,255,0.42)" />
          <stop offset="60%" stopColor="rgba(255,255,255,0.14)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </radialGradient>
        <filter id={blur}>
          <feGaussianBlur stdDeviation="24" />
        </filter>
      </defs>
      <ellipse cx="186" cy="140" rx="210" ry="130" fill={`url(#${grad})`} filter={`url(#${blur})`} />
      <ellipse cx="364" cy="188" rx="170" ry="110" fill="rgba(255,255,255,0.1)" filter={`url(#${blur})`} />
      <path d="M48 254C142 206 252 192 382 206c52 5 96 17 132 34" stroke="rgba(255,255,255,0.35)" strokeWidth="2" />
    </svg>
  );
}

export function HeroGlassIllustration({ className }) {
  const id = useId();
  const grad = `${id}-hero-grad`;
  const blur = `${id}-hero-blur`;

  return (
    <svg viewBox="0 0 1243 847" className={className} aria-hidden="true">
      <defs>
        <radialGradient id={grad} cx="0.25" cy="0.25" r="0.85">
          <stop offset="0%" stopColor="rgba(255,255,255,0.45)" />
          <stop offset="58%" stopColor="rgba(255,255,255,0.14)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </radialGradient>
        <filter id={blur}>
          <feGaussianBlur stdDeviation="40" />
        </filter>
      </defs>
      <ellipse cx="420" cy="300" rx="420" ry="240" fill={`url(#${grad})`} filter={`url(#${blur})`} />
      <ellipse cx="760" cy="420" rx="350" ry="220" fill="rgba(255,255,255,0.12)" filter={`url(#${blur})`} />
      <path d="M82 660c192-86 412-108 652-62 120 24 237 66 344 124" stroke="rgba(255,255,255,0.3)" strokeWidth="3" />
    </svg>
  );
}

export function PodiumAvatarIllustration({ rank = 1, className }) {
  const colors =
    rank === 1
      ? { from: '#5D4B1F', to: '#B88A27' }
      : rank === 2
        ? { from: '#344156', to: '#7A89A6' }
        : { from: '#5B3C33', to: '#9D5D47' };
  const id = useId();
  const grad = `${id}-avatar-grad`;

  return (
    <svg viewBox="0 0 116 116" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={grad} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={colors.from} />
          <stop offset="100%" stopColor={colors.to} />
        </linearGradient>
      </defs>
      <rect width="116" height="116" rx="24" fill={`url(#${grad})`} />
      <circle cx="58" cy="46" r="16" fill="rgba(255,255,255,0.8)" />
      <path d="M30 98a28 28 0 0 1 56 0" fill="rgba(255,255,255,0.8)" />
    </svg>
  );
}

export function PodiumShelfIllustration({ className }) {
  const id = useId();
  const grad = `${id}-podium-shelf-main`;

  return (
    <svg viewBox="0 0 1592 180" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={grad} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="rgba(255,255,255,0.03)" />
          <stop offset="50%" stopColor="rgba(255,255,255,0.16)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0.03)" />
        </linearGradient>
      </defs>
      <path d="M0 124 212 88h1168l212 36v56H0z" fill={`url(#${grad})`} />
      <path d="M0 124 212 88h1168l212 36" stroke="rgba(255,255,255,0.18)" strokeWidth="2" />
    </svg>
  );
}
