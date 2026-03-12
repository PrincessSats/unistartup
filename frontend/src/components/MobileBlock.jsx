import React from 'react';
import HacknetLogo from './HacknetLogo';

export default function MobileBlock() {
  const handleRequestDesktop = () => {
    // Attempt to open the desktop version hint — most mobile browsers honour this
    const metaViewport = document.querySelector('meta[name="viewport"]');
    if (metaViewport) {
      metaViewport.setAttribute('content', 'width=1280');
    }
    window.location.reload();
  };

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-start pt-16 px-6 text-white"
      style={{ background: '#0B0A10' }}
    >
      {/* Logo */}
      <HacknetLogo className="w-14 h-14 mb-6" />

      {/* Badge */}
      <div
        className="mb-5 px-4 py-1.5 rounded-full text-sm text-zinc-400 border border-zinc-700"
        style={{ background: 'rgba(255,255,255,0.04)' }}
      >
        Мобильная версия
      </div>

      {/* Heading */}
      <h1 className="text-3xl font-bold text-center mb-3 leading-tight">
        Мы ещё не добрались до смартфонов!
      </h1>

      {/* Subtitle */}
      <p className="text-zinc-400 text-center text-base max-w-xs mb-8 leading-relaxed">
        Мы работаем над адаптацией под мобильные устройства. Пожалуйста, зайди с&nbsp;компьютера или запроси ПК&#8209;версию сайта.
      </p>

      {/* CTA button */}
      <button
        onClick={handleRequestDesktop}
        className="px-8 py-3 rounded-xl font-semibold text-white transition-opacity hover:opacity-90 active:opacity-75"
        style={{ background: 'linear-gradient(90deg, #7C5CFC 0%, #9B59F5 100%)' }}
      >
        Запросить ПК&#8209;версию
      </button>

      {/* Support hint */}
      <p className="mt-6 text-sm text-zinc-500 text-center">
        Нужна помощь?{' '}
        <a
          href="https://t.me/hacknet_support"
          target="_blank"
          rel="noopener noreferrer"
          className="text-white font-semibold hover:underline"
        >
          Напиши в поддержку
        </a>
      </p>

      {/* Illustration — monitor + phone */}
      <div className="mt-14 w-full flex justify-center">
        <svg
          width="280"
          height="200"
          viewBox="0 0 280 200"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          {/* Monitor */}
          <rect x="30" y="20" width="160" height="110" rx="12" fill="#5B4FCF" />
          <rect x="38" y="28" width="144" height="94" rx="8" fill="#1A1630" />
          {/* Screen content lines */}
          <rect x="52" y="44" width="80" height="8" rx="4" fill="#7C5CFC" opacity="0.7" />
          <rect x="52" y="60" width="116" height="6" rx="3" fill="#3D3560" />
          <rect x="52" y="72" width="96" height="6" rx="3" fill="#3D3560" />
          <rect x="52" y="84" width="60" height="6" rx="3" fill="#3D3560" />
          {/* Monitor stand */}
          <rect x="95" y="130" width="30" height="16" rx="4" fill="#4A3FB5" />
          <rect x="78" y="146" width="64" height="8" rx="4" fill="#4A3FB5" />

          {/* Phone — overlapping on the right */}
          <rect x="178" y="60" width="68" height="118" rx="14" fill="#3D3480" />
          <rect x="184" y="70" width="56" height="96" rx="8" fill="#1A1630" />
          {/* Phone notch */}
          <rect x="202" y="64" width="20" height="4" rx="2" fill="#2A2560" />
          {/* Phone screen content */}
          <rect x="192" y="82" width="40" height="6" rx="3" fill="#7C5CFC" opacity="0.7" />
          <rect x="192" y="95" width="40" height="5" rx="2.5" fill="#3D3560" />
          <rect x="192" y="107" width="28" height="5" rx="2.5" fill="#3D3560" />
          {/* Phone home bar */}
          <rect x="202" y="156" width="20" height="4" rx="2" fill="#3D3560" />

          {/* "No mobile" X badge on phone */}
          <circle cx="226" cy="68" r="12" fill="#0B0A10" />
          <circle cx="226" cy="68" r="10" fill="#E74C3C" opacity="0.9" />
          <line x1="221" y1="63" x2="231" y2="73" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
          <line x1="231" y1="63" x2="221" y2="73" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      </div>
    </div>
  );
}
