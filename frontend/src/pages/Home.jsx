import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useOutletContext } from 'react-router-dom';
import { educationAPI, knowledgeAPI, ratingsAPI, authAPI, profileAPI } from '../services/api';
import FeedbackModal from '../components/FeedbackModal';
import AppIcon from '../components/AppIcon';
import { TrainingIllustration } from '../components/AppIllustration';
import { SkeletonBlock } from '../components/LoadingState';
import HomeOnboardingOverlay from '../components/HomeOnboardingOverlay';
import { getEducationCardVisual } from '../utils/educationVisuals';

const DEFAULT_USERNAME = 'Пользователь';

const trainingCards = [
  {
    variant: 'web',
    title: 'Основы шифрования RSA',
    description: 'Изучи основы криптографии RSA и безопасного обмена ключами шифрования',
    tags: ['Веб', 'Среднее'],
    duration: '45 мин',
    progress: 67,
    points: 450,
  },
  {
    variant: 'forensics',
    title: 'Основы шифрования RSA',
    description: 'Изучи основы криптографии RSA и безопасного обмена ключами шифрования',
    tags: ['Форензика', 'Сложно'],
    duration: '45 мин',
    progress: 67,
    points: 450,
  },
  {
    variant: 'pentest',
    title: 'Основы шифрования RSA',
    description: 'Изучи основы криптографии RSA и безопасного обмена ключами шифрования',
    tags: ['Pentest Machine', 'Легко'],
    duration: '45 мин',
    progress: 67,
    points: 450,
  },
];


const knowledgeAreas = [
  'Веб',
  'OSINT',
  'Криптография',
  'Форензика',
  'Reverse',
  'Pentest',
  'Blue Team',
  'Network',
];

const HOME_KNOWLEDGE_CACHE_KEY = 'home:knowledge-feed:v1';
const HOME_KNOWLEDGE_CACHE_TTL_MS = 5 * 60 * 1000;
const HOME_LEADERBOARD_CACHE_KEY = 'home:leaderboard-stats:v1';
const HOME_LEADERBOARD_CACHE_TTL_MS = 2 * 60 * 1000;
const ONBOARDING_STEPS_COUNT = 4;

function readKnowledgeFeedCache() {
  try {
    const raw = localStorage.getItem(HOME_KNOWLEDGE_CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    const items = Array.isArray(parsed?.items) ? parsed.items : [];
    const savedAt = Number(parsed?.savedAt) || 0;
    if (!savedAt || Date.now() - savedAt > HOME_KNOWLEDGE_CACHE_TTL_MS) {
      return [];
    }
    return items;
  } catch {
    return [];
  }
}

function writeKnowledgeFeedCache(items) {
  try {
    localStorage.setItem(
      HOME_KNOWLEDGE_CACHE_KEY,
      JSON.stringify({ items, savedAt: Date.now() })
    );
  } catch {
    // ignore cache write errors
  }
}

function readLeaderboardStatsCache() {
  try {
    const raw = localStorage.getItem(HOME_LEADERBOARD_CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const savedAt = Number(parsed?.savedAt) || 0;
    if (!savedAt || Date.now() - savedAt > HOME_LEADERBOARD_CACHE_TTL_MS) {
      return null;
    }

    const contest = parsed?.contest && typeof parsed.contest === 'object' ? parsed.contest : null;
    const practice = parsed?.practice && typeof parsed.practice === 'object' ? parsed.practice : null;
    if (!contest && !practice) return null;

    return {
      contest,
      practice,
    };
  } catch {
    return null;
  }
}

function writeLeaderboardStatsCache(stats) {
  try {
    localStorage.setItem(
      HOME_LEADERBOARD_CACHE_KEY,
      JSON.stringify({
        contest: stats?.contest || null,
        practice: stats?.practice || null,
        savedAt: Date.now(),
      })
    );
  } catch {
    // ignore cache write errors
  }
}

function toSafeNumber(value, fallback = 0) {
  return Number.isFinite(Number(value)) ? Number(value) : fallback;
}

const practiceStatusOrder = {
  not_started: 0,
  in_progress: 1,
  solved: 2,
};

function getPracticePriority(task) {
  const status = String(task?.my_status || '').trim().toLowerCase();
  const accessType = String(task?.access_type || '').trim().toLowerCase();
  // Chat-задачи можно перепроходить, поэтому не прячем их в конце как обычные solved.
  if (status === 'solved' && accessType === 'chat') {
    return practiceStatusOrder.not_started;
  }
  return practiceStatusOrder[status] ?? 99;
}

const practiceStatusLabel = {
  not_started: 'Не начато',
  in_progress: 'В процессе',
  solved: 'Решено',
};

const practiceDifficultyBadgeClasses = {
  Легко: 'border-[#3FD18A]/30 bg-[#3FD18A]/10 text-[#3FD18A]',
  Средне: 'border-[#F2C94C]/30 bg-[#F2C94C]/10 text-[#F2C94C]',
  Сложно: 'border-[#FF5A6E]/30 bg-[#FF5A6E]/10 text-[#FF5A6E]',
};

function Tag({ children, tone = 'neutral' }) {
  const toneStyles = {
    neutral: 'bg-[#8E51FF]/10 border-[#8E51FF]/30 text-[#A684FF]',
    easy: 'bg-emerald-500/10 border-emerald-400/30 text-emerald-300',
    medium: 'bg-amber-400/10 border-amber-300/30 text-amber-200',
    hard: 'bg-rose-500/10 border-rose-400/30 text-rose-300',
  };

  return (
    <span
      className={`border border-solid rounded-[10px] px-[13px] py-[9px] text-[16px] leading-[19px] tracking-[0.64px] ${
        toneStyles[tone]
      }`}
    >
      {children}
    </span>
  );
}

function ProgressBar({ value = 67, size = 'small' }) {
  if (size === 'small') {
    return (
      <div className="w-[176px]">
        <div className="text-[16px] leading-[20px] tracking-[0.64px] text-white/60 mb-2">
          {value}%
        </div>
        <div className="h-1 rounded-[8px] bg-white/10 overflow-hidden">
          <div className="h-full bg-[#9B6BFF]" style={{ width: `${value}%` }} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 w-full">
      <div className="h-1 rounded-[8px] bg-white/10 overflow-hidden flex-1">
        <div className="h-full bg-[#9B6BFF]" style={{ width: `${value}%` }} />
      </div>
      <div className="text-[16px] leading-[20px] tracking-[0.64px] text-white/60 min-w-[40px] text-right">
        {value}%
      </div>
    </div>
  );
}

function ScoreCard({ label, value, loading = false }) {
  return (
    <div className="bg-white/[0.09] border border-white/[0.14] rounded-[16px] px-[25px] py-[25px] h-[86px] flex items-center justify-between min-w-[220px] flex-1">
      <span className="text-[18px] leading-[24px] tracking-[0.72px] text-white/60">
        {label}
      </span>
      {loading ? (
        <SkeletonBlock className="h-9 w-20 rounded-[8px] border-white/[0.16] bg-white/[0.07]" />
      ) : (
        <span className="font-mono-figma text-[29px] leading-[36px] tracking-[0.58px] text-white">
          {value}
        </span>
      )}
    </div>
  );
}

function TrainingCard({ variant, title, description, tags, duration, progress, points, to }) {
  const difficultyTone = tags[1] === 'Легко' ? 'easy' : tags[1] === 'Среднее' || tags[1] === 'Средне' ? 'medium' : 'hard';
  const containerClasses = `bg-white/[0.05] rounded-[12px] p-6 flex flex-col gap-12 w-full ${to ? 'transition hover:border hover:border-[#9B6BFF]/50' : ''}`;

  const content = (
    <>
      <div className="h-[173px] w-[304px] max-w-full relative overflow-hidden mx-auto">
        <TrainingIllustration variant={variant || 'web'} className="absolute inset-0 w-full h-full" />
      </div>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-4">
          <h3 className="text-[20px] leading-[24px] tracking-[0.4px] text-white">
            {title}
          </h3>
          <p className="text-[16px] leading-[20px] tracking-[0.64px] text-white/60 max-h-[40px] overflow-hidden">
            {description}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <Tag tone="neutral">{tags[0]}</Tag>
          <Tag tone={difficultyTone}>{tags[1]}</Tag>
          <span className="text-[14px] leading-[20px] tracking-[0.64px] text-white/50">
            {duration}
          </span>
        </div>
        <div className="flex items-end justify-between">
          <ProgressBar value={progress} size="small" />
          <div className="flex items-center gap-2">
            <AppIcon name="star" className="w-5 h-5 text-white/80" />
            <span className="font-mono-figma text-[18px] leading-[24px] tracking-[0.36px] text-white">
              {points}
            </span>
          </div>
        </div>
      </div>
    </>
  );

  if (to) {
    return (
      <Link to={to} className={containerClasses}>
        {content}
      </Link>
    );
  }

  return (
    <div className={containerClasses}>
      {content}
    </div>
  );
}

function PracticeTrainingCard({ task }) {
  const visual = getEducationCardVisual(task);
  const difficultyClass = practiceDifficultyBadgeClasses[task?.difficulty_label] || practiceDifficultyBadgeClasses.Средне;
  const isSolved = task?.my_status === 'solved';
  const statusLabel = practiceStatusLabel[task?.my_status] || 'Не начато';

  return (
    <Link
      to={`/education/${task.id}`}
      className="group h-full rounded-[12px] border border-white/[0.06] bg-white/[0.03] p-6 transition hover:border-[#9B6BFF]/60"
    >
      <div className="relative aspect-[16/9] overflow-hidden rounded-[10px] border border-white/[0.06] bg-black/20">
        <img
          src={visual}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
        />
        {isSolved && (
          <span className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-[8px] border border-[#3FD18A]/45 bg-[#3FD18A]/20 px-3 py-[6px] text-[14px] leading-[20px] text-[#3FD18A]">
            <AppIcon name="check-circle" className="h-3.5 w-3.5" />
            Решено
          </span>
        )}
      </div>

      <div className="mt-12 flex flex-col gap-12">
        <div>
          <h3 className="line-clamp-2 text-[20px] leading-[24px] tracking-[0.02em] text-white">
            {task.title}
          </h3>
          <p className="mt-4 line-clamp-2 text-[16px] leading-[20px] tracking-[0.04em] text-white/60">
            {task.summary || 'Описание задачи пока не добавлено'}
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-2">
            <span className="rounded-[8px] border border-white/[0.14] bg-white/[0.05] px-3 py-[6px] text-[14px] leading-[20px] text-white/75">
              {task.category}
            </span>
            <span className={`rounded-[8px] border px-3 py-[6px] text-[14px] leading-[20px] ${difficultyClass}`}>
              {task.difficulty_label}
            </span>
            <span className="rounded-[8px] border border-white/[0.12] bg-white/[0.04] px-3 py-[6px] text-[14px] leading-[20px] text-white/70">
              {statusLabel}
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between text-[16px] leading-[20px] tracking-[0.04em] text-white/65">
          <span>{task.passed_users_count} прошли</span>
          <span className="inline-flex items-center gap-2 font-mono-figma text-[18px] leading-[24px] text-white">
            <AppIcon name="star" className="h-[22px] w-[22px] text-white/80" />
            {task.points}
          </span>
        </div>
      </div>
    </Link>
  );
}


function KnowledgeCard({ title }) {
  return (
    <div className="backdrop-blur-[16px] bg-white/[0.05] rounded-[12px] p-6 w-full">
      <div className="text-[18px] leading-[24px] tracking-[0.72px] text-white mb-6">
        {title}
      </div>
      <ProgressBar value={67} size="large" />
    </div>
  );
}

function TrainingNotificationCard() {
  return (
    <div className="backdrop-blur-[64px] bg-[#9B6BFF]/[0.14] rounded-[20px] p-6 flex flex-col gap-6">
      <div className="flex items-start gap-6">
        <div className="flex-1">
          <div className="text-[20px] leading-[24px] tracking-[0.4px] text-white">
            Пройди обучающую задачу
          </div>
          <div className="text-[16px] leading-[20px] tracking-[0.64px] text-white/60 mt-3">
            За решение получишь первые очки
            <br />в рейтинг
          </div>
        </div>
        <AppIcon name="close" className="w-[22px] h-[22px] text-white/80" />
      </div>
      <button onClick={() => window.location.href = 'https://www.hacknet.tech/#/education/10'} className="bg-[#9B6BFF] rounded-[10px] px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] text-white w-fit">
        Пройти
      </button>
    </div>
  );
}

function FeedbackCard({ onOpen, onClose }) {
  return (
    <div className="backdrop-blur-[64px] bg-[#9B6BFF]/[0.14] rounded-[20px] p-6 flex flex-col gap-6">
      <div className="flex items-start gap-6">
        <div className="flex-1">
          <div className="text-[20px] leading-[24px] tracking-[0.4px] text-white">
            Оцени работу платформы
          </div>
          <div className="text-[16px] leading-[20px] tracking-[0.64px] text-white/60 mt-3">
            Твои идеи и замечания сделают платформу
            <br />
            еще удобнее и подскажут, как нам расти!
          </div>
        </div>
        <button onClick={onClose} className="shrink-0">
          <AppIcon name="close" className="w-[22px] h-[22px] text-white/80" />
        </button>
      </div>
      <button
        onClick={onOpen}
        className="bg-[#9B6BFF] rounded-[10px] px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] text-white w-fit"
      >
        Оценить
      </button>
    </div>
  );
}

function NewsCard({ title, children, icon }) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3 px-4">
        <span className="text-white/80">{icon}</span>
        <span className="text-[23px] leading-[28px] tracking-[0.46px] text-white">
          {title}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {children}
      </div>
    </div>
  );
}

function NewsItem({ title, meta, to }) {
  const content = (
    <>
      <div className="text-[18px] leading-[24px] tracking-[0.72px] text-white truncate">
        {title}
      </div>
      {meta ? (
        <div className="text-[14px] leading-[20px] tracking-[0.64px] text-white/50 mt-2">
          {meta}
        </div>
      ) : null}
    </>
  );

  if (to) {
    return (
      <Link to={to} className="bg-white/[0.05] rounded-[12px] px-4 py-5 transition hover:border hover:border-[#9B6BFF]/50">
        {content}
      </Link>
    );
  }

  return (
    <div className="bg-white/[0.05] rounded-[12px] px-4 py-5">
      {content}
    </div>
  );
}

function TaskNewsItem({ task }) {
  const title = String(task?.title || '').trim() || 'Без названия';
  const category = String(task?.category || '').trim() || 'Без категории';
  const passedUsersCount = toSafeNumber(task?.passed_users_count, 0);

  return (
    <Link to={`/education/${task.id}`} className="bg-white/[0.05] rounded-[12px] px-4 py-5 transition hover:border hover:border-[#9B6BFF]/50">
      <div className="text-[18px] leading-[24px] tracking-[0.72px] text-white truncate">
        {title}
      </div>
      <div className="flex items-center gap-4 mt-3">
        <span className="bg-white/5 border border-white/10 rounded-[10px] px-3 py-1.5 text-[14px] leading-[20px] tracking-[0.64px] text-white/70">
          {category}
        </span>
        <span className="text-[14px] leading-[20px] tracking-[0.64px] text-white/50">
          {passedUsersCount} прошли
        </span>
      </div>
    </Link>
  );
}

function PracticeTrainingCardSkeleton() {
  return (
    <div className="h-full rounded-[12px] border border-white/[0.06] bg-white/[0.03] p-6">
      <SkeletonBlock className="aspect-[16/9] w-full rounded-[10px]" />
      <div className="mt-12 space-y-4">
        <SkeletonBlock className="h-6 w-[72%] rounded-[8px]" />
        <SkeletonBlock className="h-5 w-full rounded-[8px]" />
        <SkeletonBlock className="h-5 w-[90%] rounded-[8px]" />
      </div>
      <div className="mt-6 flex gap-2">
        <SkeletonBlock className="h-8 w-20 rounded-[8px]" />
        <SkeletonBlock className="h-8 w-24 rounded-[8px]" />
        <SkeletonBlock className="h-8 w-24 rounded-[8px]" />
      </div>
      <div className="mt-12 flex items-center justify-between">
        <SkeletonBlock className="h-5 w-28 rounded-[8px]" />
        <SkeletonBlock className="h-6 w-16 rounded-[8px]" />
      </div>
    </div>
  );
}

function NewsItemSkeleton() {
  return (
    <div className="rounded-[12px] bg-white/[0.05] px-4 py-5">
      <SkeletonBlock className="h-6 w-[82%] rounded-[8px]" />
      <SkeletonBlock className="mt-3 h-4 w-24 rounded-[8px]" />
    </div>
  );
}

function formatRelativeTime(value) {
  if (!value) return 'Без даты';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Без даты';
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60000) return 'Только что';
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return `${diffMin} мин назад`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours} ч назад`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} дн назад`;
}

function getArticleTitle(entry) {
  const title = String(entry?.ru_title || '').trim();
  return title || 'Без названия';
}

export default function Home({ currentUser: currentUserProp = null }) {
  const navigate = useNavigate();
  const location = useLocation();
  // Приоритет у данных из Layout, чтобы не ждать дополнительной загрузки пользователя.
  const outletContext = useOutletContext();
  const currentUser = outletContext?.currentUser || currentUserProp;
  const initialKnowledgeFeed = useMemo(() => readKnowledgeFeedCache(), []);
  const initialLeaderboardStats = useMemo(() => readLeaderboardStatsCache(), []);
  const hasCachedKnowledge = initialKnowledgeFeed.length > 0;
  const hasCachedLeaderboardStats = Boolean(initialLeaderboardStats);
  const [profile, setProfile] = useState(currentUser);
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [showFeedbackCard, setShowFeedbackCard] = useState(true);
  const [homeMode, setHomeMode] = useState(!currentUser ? 'education' : 'championship');
  const [knowledgeItems, setKnowledgeItems] = useState(initialKnowledgeFeed);
  const [knowledgeLoading, setKnowledgeLoading] = useState(initialKnowledgeFeed.length === 0);
  const [knowledgeError, setKnowledgeError] = useState('');
  const [trainingTab, setTrainingTab] = useState('practice');
  const [practiceTrainingItems, setPracticeTrainingItems] = useState([]);
  const [practiceLoading, setPracticeLoading] = useState(true);
  const [practiceError, setPracticeError] = useState('');
  const [latestTasks, setLatestTasks] = useState([]);
  const [latestTasksLoading, setLatestTasksLoading] = useState(true);
  const [latestTasksError, setLatestTasksError] = useState('');
  const [activeOnboardingStep, setActiveOnboardingStep] = useState(null);
  const [onboardingSaving, setOnboardingSaving] = useState(false);
  const [leaderboardStats, setLeaderboardStats] = useState(
    initialLeaderboardStats || {
      contest: null,
      practice: null,
    }
  );
  const [leaderboardStatsLoading, setLeaderboardStatsLoading] = useState(!hasCachedLeaderboardStats);
  const autoOnboardingStartedRef = useRef(false);
  const isAdmin = profile?.role === 'admin';
  const onboardingStatus = profile?.onboarding_status ?? null;

  useEffect(() => {
    if (currentUser) {
      setProfile(currentUser);
    }
  }, [currentUser]);

  useEffect(() => {
    const handleProfileUpdated = (event) => {
      if (event?.detail) {
        setProfile((prev) => ({ ...(prev || {}), ...event.detail }));
      }
    };

    window.addEventListener('profile-updated', handleProfileUpdated);
    return () => {
      window.removeEventListener('profile-updated', handleProfileUpdated);
    };
  }, []);

  useEffect(() => {
    if (!profile) return;
    const params = new URLSearchParams(location.search);
    if (!params.has('onboarding')) return;

    setActiveOnboardingStep(0);
    autoOnboardingStartedRef.current = true;
    navigate(location.pathname, { replace: true });
  }, [location.pathname, location.search, navigate, profile]);

  useEffect(() => {
    if (autoOnboardingStartedRef.current) return;
    if (!profile || isAdmin) return;
    if (onboardingStatus !== 'pending') return;

    setActiveOnboardingStep(0);
    autoOnboardingStartedRef.current = true;
  }, [isAdmin, onboardingStatus, profile]);

  const dispatchProfileUpdated = (detail) => {
    window.dispatchEvent(new CustomEvent('profile-updated', { detail }));
  };

  const persistOnboardingStatus = async (statusValue) => {
    if (isAdmin) return;
    setOnboardingSaving(true);
    try {
      const updatedProfile = await profileAPI.updateOnboardingStatus(statusValue);
      setProfile((prev) => ({ ...(prev || {}), ...updatedProfile }));
      dispatchProfileUpdated(updatedProfile);
    } catch (error) {
      console.error('Не удалось обновить статус онбординга', error);
      setProfile((prev) => (prev ? { ...prev, onboarding_status: statusValue } : prev));
      dispatchProfileUpdated({ onboarding_status: statusValue });
    } finally {
      setOnboardingSaving(false);
    }
  };

  const handleOnboardingClose = async () => {
    if (onboardingSaving) return;
    setActiveOnboardingStep(null);
    await persistOnboardingStatus('dismissed');
  };

  const handleOnboardingNext = () => {
    if (onboardingSaving) return;
    setActiveOnboardingStep((prev) => {
      if (prev == null) return 0;
      return Math.min(prev + 1, ONBOARDING_STEPS_COUNT - 1);
    });
  };

  const handleOnboardingFinish = async () => {
    if (onboardingSaving) return;
    setActiveOnboardingStep(null);
    await persistOnboardingStatus('completed');
  };

  useEffect(() => {
    let isMounted = true;
    if (hasCachedKnowledge) {
      setKnowledgeLoading(false);
      return () => {
        isMounted = false;
      };
    }

    const fetchKnowledge = async () => {
      if (isMounted) {
        setKnowledgeLoading(true);
      }
      try {
        setKnowledgeError('');
        const data = await knowledgeAPI.getFeed({ limit: 3 });
        if (isMounted) {
          const items = Array.isArray(data) ? data : [];
          setKnowledgeItems(items);
          writeKnowledgeFeedCache(items);
        }
      } catch (error) {
        console.error('Не удалось загрузить статьи базы знаний', error);
        if (isMounted) {
          if (error?.response?.status === 401 && !authAPI.isAuthenticated()) {
            setKnowledgeItems([]);
          } else {
            const detail = error?.response?.data?.detail;
            setKnowledgeError(typeof detail === 'string' ? detail : 'Не удалось загрузить статьи');
            setKnowledgeItems([]);
          }
        }
      } finally {
        if (isMounted) {
          setKnowledgeLoading(false);
        }
      }
    };

    fetchKnowledge();

    return () => {
      isMounted = false;
    };
  }, [hasCachedKnowledge]);

  useEffect(() => {
    let isMounted = true;

    const fetchPracticeTasks = async () => {
      try {
        setPracticeError('');
        setLatestTasksError('');
        // Одна загрузка покрывает и "Практику", и "Новые задания", чтобы не дергать API дважды.
        const response = await educationAPI.getPracticeTasks({
          limit: 6,
          offset: 0,
          include_total: false,
          include_categories: false,
        });
        const items = Array.isArray(response?.items) ? response.items : [];
        const sorted = [...items].sort((a, b) => {
          const left = getPracticePriority(a);
          const right = getPracticePriority(b);
          if (left !== right) return left - right;
          return (Number(b?.points) || 0) - (Number(a?.points) || 0);
        });
        if (isMounted) {
          setPracticeTrainingItems(sorted);
          setLatestTasks(items.slice(0, 3));
        }
      } catch (error) {
        console.error('Не удалось загрузить практические задачи для главной страницы', error);
        if (isMounted) {
          if (error?.response?.status === 401 && !authAPI.isAuthenticated()) {
            setPracticeTrainingItems([]);
            setLatestTasks([]);
          } else {
            const detail = error?.response?.data?.detail;
            setPracticeError(typeof detail === 'string' ? detail : 'Не удалось загрузить практические задачи');
            setPracticeTrainingItems([]);
            setLatestTasksError(typeof detail === 'string' ? detail : 'Не удалось загрузить новые задачи');
            setLatestTasks([]);
          }
        }
      } finally {
        if (isMounted) {
          setPracticeLoading(false);
          setLatestTasksLoading(false);
        }
      }
    };

    fetchPracticeTasks();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    const fetchLeaderboardStats = async () => {
      try {
        if (!hasCachedLeaderboardStats) {
          setLeaderboardStatsLoading(true);
        }
        const stats = await ratingsAPI.getMyStatsBundle();

        if (!isMounted) return;

        const normalizedStats = {
          contest: {
            rank: toSafeNumber(stats?.contest?.rank, null),
            points: toSafeNumber(stats?.contest?.rating, 0),
            firstBlood: toSafeNumber(stats?.contest?.first_blood, 0),
          },
          practice: {
            rank: toSafeNumber(stats?.practice?.rank, null),
            points: toSafeNumber(stats?.practice?.rating, 0),
            firstBlood: toSafeNumber(stats?.practice?.first_blood, 0),
          },
        };
        setLeaderboardStats(normalizedStats);
        writeLeaderboardStatsCache(normalizedStats);
      } catch (error) {
        if (isMounted) {
          console.error('Не удалось загрузить статистику рейтинга для главной страницы', error);
        }
      } finally {
        if (isMounted) {
          setLeaderboardStatsLoading(false);
        }
      }
    };

    fetchLeaderboardStats();

    return () => {
      isMounted = false;
    };
  }, [hasCachedLeaderboardStats]);

  const inProgressTasks = useMemo(
    () => practiceTrainingItems.filter((t) => t.my_status === 'in_progress'),
    [practiceTrainingItems]
  );

  const modeStats = homeMode === 'championship'
    ? {
      rank: leaderboardStats.contest?.rank,
      points: leaderboardStats.contest?.points ?? toSafeNumber(profile?.contest_rating, 0),
      firstBlood: leaderboardStats.contest?.firstBlood ?? toSafeNumber(profile?.first_blood, 0),
      targetPath: '/championship',
      targetLabel: 'Перейти к чемпионату',
    }
    : {
      rank: leaderboardStats.practice?.rank,
      points: leaderboardStats.practice?.points ?? toSafeNumber(profile?.practice_rating, 0),
      firstBlood: leaderboardStats.practice?.firstBlood ?? toSafeNumber(profile?.first_blood, 0),
      targetPath: '/education',
      targetLabel: 'Перейти к обучению',
    };

  const rankValue = modeStats.rank ?? (leaderboardStatsLoading ? '...' : '—');
  const stats = [
    { label: 'Рейтинг', value: rankValue },
    { label: 'Очки', value: modeStats.points },
    { label: 'First blood', value: modeStats.firstBlood },
  ];
  const practiceGridClassName = 'grid grid-cols-3 gap-4 w-full';

  return (
    <div className="font-sans-figma text-white">
      <FeedbackModal open={isFeedbackOpen} onClose={() => setIsFeedbackOpen(false)} />
      {activeOnboardingStep != null && (
        <HomeOnboardingOverlay
          stepIndex={activeOnboardingStep}
          onClose={handleOnboardingClose}
          onNext={handleOnboardingNext}
          onFinish={handleOnboardingFinish}
        />
      )}
      <section
        data-onboarding-target="home-hero"
        className="rounded-[20px] px-4 pb-6 pt-8 sm:px-6"
        style={{
          backgroundImage:
            'linear-gradient(80.61639898439296deg, rgb(86, 59, 166) 1.2823%, rgb(87, 56, 158) 15.301%, rgb(89, 60, 158) 35.395%, rgb(131, 89, 221) 62.966%, rgb(159, 99, 255) 98.48%)',
        }}
      >
        <div className="flex flex-col gap-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="text-[30px] leading-[36px] tracking-[0.72px] font-medium sm:text-[36px] sm:leading-[44px]">
                Привет, {profile?.username || DEFAULT_USERNAME}!
              </h1>
              <p className="mt-4 text-[18px] leading-[22px] tracking-[0.4px] text-white/60 sm:text-[20px] sm:leading-[24px]">
                Подготовили твои результаты на сегодняшний день
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setHomeMode('championship')}
                className={`rounded-[10px] border px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] ${
                  homeMode === 'championship'
                    ? 'bg-white/10 border-white/10 text-white/90'
                    : 'bg-white/5 border-white/10 text-white/60'
                }`}
              >
                Чемпионат
              </button>
              <button
                onClick={() => setHomeMode('education')}
                className={`rounded-[10px] border px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] ${
                  homeMode === 'education'
                    ? 'bg-white/10 border-white/10 text-white/90'
                    : 'bg-white/5 border-white/10 text-white/60'
                }`}
              >
                Обучение
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2 lg:flex-row lg:gap-2">
              {stats.map((item) => (
                <ScoreCard key={item.label} label={item.label} value={item.value} loading={leaderboardStatsLoading} />
              ))}
            </div>
            <button
              onClick={() => navigate(modeStats.targetPath)}
              className="flex items-center gap-2 text-[18px] leading-[24px] tracking-[0.72px] text-white/90"
            >
              {modeStats.targetLabel}
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 5l6 7-6 7" />
              </svg>
            </button>
          </div>
        </div>
      </section>

      <section className="mt-8 flex flex-col gap-4 xl:flex-row">
        <div className="flex-1 flex flex-col gap-4 min-w-0">
          <div data-onboarding-target="home-training" className="bg-white/[0.03] rounded-[20px] px-6 pt-8 pb-6">
            <div className="flex flex-col gap-8">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <h2 className="text-[24px] leading-[30px] tracking-[0.58px] font-medium sm:text-[29px] sm:leading-[36px]">
                  Обучение под мои интересы
                </h2>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => setTrainingTab('theory')}
                    className={`rounded-[10px] px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] border ${
                      trainingTab === 'theory'
                        ? 'bg-white/10 border-white/10 text-[#9B6BFF]'
                        : 'bg-white/5 border-white/10 text-white/60'
                    }`}
                  >
                    Теория
                  </button>
                  <button
                    onClick={() => setTrainingTab('practice')}
                    className={`rounded-[10px] px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] border ${
                      trainingTab === 'practice'
                        ? 'bg-white/10 border-white/10 text-[#9B6BFF]'
                        : 'bg-white/5 border-white/10 text-white/60'
                    }`}
                  >
                    Практика
                  </button>
                </div>
              </div>
              <div>
                {trainingTab === 'theory' && (
                  <div className="grid grid-cols-3 gap-4 w-full">
                    {trainingCards.map((card, index) => (
                      <TrainingCard key={`${card.title}-${index}`} {...card} />
                    ))}
                  </div>
                )}
                {trainingTab === 'practice' && practiceLoading && (
                  <div className={practiceGridClassName}>
                    {Array.from({ length: 3 }).map((_, index) => (
                      <PracticeTrainingCardSkeleton key={`practice-training-skeleton-${index}`} />
                    ))}
                  </div>
                )}
                {trainingTab === 'practice' && !practiceLoading && practiceError && (
                  <div className="text-rose-300 text-[16px]">{practiceError}</div>
                )}
                {trainingTab === 'practice' && !practiceLoading && !practiceError && practiceTrainingItems.length === 0 && (
                  <div className="text-white/60 text-[16px]">Подходящих практических задач пока нет.</div>
                )}
                {trainingTab === 'practice' && !practiceLoading && !practiceError && (
                  <div className={practiceGridClassName}>
                    {practiceTrainingItems.slice(0, 3).map((task) => (
                      <PracticeTrainingCard key={task.id} task={task} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="bg-white/[0.03] rounded-[20px] px-6 pt-8 pb-6">
            <div className="flex flex-col gap-8">
              <h2 className="text-[24px] leading-[30px] tracking-[0.58px] font-medium sm:text-[29px] sm:leading-[36px]">
                Задания в процессе
              </h2>
              {practiceLoading && (
                <div className="flex flex-col gap-2">
                  {Array.from({ length: 2 }).map((_, i) => (
                    <div key={i} className="rounded-[12px] border border-white/[0.06] bg-white/[0.03] px-6 py-6">
                      <SkeletonBlock className="h-6 w-[60%] rounded-[8px]" />
                      <div className="mt-4 flex gap-2">
                        <SkeletonBlock className="h-7 w-20 rounded-[8px]" />
                        <SkeletonBlock className="h-7 w-16 rounded-[8px]" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {!practiceLoading && inProgressTasks.length === 0 && (
                <div className="flex flex-col items-center gap-6 py-10 text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-[20px] bg-[#9B6BFF]/10 border border-[#9B6BFF]/20">
                    <AppIcon name="flag" className="h-7 w-7 text-[#9B6BFF]/70" />
                  </div>
                  <div>
                    <div className="text-[18px] leading-[24px] tracking-[0.4px] text-white/80">
                      Нет начатых заданий
                    </div>
                    <div className="mt-2 text-[15px] leading-[20px] text-white/40">
                      Перейди в раздел Обучение и начни решать задачи
                    </div>
                  </div>
                  <Link
                    to="/education"
                    className="rounded-[10px] bg-[#9B6BFF]/20 border border-[#9B6BFF]/30 px-5 py-3 text-[16px] leading-[20px] text-[#C4A3FF] transition hover:bg-[#9B6BFF]/30"
                  >
                    Перейти к обучению
                  </Link>
                </div>
              )}
              {!practiceLoading && inProgressTasks.length > 0 && (
                <div className="flex flex-col gap-2">
                  {inProgressTasks.map((task) => (
                    <Link
                      key={task.id}
                      to={`/education/${task.id}`}
                      className="group backdrop-blur-[16px] border border-white/[0.14] rounded-[12px] px-[25px] py-[24px] bg-white/[0.02] transition hover:border-[#9B6BFF]/40"
                    >
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-3">
                            <h4 className="text-[18px] leading-[24px] tracking-[0.72px] text-white truncate">
                              {task.title}
                            </h4>
                            <span className="rounded-[8px] border border-[#8E51FF]/30 bg-[#8E51FF]/10 px-3 py-[6px] text-[14px] leading-[20px] text-[#A684FF]">
                              {task.category}
                            </span>
                            <span className={`rounded-[8px] border px-3 py-[6px] text-[14px] leading-[20px] ${practiceDifficultyBadgeClasses[task.difficulty_label] || practiceDifficultyBadgeClasses.Средне}`}>
                              {task.difficulty_label}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-5">
                          <div className="flex items-center gap-2">
                            <AppIcon name="star" className="w-5 h-5 text-white/80" />
                            <span className="font-mono-figma text-[18px] leading-[24px] tracking-[0.36px] text-white">
                              {task.points}
                            </span>
                          </div>
                          <div className="w-12 h-12 rounded-[10px] bg-white/5 border border-white/10 flex items-center justify-center">
                            <svg className="w-5 h-5 text-white/80" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M8 5l8 7-8 7" />
                            </svg>
                          </div>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="bg-white/[0.03] rounded-[20px] px-6 pt-8 pb-6">
            <h2 className="text-[24px] leading-[30px] tracking-[0.58px] font-medium sm:text-[29px] sm:leading-[36px]">
              % пройденных областей знаний
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-8">
              {knowledgeAreas.map((area) => (
                <KnowledgeCard key={area} title={area} />
              ))}
            </div>
          </div>
        </div>

        <aside className="w-full xl:w-[440px] flex flex-col gap-4">
          <div data-onboarding-target="home-first-task">
            <TrainingNotificationCard />
          </div>
          {showFeedbackCard && (
            <FeedbackCard
              onOpen={() => setIsFeedbackOpen(true)}
              onClose={() => setShowFeedbackCard(false)}
            />
          )}

          <div className="bg-white/[0.03] rounded-[20px] px-6 pt-8 pb-6 flex flex-col gap-12">
            <div className="px-4 text-[24px] leading-[30px] tracking-[0.58px] text-white sm:text-[29px] sm:leading-[36px]">
              Новости
            </div>

            <NewsCard title="База знаний" icon={<AppIcon name="doc" className="w-7 h-7" />}>
              {knowledgeError && (
                <NewsItem title={knowledgeError} meta="" />
              )}
              {knowledgeLoading && (
                <>
                  {Array.from({ length: 3 }).map((_, index) => (
                    <NewsItemSkeleton key={`knowledge-news-skeleton-${index}`} />
                  ))}
                </>
              )}
              {!knowledgeLoading && !knowledgeError && knowledgeItems.length === 0 && (
                <NewsItem title="Пока нет статей" meta="" />
              )}
              {!knowledgeLoading && !knowledgeError && knowledgeItems.length > 0 && knowledgeItems.map((item) => (
                <NewsItem
                  key={item.id}
                  title={getArticleTitle(item)}
                  meta={formatRelativeTime(item.created_at)}
                  to={item?.id ? `/knowledge/${item.id}` : undefined}
                />
              ))}
            </NewsCard>

            <NewsCard title="Новые задания" icon={<AppIcon name="flag" className="w-7 h-7" />}>
              {latestTasksError && (
                <NewsItem title={latestTasksError} meta="" />
              )}
              {latestTasksLoading && (
                <>
                  {Array.from({ length: 3 }).map((_, index) => (
                    <NewsItemSkeleton key={`latest-tasks-skeleton-${index}`} />
                  ))}
                </>
              )}
              {!latestTasksLoading && !latestTasksError && latestTasks.length === 0 && (
                <NewsItem title="Пока нет новых задач" meta="" />
              )}
              {!latestTasksLoading && !latestTasksError && latestTasks.map((task) => (
                <TaskNewsItem key={task.id} task={task} />
              ))}
            </NewsCard>
          </div>
        </aside>
      </section>
    </div>
  );
}
