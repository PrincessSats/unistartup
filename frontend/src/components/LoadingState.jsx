import React from 'react';

export function SkeletonBlock({ className = '' }) {
  return (
    <div
      className={`skeleton-shimmer rounded-[12px] border border-white/[0.08] bg-white/[0.03] ${className}`}
      aria-hidden="true"
    />
  );
}

function DefaultPageSkeleton() {
  return (
    <div className="space-y-6">
      <SkeletonBlock className="h-11 w-[220px]" />

      <div className="flex flex-wrap gap-3">
        <SkeletonBlock className="h-12 w-[180px]" />
        <SkeletonBlock className="h-12 w-[140px]" />
        <SkeletonBlock className="h-12 w-[160px]" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <SkeletonBlock className="h-[210px] w-full" />
        <SkeletonBlock className="h-[210px] w-full" />
        <SkeletonBlock className="h-[210px] w-full" />
      </div>

      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <SkeletonBlock key={`page-loader-row-${index}`} className="h-16 w-full rounded-[16px]" />
        ))}
      </div>
    </div>
  );
}

function HomePageSkeleton() {
  return (
    <div className="space-y-8">
      <SkeletonBlock className="h-[260px] w-full rounded-[20px]" />

      <div className="grid gap-4 xl:grid-cols-[1fr_440px]">
        <div className="space-y-4">
          <SkeletonBlock className="h-[420px] w-full rounded-[20px]" />
          <SkeletonBlock className="h-[300px] w-full rounded-[20px]" />
          <SkeletonBlock className="h-[260px] w-full rounded-[20px]" />
        </div>
        <div className="space-y-4">
          <SkeletonBlock className="h-[180px] w-full rounded-[20px]" />
          <SkeletonBlock className="h-[180px] w-full rounded-[20px]" />
          <SkeletonBlock className="h-[520px] w-full rounded-[20px]" />
        </div>
      </div>
    </div>
  );
}

function EducationPageSkeleton() {
  return (
    <div className="space-y-6">
      <SkeletonBlock className="h-11 w-[220px]" />

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <SkeletonBlock className="h-14 w-full" />
        <SkeletonBlock className="h-14 w-full" />
        <SkeletonBlock className="h-14 w-full" />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 2xl:grid-cols-3 3xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, index) => (
          <SkeletonBlock key={`education-loader-card-${index}`} className="h-[430px] w-full rounded-[16px]" />
        ))}
      </div>
    </div>
  );
}

function KnowledgePageSkeleton() {
  return (
    <div className="space-y-6">
      <SkeletonBlock className="h-11 w-[240px]" />

      <div className="flex flex-wrap items-center justify-between gap-4">
        <SkeletonBlock className="h-11 w-[260px]" />
        <div className="flex gap-3">
          <SkeletonBlock className="h-11 w-[160px]" />
          <SkeletonBlock className="h-11 w-[170px]" />
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <SkeletonBlock key={`knowledge-loader-card-${index}`} className="h-[420px] w-full rounded-[16px]" />
        ))}
      </div>
    </div>
  );
}

function ChampionshipPageSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_420px]">
        <SkeletonBlock className="h-[760px] w-full rounded-[16px]" />
        <SkeletonBlock className="h-[760px] w-full rounded-[16px]" />
      </div>
      <SkeletonBlock className="h-[420px] w-full rounded-[16px]" />
    </div>
  );
}

function RatingPageSkeleton() {
  return (
    <div className="space-y-8">
      <div className="space-y-5">
        <SkeletonBlock className="h-11 w-[180px]" />

        <div className="flex flex-wrap items-center justify-between gap-4">
          <SkeletonBlock className="h-14 w-[342px]" />
          <SkeletonBlock className="h-14 w-[300px]" />
        </div>
      </div>

      <SkeletonBlock className="h-[480px] w-full rounded-[20px]" />

      <SkeletonBlock className="mx-auto h-[720px] w-full max-w-[1114px] rounded-[20px]" />
    </div>
  );
}

function EducationTaskPageSkeleton() {
  return (
    <div className="space-y-4">
      <SkeletonBlock className="h-[520px] w-full rounded-[20px]" />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_380px]">
        <SkeletonBlock className="h-[460px] w-full rounded-[20px]" />
        <SkeletonBlock className="h-[460px] w-full rounded-[20px]" />
      </div>
    </div>
  );
}

function KnowledgeArticlePageSkeleton() {
  return (
    <div className="space-y-8">
      <SkeletonBlock className="h-[426px] w-full rounded-[20px]" />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[142px_1fr]">
        <div className="space-y-3">
          <SkeletonBlock className="h-10 w-full" />
          <SkeletonBlock className="h-10 w-full" />
          <SkeletonBlock className="h-10 w-full" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 7 }).map((_, index) => (
            <SkeletonBlock key={`knowledge-article-paragraph-${index}`} className="h-5 w-full rounded-[8px]" />
          ))}
        </div>
      </div>

      <SkeletonBlock className="h-[340px] w-full max-w-[900px] rounded-[16px]" />
    </div>
  );
}

function ProfilePageSkeleton() {
  return (
    <div className="space-y-4">
      <SkeletonBlock className="h-11 w-[260px]" />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[444px_1fr]">
        <SkeletonBlock className="h-[640px] w-full rounded-[20px]" />
        <SkeletonBlock className="h-[640px] w-full rounded-[20px]" />
      </div>
    </div>
  );
}

function AdminPageSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <SkeletonBlock key={`admin-stat-${index}`} className="h-[130px] w-full rounded-[16px]" />
        ))}
      </div>
      <SkeletonBlock className="h-[340px] w-full rounded-[16px]" />
      <SkeletonBlock className="h-[460px] w-full rounded-[16px]" />
    </div>
  );
}

const pageSkeletons = {
  default: DefaultPageSkeleton,
  home: HomePageSkeleton,
  education: EducationPageSkeleton,
  knowledge: KnowledgePageSkeleton,
  championship: ChampionshipPageSkeleton,
  rating: RatingPageSkeleton,
  'education-task': EducationTaskPageSkeleton,
  'knowledge-article': KnowledgeArticlePageSkeleton,
  profile: ProfilePageSkeleton,
  admin: AdminPageSkeleton,
};

export function InlineLoader({ label = 'Загрузка...' }) {
  return (
    <div className="inline-flex items-center gap-3 text-white/70">
      <SkeletonBlock className="h-4 w-24 rounded-[8px] border-white/[0.06]" />
      <span className="text-[14px] leading-[20px] tracking-[0.04em]">{label}</span>
    </div>
  );
}

export function PageLoader({ label = 'Загрузка...', variant = 'default' }) {
  const Skeleton = pageSkeletons[variant] || pageSkeletons.default;

  return (
    <div className="flex min-h-[48vh] justify-center font-sans-figma">
      <div className="w-full max-w-[1240px] space-y-6">
        <div className="text-[15px] leading-[20px] tracking-[0.04em] text-white/60">{label}</div>
        <Skeleton />
      </div>
    </div>
  );
}

export function FullScreenLoader({ label = 'Загрузка...' }) {
  return (
    <div className="min-h-screen bg-[#0B0A10] font-sans-figma">
      <div className="flex min-h-screen">
        <aside className="hidden w-[264px] border-r border-white/[0.09] xl:flex xl:flex-col">
          <div className="space-y-8 px-8 py-8">
            <div className="flex items-center gap-4">
              <SkeletonBlock className="h-12 w-12 rounded-[14px]" />
              <SkeletonBlock className="h-6 w-24 rounded-[8px]" />
            </div>

            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <SkeletonBlock key={`full-screen-sidebar-${index}`} className="h-11 w-full rounded-[10px]" />
              ))}
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-white/[0.09] px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-4">
              <SkeletonBlock className="h-12 flex-1 rounded-[10px]" />
              <SkeletonBlock className="h-12 w-12 rounded-[10px]" />
              <SkeletonBlock className="h-12 w-12 rounded-[10px]" />
            </div>
          </header>

          <main className="flex-1 px-4 py-4 sm:px-6 lg:px-8">
            <div className="mb-6 text-[16px] leading-[20px] tracking-[0.04em] text-white/60">{label}</div>
            <DefaultPageSkeleton />
          </main>
        </div>
      </div>
    </div>
  );
}

export function SkeletonList({ rows = 3 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <SkeletonBlock key={`skeleton-row-${index}`} className="h-14 w-full" />
      ))}
    </div>
  );
}
