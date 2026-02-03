import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { profileAPI } from '../services/api';

const assets = {
  trainingWeb: 'https://www.figma.com/api/mcp/asset/fc4f12da-20d3-4566-8900-ff0041cc9699',
  trainingForensics: 'https://www.figma.com/api/mcp/asset/e3408f5c-e06c-4501-874e-3db6c3891edb',
  trainingPm: 'https://www.figma.com/api/mcp/asset/1c4915f0-cdae-45d9-84a2-f5336378d0a6',
  star: 'https://www.figma.com/api/mcp/asset/64b5abbd-9674-4865-a192-72c48eff21c5',
  doc: 'https://www.figma.com/api/mcp/asset/ead9f752-c620-46c6-9f49-9cdab79979ff',
  flag: 'https://www.figma.com/api/mcp/asset/e681f1f0-b79c-4f59-a588-7982a4b22e4e',
  close: 'https://www.figma.com/api/mcp/asset/144edf45-ec18-443a-94d3-98858cb6a783',
};

const DEFAULT_USERNAME = 'Пользователь';

const trainingCards = [
  {
    image: assets.trainingWeb,
    title: 'Основы шифрования RSA',
    description: 'Изучи основы криптографии RSA и безопасного обмена ключами шифрования',
    tags: ['Веб', 'Среднее'],
    duration: '45 мин',
    progress: 67,
    points: 450,
  },
  {
    image: assets.trainingForensics,
    title: 'Основы шифрования RSA',
    description: 'Изучи основы криптографии RSA и безопасного обмена ключами шифрования',
    tags: ['Форензика', 'Сложно'],
    duration: '45 мин',
    progress: 67,
    points: 450,
  },
  {
    image: assets.trainingPm,
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

const knowledgeNews = [
  'Новое руководство: продвинутые методы переполнения буфера',
  'Новое руководство: продвинутые методы переполнения буфера',
  'Новое руководство: продвинутые методы переполнения буфера',
];

const taskNews = [
  'Новое руководство: продвинутые методы переполнения буфера',
  'Новое руководство: продвинутые методы переполнения буфера',
  'Новое руководство: продвинутые методы переполнения буфера',
];

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

function TrainingCard({ image, title, description, tags, duration, progress, points }) {
  const difficultyTone = tags[1] === 'Легко' ? 'easy' : tags[1] === 'Среднее' ? 'medium' : 'hard';

  return (
    <div className="bg-white/[0.05] rounded-[12px] p-6 flex flex-col gap-6 w-full md:w-[352px]">
      <div className="h-[173px] w-[304px] max-w-full relative overflow-hidden mx-auto">
        <img
          src={image}
          alt=""
          className="absolute inset-0 w-full h-full object-contain"
        />
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
          <img src={assets.star} alt="" className="w-5 h-5" />
          <span className="font-mono-figma text-[18px] leading-[24px] tracking-[0.36px] text-white">
            {points}
          </span>
        </div>
      </div>
    </div>
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
            <img src={assets.star} alt="" className="w-5 h-5" />
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

function NotificationCard() {
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
        <img src={assets.close} alt="" className="w-[22px] h-[22px]" />
      </div>
      <button className="bg-[#9B6BFF] rounded-[10px] px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] text-white w-fit">
        Пройти
      </button>
    </div>
  );
}

function NewsCard({ title, children, icon }) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3 px-4">
        <img src={icon} alt="" className="w-7 h-7" />
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

function NewsItem({ title, meta }) {
  return (
    <div className="bg-white/[0.05] rounded-[12px] px-4 py-5">
      <div className="text-[18px] leading-[24px] tracking-[0.72px] text-white truncate">
        {title}
      </div>
      {meta ? (
        <div className="text-[14px] leading-[20px] tracking-[0.64px] text-white/50 mt-2">
          {meta}
        </div>
      ) : null}
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

export default function Home() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);

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

  const stats = [
    { label: 'Рейтинг', value: profile?.contest_rating ?? 0 },
    { label: 'Очки', value: profile?.practice_rating ?? 0 },
    { label: 'First blood', value: profile?.first_blood ?? 0 },
  ];

  return (
    <div className="font-sans-figma text-white">
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
                  <button className="bg-white/10 border border-white/10 rounded-[10px] px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] text-[#9B6BFF]">
                    Теория
                  </button>
                  <button className="bg-white/5 border border-white/10 rounded-[10px] px-5 py-4 text-[18px] leading-[24px] tracking-[0.72px] text-white/60">
                    Практика
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap gap-4">
                {trainingCards.map((card, index) => (
                  <TrainingCard key={`${card.title}-${index}`} {...card} />
                ))}
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
          <NotificationCard />
          <NotificationCard />

          <div className="bg-white/[0.03] rounded-[20px] px-6 pt-8 pb-6 flex flex-col gap-12">
            <div className="text-[29px] leading-[36px] tracking-[0.58px] text-white px-4">
              Новости
            </div>

            <NewsCard title="База знаний" icon={assets.doc}>
              {knowledgeNews.map((item, index) => (
                <NewsItem key={`${item}-${index}`} title={item} meta="45 мин назад" />
              ))}
            </NewsCard>

            <NewsCard title="Новые задания" icon={assets.flag}>
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
