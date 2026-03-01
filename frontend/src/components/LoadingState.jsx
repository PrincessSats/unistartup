import React from 'react';

function Spinner({ size = 'md' }) {
  const sizeClasses = size === 'sm'
    ? 'h-5 w-5 border-2'
    : size === 'lg'
      ? 'h-10 w-10 border-[3px]'
      : 'h-7 w-7 border-2';

  return (
    <span
      className={`loading-ring inline-block rounded-full border-solid border-white/20 border-t-[#9B6BFF] ${sizeClasses}`}
      aria-hidden="true"
    />
  );
}

export function InlineLoader({ label = 'Загрузка...' }) {
  return (
    <div className="inline-flex items-center gap-3 text-white/70">
      <Spinner size="sm" />
      <span>{label}</span>
    </div>
  );
}

export function PageLoader({ label = 'Загрузка...' }) {
  return (
    <div className="flex min-h-[40vh] items-center justify-center font-sans-figma">
      <div className="flex items-center gap-3 rounded-[14px] border border-white/[0.12] bg-white/[0.04] px-4 py-3 text-white/75">
        <Spinner />
        <span>{label}</span>
      </div>
    </div>
  );
}

export function FullScreenLoader({ label = 'Загрузка...' }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0B0A10] font-sans-figma">
      <div className="flex items-center gap-3 rounded-[16px] border border-white/[0.12] bg-white/[0.04] px-5 py-4 text-white/80">
        <Spinner size="lg" />
        <span className="text-[17px]">{label}</span>
      </div>
    </div>
  );
}

export function SkeletonList({ rows = 3 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={`skeleton-row-${index}`}
          className="h-14 animate-pulse rounded-[12px] border border-white/[0.08] bg-white/[0.04]"
        />
      ))}
    </div>
  );
}
