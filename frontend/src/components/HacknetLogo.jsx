import React from 'react';
import logoSrc from '../logo.png';

export default function HacknetLogo({ className = 'w-12 h-12', alt = 'HackNet' }) {
  return (
    <img
      src={logoSrc}
      alt={alt}
      width={48}
      height={48}
      loading="eager"
      decoding="async"
      className={`${className} block shrink-0`}
    />
  );
}
