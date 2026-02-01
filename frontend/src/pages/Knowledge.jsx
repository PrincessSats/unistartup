import React from 'react';

const sortTabs = [
  { label: 'Сначала новые', active: true },
  { label: 'Сначала старые', active: false },
];

const cards = [
  {
    title: 'Хакки 2025: эволюция атак и новые рубежи киберзащиты',
    description: 'Анализ современных методов взлома и стратегии противодействия для корпоративных систем',
    image: '/kb/kb-img-1.png',
    imageBg: '#5B3CA8',
    tag: 'Web',
    time: '5 мин',
    views: '56',
    date: '26 дек 2025',
  },
  {
    title: 'Решения Чемпионата от 10.12.2025',
    description: 'Разбор ключевых подходов, ошибок и лучших решений сезона',
    image: '/kb/kb-img-2.png',
    imageBg: '#5865C8',
    tag: 'Pentest Machine',
    time: '12 мин',
    views: '48',
    date: '16 дек 2025',
  },
  {
    title: 'Хакки 2025: эволюция атак и новые рубежи киберзащиты',
    description: 'Анализ современных методов взлома и стратегии противодействия для корпоративных систем',
    image: '/kb/kb-img-3.png',
    imageBg: '#3A2A5A',
    tag: 'OSINT',
    time: '5 мин',
    views: '40',
    date: '26 дек 2025',
  },
  {
    title: 'Хакки 2025: эволюция атак и новые рубежи киберзащиты',
    description: 'Анализ современных методов взлома и стратегии противодействия для корпоративных систем',
    image: '/kb/kb-img-8.png',
    imageBg: '#1B1B24',
    tag: 'PWN',
    time: '5 мин',
    views: '32',
    date: '26 дек 2025',
  },
  {
    title: 'Хакки 2025: эволюция атак и новые рубежи киберзащиты',
    description: 'Анализ современных методов взлома и стратегии противодействия для корпоративных систем',
    image: '/kb/kb-img-4.png',
    imageBg: '#2B2B3A',
    tag: 'Реверс-инжиниринг',
    time: '5 мин',
    views: '44',
    date: '20 дек 2025',
  },
  {
    title: 'Решения Чемпионата от 10.12.2025',
    description: 'Подборка результатов и практики применения флагов',
    image: '/kb/kb-img-5.png',
    imageBg: '#5F6ADB',
    tag: 'Стеганография',
    time: '5 мин',
    views: '51',
    date: '16 дек 2025',
  },
  {
    title: 'Решения Чемпионата от 10.12.2025',
    description: 'Разбор ключевых задач и стратегия лидеров',
    image: '/kb/kb-img-6.png',
    imageBg: '#2C367F',
    tag: 'Pentest Machine',
    time: '5 мин',
    views: '28',
    date: '16 дек 2025',
  },
  {
    title: 'Хакки 2025: эволюция атак и новые рубежи киберзащиты',
    description: 'Анализ современных методов взлома и стратегии противодействия для корпоративных систем',
    image: '/kb/kb-img-7.png',
    imageBg: '#4E7C19',
    tag: 'Форензика',
    time: '5 мин',
    views: '38',
    date: '26 дек 2025',
  },
  {
    title: 'Хакки 2025: эволюция атак и новые рубежи киберзащиты',
    description: 'Анализ современных методов взлома и стратегии противодействия для корпоративных систем',
    image: '/kb/kb-img-8.png',
    imageBg: '#5B3CA8',
    tag: 'Криптография',
    time: '5 мин',
    views: '26',
    date: '26 дек 2025',
  },
];

function Knowledge() {
  return (
    <div className="font-sans-figma text-white">
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-[28px] leading-[34px]">База знаний</h1>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 rounded-[12px] border border-white/[0.06] bg-white/[0.02] p-1">
            {sortTabs.map((tab) => (
              <button
                key={tab.label}
                className={`h-9 rounded-[10px] px-4 text-[13px] transition ${
                  tab.active
                    ? 'bg-[#9B6BFF] text-white'
                    : 'text-white/50 hover:text-[#9B6BFF]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <select
                className="h-9 w-[160px] appearance-none rounded-[10px] border border-white/[0.08] bg-[#111118] px-3 pr-8 text-[13px] text-white/70 focus:outline-none focus:border-[#9B6BFF]/70"
                defaultValue=""
              >
                <option value="" disabled>Категория</option>
                <option>Web</option>
                <option>Pwn</option>
                <option>Crypto</option>
                <option>Forensics</option>
              </select>
              <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-white/40">▾</span>
            </div>
            <div className="relative">
              <select
                className="h-9 w-[170px] appearance-none rounded-[10px] border border-white/[0.08] bg-[#111118] px-3 pr-8 text-[13px] text-white/70 focus:outline-none focus:border-[#9B6BFF]/70"
                defaultValue=""
              >
                <option value="" disabled>Тип материала</option>
                <option>Гайд</option>
                <option>Разбор</option>
                <option>Чек-лист</option>
              </select>
              <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-white/40">▾</span>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <article
            key={`${card.title}-${card.tag}-${card.date}`}
            className="rounded-[16px] border border-white/[0.06] bg-[#0F0F14] p-4 transition hover:border-[#9B6BFF]/60"
          >
            <div
              className="flex h-[140px] items-center justify-center rounded-[14px] bg-[#1B1B24]"
              style={{ backgroundColor: card.imageBg }}
            >
              <img src={card.image} alt="" aria-hidden="true" className="h-[120px] w-[160px] object-contain" />
            </div>

            <div className="mt-4 flex items-center justify-between text-[12px] text-white/50">
              <div className="flex items-center gap-3">
                <span className="inline-flex items-center gap-1">
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.458 12C3.732 7.943 7.522 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.478 0-8.268-2.943-9.542-7z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  {card.views}
                </span>
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] text-white/70">
                  {card.tag}
                </span>
                <span>{card.time}</span>
              </div>
              <span>{card.date}</span>
            </div>

            <h3 className="mt-3 text-[16px] leading-[20px]">{card.title}</h3>
            <p className="mt-2 text-[13px] leading-[18px] text-white/50">{card.description}</p>
          </article>
        ))}
      </div>
    </div>
  );
}

export default Knowledge;
