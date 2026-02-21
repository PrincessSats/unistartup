import React from 'react';

function getIconPath(name) {
  switch (name) {
    case 'home':
      return (
        <>
          <path d="M3 11.5 12 4l9 7.5" />
          <path d="M5 10.5V20h14v-9.5" />
        </>
      );
    case 'championship':
      return (
        <>
          <path d="M8 4h8v3a4 4 0 0 1-8 0V4Z" />
          <path d="M8 7H5a3 3 0 0 0 3 3" />
          <path d="M16 7h3a3 3 0 0 1-3 3" />
          <path d="M12 11v4" />
          <path d="M9.5 20h5" />
          <path d="M10 15h4v5h-4z" />
        </>
      );
    case 'education':
      return (
        <>
          <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z" />
          <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H20" />
          <path d="M8 8h8" />
          <path d="M8 12h8" />
        </>
      );
    case 'rating':
      return (
        <>
          <path d="M4 19h16" />
          <path d="m7 14 3-3 3 2 4-5" />
          <path d="m16.2 8 1.8-.2-.2 1.8" />
        </>
      );
    case 'knowledge':
    case 'doc':
      return (
        <>
          <path d="M8 3h7l4 4v13a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" />
          <path d="M15 3v4h4" />
          <path d="M9 13h6" />
          <path d="M9 17h6" />
        </>
      );
    case 'faq':
      return (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="M9.5 9a2.5 2.5 0 0 1 4.8 1c0 1.3-1 1.9-1.8 2.5-.6.4-1 .8-1 1.5" />
          <circle cx="12" cy="16.6" r="0.9" fill="currentColor" stroke="none" />
        </>
      );
    case 'admin':
      return (
        <>
          <path d="m12 3-7 3v6c0 4.5 2.7 7.2 7 9 4.3-1.8 7-4.5 7-9V6l-7-3z" />
          <path d="m9 12 2 2 4-4" />
        </>
      );
    case 'search':
      return (
        <>
          <circle cx="11" cy="11" r="6.5" />
          <path d="m16 16 4 4" />
        </>
      );
    case 'support':
      return (
        <>
          <path d="M6 5h12a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3h-7l-5 4v-4H6a3 3 0 0 1-3-3V8a3 3 0 0 1 3-3z" />
          <path d="M8 10h8" />
          <path d="M8 13h5" />
        </>
      );
    case 'person':
      return (
        <>
          <circle cx="12" cy="8" r="3.5" />
          <path d="M5 20a7 7 0 0 1 14 0" />
        </>
      );
    case 'star':
      return (
        <path d="m12 4 2.44 4.94 5.45.79-3.95 3.84.93 5.43L12 16.42 7.13 19l.93-5.43-3.95-3.84 5.45-.79L12 4z" />
      );
    case 'flag':
      return (
        <>
          <path d="M5 4v16" />
          <path d="M5 5h10l-1.8 3L15 11H5" />
        </>
      );
    case 'cup':
      return (
        <>
          <path d="M8 4h8v3a4 4 0 0 1-8 0V4Z" />
          <path d="M8 7H5a3 3 0 0 0 3 3" />
          <path d="M16 7h3a3 3 0 0 1-3 3" />
          <path d="M12 11v4" />
          <path d="M9 20h6" />
          <path d="M10 15h4v5h-4z" />
        </>
      );
    case 'close':
      return (
        <>
          <path d="m6 6 12 12" />
          <path d="M18 6 6 18" />
        </>
      );
    case 'eye':
      return (
        <>
          <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z" />
          <circle cx="12" cy="12" r="2.5" />
        </>
      );
    case 'arrow-left':
      return <path d="m15 6-6 6 6 6" />;
    case 'check-circle':
      return (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="m8.5 12.2 2.2 2.2 4.8-4.8" />
        </>
      );
    default:
      return (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 8v4" />
          <circle cx="12" cy="16.5" r="0.8" fill="currentColor" stroke="none" />
        </>
      );
  }
}

function AppIcon({ name, className = 'w-5 h-5', title }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? 'img' : 'presentation'}
      aria-hidden={title ? undefined : true}
    >
      {title ? <title>{title}</title> : null}
      {getIconPath(name)}
    </svg>
  );
}

export default AppIcon;
