import React from 'react';

/**
 * HackNet brand logo — exact SVG from design assets.
 * className controls the size (e.g. "w-12 h-12").
 */
export default function HacknetLogo({ className = 'w-12 h-12', alt = 'HackNet' }) {
  return (
    <svg
      width="48"
      height="48"
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label={alt}
      className={className}
    >
      <path d="M0 12C0 5.37258 5.37258 0 12 0H36C42.6274 0 48 5.37258 48 12V36C48 42.6274 42.6274 48 36 48H12C5.37258 48 0 42.6274 0 36V12Z" fill="url(#hn-logo-bg)" />
      <path d="M26.1186 14.4708H28.2362V10.9414H26.1186V14.4708Z" fill="white" />
      <path d="M21.1774 21.5296V19.412H7.76562V21.5296H21.1774Z" fill="white" />
      <path d="M28.2362 26.4708H26.1186V37.0591H28.2362V26.4708Z" fill="white" />
      <path d="M33.1774 19.412V21.5296H40.2362V19.412H33.1774Z" fill="white" />
      <path d="M26.1186 26.4708H28.2362L30.0009 24.7061L31.5892 23.1179L33.1774 21.5296V19.412L31.4127 17.6473L30.0009 16.2355L28.2362 14.4708H26.1186L24.3539 16.2355L22.7656 17.8238L21.1774 19.412V21.5296L22.9421 23.2943L24.3539 24.7061L26.1186 26.4708Z" fill="white" />
      <defs>
        <linearGradient id="hn-logo-bg" x1="0.84" y1="54.5455" x2="48.9103" y2="53.0385" gradientUnits="userSpaceOnUse">
          <stop stopColor="#563BA6" />
          <stop offset="0.629808" stopColor="#8359DD" />
          <stop offset="1" stopColor="#9F63FF" />
        </linearGradient>
      </defs>
    </svg>
  );
}
