import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { educationAPI, knowledgeAPI, profileAPI } from '../services/api';
import FeedbackModal from '../components/FeedbackModal';
import AppIcon from '../components/AppIcon';
import { TrainingIllustration } from '../components/AppIllustration';
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

const tasks = [
  {
    title: 'Реверс-инжиниринг нестандартного протокола обмена ключами',
    category: 'Реверс-инжиниринг',
    type: 'Теория',
    level: 'Легко',
    progress: 67,
    points: 450,
  },
  {
    title: 'Архитектура адаптивной защиты распределенных систем',
    category: 'Форензика',
    type: 'Практика',
    level: 'Среднее',
    progress: 67,
    points: 450,
  },
  {
    title: 'Атака через небезопасную десериализацию',
    category: 'Веб',
    type: 'Практика',
    level: 'Сложно',
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

const taskNews = [
  'Новое руководство: продвинутые методы переполнения буфера',
  'Новое руководство: продвинутые методы переполнения буфера',
  'Новое руководство: продвинутые методы переполнения буфера',
];

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

function ScoreCard({ label, value }) {
  return (
    <div className="bg-white/[0.09] border border-white/[0.14] rounded-[16px] px-[25px] py-[25px] h-[86px] flex items-center justify-between min-w-[220px] flex-1">
      <span className="text-[18px] leading-[24px] tracking-[0.72px] text-white/60">
        {label}
      </span>
      <span className="font-mono-figma text-[29px] leading-[36px] tracking-[0.58px] text-white">
        {value}
      </span>
    </div>
  );
}

function TrainingCard({ variant, title, description, tags, duration, progress, points, to }) {
  const difficultyTone = tags[1] === 'Легко' ? 'easy' : tags[1] === 'Среднее' || tags[1] === 'Средне' ? 'medium' : 'hard';
  const containerClasses = `bg-white/[0.05] rounded-[12px] p-6 flex flex-col gap-6 w-full md:w-[352px] ${to ? 'transition hover:border hover:border-[#9B6BFF]/50' : ''}`;

  const content = (
    <>
      <div className="h-[173px] w-[304px] max-w-full relative overflow-hidden mx-auto">
        <TrainingIllustration variant={variant || 'web'} className="absolute inset-0 w-full h-full" />
      </div>
      <div className="flex flex-col gap-4">
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
      className="group h-full rounded-[12px] border border-white/[0.06] bg-white/[0.03] p-5 transition hover:border-[#9B6BFF]/60"
    >
      <div className="relative aspect-[16/9] overflow-hidden rounded-[10px] border border-white/[0.06] bg-black/20">
        <img
          src={visual}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
        />
        {isSolved && (
          <span className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-[8px] border border-[#3FD18A]/45 bg-[#3FD18A]/20 px-2.5 py-1 text-[12px] text-[#3FD18A]">
            <AppIcon name="check-circle" className="h-3.5 w-3.5" />
            Решено
          </span>
        )}
      </div>

      <div className="mt-5 flex h-[170px] flex-col justify-between">
        <div>
          <h3 className="line-clamp-2 text-[22px] leading-[1.2] tracking-[0.01em] text-white">
            {task.title}
          </h3>
          <p className="mt-3 line-clamp-2 text-[15px] leading-[20px] tracking-[0.04em] text-white/60">
            {task.summary || 'Описание задачи пока не добавлено'}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="rounded-[10px] border border-white/[0.14] bg-white/[0.05] px-3 py-1.5 text-[12px] text-white/75">
              {task.category}
            </span>
            <span className={`rounded-[10px] border px-3 py-1.5 text-[12px] ${difficultyClass}`}>
              {task.difficulty_label}
            </span>
            <span className="rounded-[10px] border border-white/[0.12] bg-white/[0.04] px-3 py-1.5 text-[12px] text-white/70">
              {statusLabel}
            </span>
          </div>
        </div>
        <div className="mt-4 flex items-center justify-between text-[15px] leading-[20px] tracking-[0.04em] text-white/65">
          <span>{task.passed_users_count} прошли</span>
          <span className="inline-flex items-center gap-2 font-mono-figma text-white">
            <AppIcon name="star" className="h-4 w-4 text-white/80" />
            {task.points}
          </span>
        </div>
      </div>
    </Link>
  );
}

function TaskRow({ title, category, type, level, progress, points }) {
  const levelTone = level === 'Легко' ? 'easy' : level === 'Среднее' ? 'medium' : 'hard';

  return (
    <div className="backdrop-blur-[16px] border border-white/[0.14] rounded-[12px] px-[25px] py-[24px] bg-white/[0.02]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h4 className="text-[18px] leading-[24px] tracking-[0.72px] text-white truncate">
              {title}
            </h4>
            <Tag tone="neutral">{category}</Tag>
            <span className="text-[14px] leading-[20px] tracking-[0.64px] text-white/50">
              {type}
            </span>
            <Tag tone={levelTone}>{level}</Tag>
          </div>
          <div className="mt-4 flex items-center gap-4">
            <div className="flex-1">
              <div className="h-1 rounded-[8px] bg-white/10 overflow-hidden">
                <div className="h-full bg-[#9B6BFF]" style={{ width: `${progress}%` }} />
              </div>
            </div>
            <span className="text-[14px] leading-[20px] tracking-[0.64px] text-white/50">
              {progress}%
            </span>
          </div>
        </div>
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2">
            <AppIcon name="star" className="w-5 h-5 text-white/80" />
            <span className="font-mono-figma text-[18px] leading-[24px] tracking-[0.36px] text-white">
              {points}
            </span>
          </div>
          <button className="w-12 h-12 rounded-[10px] bg-white/5 border border-white/10 flex items-center justify-center">
            <svg className="w-5 h-5 text-white/80" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 5l8 7-8 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
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
      <button className="bg-[#9B6BFF] rounded-[10px] px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] text-white w-fit">
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

function TaskNewsItem({ title }) {
  return (
    <div className="bg-white/[0.05] rounded-[12px] px-4 py-5">
      <div className="text-[18px] leading-[24px] tracking-[0.72px] text-white truncate">
        {title}
      </div>
      <div className="flex items-center gap-4 mt-3">
        <span className="bg-white/5 border border-white/10 rounded-[10px] px-3 py-1.5 text-[14px] leading-[20px] tracking-[0.64px] text-white/70">
          Криптография
        </span>
        <span className="text-[14px] leading-[20px] tracking-[0.64px] text-white/50">
          4 прошли
        </span>
      </div>
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

export default function Home() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [showFeedbackCard, setShowFeedbackCard] = useState(true);
  const [knowledgeItems, setKnowledgeItems] = useState([]);
  const [knowledgeLoading, setKnowledgeLoading] = useState(true);
  const [knowledgeError, setKnowledgeError] = useState('');
  const [trainingTab, setTrainingTab] = useState('theory');
  const [practiceTrainingItems, setPracticeTrainingItems] = useState([]);
  const [practiceLoading, setPracticeLoading] = useState(true);
  const [practiceError, setPracticeError] = useState('');

  useEffect(() => {
    let isMounted = true;

    const fetchProfile = async () => {
      try {
        const data = await profileAPI.getProfile();
        if (isMounted) {
          setProfile(data);
        }
      } catch (error) {
        // Если токен протух — редиректится в Layout, здесь можно молча игнорировать
        console.error('Не удалось загрузить профиль для главной страницы', error);
      }
    };

    fetchProfile();

    const handleProfileUpdated = (event) => {
      if (event?.detail) {
        setProfile((prev) => ({ ...(prev || {}), ...event.detail }));
      }
    };

    window.addEventListener('profile-updated', handleProfileUpdated);

    return () => {
      isMounted = false;
      window.removeEventListener('profile-updated', handleProfileUpdated);
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const fetchKnowledge = async () => {
      try {
        setKnowledgeError('');
        const data = await knowledgeAPI.getEntries({ limit: 3, order: 'desc', only_with_title: true });
        if (isMounted) {
          setKnowledgeItems(Array.isArray(data) ? data : []);
        }
      } catch (error) {
        console.error('Не удалось загрузить статьи базы знаний', error);
        const detail = error?.response?.data?.detail;
        setKnowledgeError(typeof detail === 'string' ? detail : 'Не удалось загрузить статьи');
        if (isMounted) {
          setKnowledgeItems([]);
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
  }, []);

  useEffect(() => {
    let isMounted = true;

    const fetchPracticeTasks = async () => {
      try {
        setPracticeError('');
        const response = await educationAPI.getPracticeTasks({ limit: 100, offset: 0 });
        const items = Array.isArray(response?.items) ? response.items : [];
        const sorted = [...items].sort((a, b) => {
          const left = getPracticePriority(a);
          const right = getPracticePriority(b);
          if (left !== right) return left - right;
          return (Number(b?.points) || 0) - (Number(a?.points) || 0);
        });
        if (isMounted) {
          setPracticeTrainingItems(sorted);
        }
      } catch (error) {
        console.error('Не удалось загрузить практические задачи для главной страницы', error);
        const detail = error?.response?.data?.detail;
        if (isMounted) {
          setPracticeError(typeof detail === 'string' ? detail : 'Не удалось загрузить практические задачи');
          setPracticeTrainingItems([]);
        }
      } finally {
        if (isMounted) {
          setPracticeLoading(false);
        }
      }
    };

    fetchPracticeTasks();

    return () => {
      isMounted = false;
    };
  }, []);

  const stats = [
    { label: 'Рейтинг', value: profile?.contest_rating ?? 0 },
    { label: 'Очки', value: profile?.practice_rating ?? 0 },
    { label: 'First blood', value: profile?.first_blood ?? 0 },
  ];

  return (
    <div className="font-sans-figma text-white">
      <FeedbackModal open={isFeedbackOpen} onClose={() => setIsFeedbackOpen(false)} />
      <section
        className="rounded-[20px] px-6 pt-8 pb-6"
        style={{
          backgroundImage:
            'linear-gradient(80.61639898439296deg, rgb(86, 59, 166) 1.2823%, rgb(87, 56, 158) 15.301%, rgb(89, 60, 158) 35.395%, rgb(131, 89, 221) 62.966%, rgb(159, 99, 255) 98.48%)',
        }}
      >
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="text-[36px] leading-[44px] tracking-[0.72px] font-medium">
                Привет, {profile?.username || DEFAULT_USERNAME}!
              </h1>
              <p className="text-[20px] leading-[24px] tracking-[0.4px] text-white/60 mt-4">
                Подготовили твои результаты на сегодняшний день
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => navigate('/championship')}
                className="bg-white/10 border border-white/10 rounded-[10px] px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] text-white/90"
              >
                Чемпионат
              </button>
              <button
                onClick={() => navigate('/education')}
                className="bg-white/5 border border-white/10 rounded-[10px] px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] text-white/60"
              >
                Обучение
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2 lg:flex-row lg:gap-2">
              {stats.map((item) => (
                <ScoreCard key={item.label} label={item.label} value={item.value} />
              ))}
            </div>
            <button
              onClick={() => navigate('/championship')}
              className="flex items-center gap-2 text-[18px] leading-[24px] tracking-[0.72px] text-white/90"
            >
              Перейти к чемпионату
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 5l6 7-6 7" />
              </svg>
            </button>
          </div>
        </div>
      </section>

      <section className="mt-8 flex flex-col gap-4 xl:flex-row">
        <div className="flex-1 flex flex-col gap-4 min-w-0">
          <div className="bg-white/[0.03] rounded-[20px] px-6 pt-8 pb-6">
            <div className="flex flex-col gap-8">
              <div className="flex items-center justify-between">
                <h2 className="text-[29px] leading-[36px] tracking-[0.58px] font-medium">
                  Обучение под мои интересы
                </h2>
                <div className="flex items-center gap-2">
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
              <div className="flex flex-wrap gap-4">
                {trainingTab === 'theory' && trainingCards.map((card, index) => (
                  <TrainingCard key={`${card.title}-${index}`} {...card} />
                ))}
                {trainingTab === 'practice' && practiceLoading && (
                  <div className="text-white/60 text-[16px]">Загрузка практических задач...</div>
                )}
                {trainingTab === 'practice' && !practiceLoading && practiceError && (
                  <div className="text-rose-300 text-[16px]">{practiceError}</div>
                )}
                {trainingTab === 'practice' && !practiceLoading && !practiceError && practiceTrainingItems.length === 0 && (
                  <div className="text-white/60 text-[16px]">Подходящих практических задач пока нет.</div>
                )}
                {trainingTab === 'practice' && !practiceLoading && !practiceError && (
                  <div className="grid w-full grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3 auto-rows-fr">
                    {practiceTrainingItems.map((task) => (
                      <PracticeTrainingCard key={task.id} task={task} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="bg-white/[0.03] rounded-[20px] px-6 pt-8 pb-6">
            <div className="flex flex-col gap-8">
              <div className="flex items-center justify-between">
                <h2 className="text-[29px] leading-[36px] tracking-[0.58px] font-medium">
                  Задания в процессе
                </h2>
                <div className="flex items-center gap-3">
                  <button className="w-12 h-12 rounded-[10px] bg-white/5 border border-white/10 flex items-center justify-center opacity-40">
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16 5l-8 7 8 7" />
                    </svg>
                  </button>
                  <button className="w-12 h-12 rounded-[10px] bg-white/5 border border-white/10 flex items-center justify-center">
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 5l8 7-8 7" />
                    </svg>
                  </button>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                {tasks.map((task) => (
                  <TaskRow key={task.title} {...task} />
                ))}
              </div>
            </div>
          </div>

          <div className="bg-white/[0.03] rounded-[20px] px-6 pt-8 pb-6">
            <h2 className="text-[29px] leading-[36px] tracking-[0.58px] font-medium">
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
          <TrainingNotificationCard />
          {showFeedbackCard && (
            <FeedbackCard
              onOpen={() => setIsFeedbackOpen(true)}
              onClose={() => setShowFeedbackCard(false)}
            />
          )}

          <div className="bg-white/[0.03] rounded-[20px] px-6 pt-8 pb-6 flex flex-col gap-12">
            <div className="text-[29px] leading-[36px] tracking-[0.58px] text-white px-4">
              Новости
            </div>

            <NewsCard title="База знаний" icon={<AppIcon name="doc" className="w-7 h-7" />}>
              {knowledgeError && (
                <NewsItem title={knowledgeError} meta="" />
              )}
              {knowledgeLoading && (
                <NewsItem title="Загрузка статей..." meta="" />
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
              {taskNews.map((item, index) => (
                <TaskNewsItem key={`${item}-${index}`} title={item} />
              ))}
            </NewsCard>
          </div>
        </aside>
      </section>
    </div>
  );
}
