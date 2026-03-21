import React from 'react';

export const UsersIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M16.5 19c0-2.5-2-4.5-4.5-4.5S7.5 16.5 7.5 19" />
    <circle cx="12" cy="8.5" r="3.5" />
    <path d="M20 19c0-2-1.1-3.7-2.8-4.4" />
    <path d="M4 19c0-2 1.1-3.7 2.8-4.4" />
  </svg>
);

export const ActivityIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M4 12h4l2.5-5 3 10 2-5h4.5" />
  </svg>
);

export const CreditIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <rect x="3" y="6" width="18" height="12" rx="2" />
    <path d="M3 10h18" />
    <path d="M7 15h4" />
  </svg>
);

export const TrophyIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M8 5h8v3a4 4 0 0 1-8 0V5Z" />
    <path d="M6 5h2v2a4 4 0 0 0 4 4" />
    <path d="M18 5h2v2a4 4 0 0 1-4 4" />
    <path d="M12 12v4" />
    <path d="M8 20h8" />
  </svg>
);

export const MessageIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M5 17l-1 4 4-2h9a4 4 0 0 0 4-4V7a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v10a4 4 0 0 0 2 0Z" />
  </svg>
);

export const FlagIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M5 4v16" />
    <path d="M5 5h10l-1.5 3L15 11H5" />
  </svg>
);

export const FileIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
    <path d="M14 3v5h5" />
  </svg>
);

const Icons = {
  UsersIcon,
  ActivityIcon,
  CreditIcon,
  TrophyIcon,
  MessageIcon,
  FlagIcon,
  FileIcon,
};

export default Icons;
