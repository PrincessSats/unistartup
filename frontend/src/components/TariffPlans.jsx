import React from 'react';

const PLANS = [
  {
    code: 'FREE',
    name: 'Free',
    price: 'Бесплатно',
    features: [
      'Лёгкие и средние задачи',
      'Без генерации задач',
      'Без доступа к Базе Знаний',
    ],
  },
  {
    code: 'PRO',
    name: 'Pro',
    price: 'Промо',
    features: [
      'Все задачи, сложность 1–10',
      '10 генераций задач в месяц',
      'Полный доступ к Базе Знаний',
    ],
  },
  {
    code: 'CORP',
    name: 'Corporate',
    price: 'По запросу',
    features: [
      'Всё из Pro',
      'Командное управление',
      'Корпоративная аналитика',
    ],
    comingSoon: true,
  },
];

function PlanCard({ plan, isCurrent }) {
  const muted = plan.comingSoon;

  return (
    <div
      className={`relative flex flex-col rounded-[18px] border p-8 transition-all duration-300 ${
        isCurrent
          ? 'border-[#9B6BFF]/20 bg-gradient-to-b from-[#9B6BFF]/[0.06] to-transparent'
          : muted
            ? 'border-white/[0.04] bg-white/[0.02]'
            : 'border-white/[0.06] bg-white/[0.03]'
      }`}
    >
      {/* Name + price row */}
      <div className="flex items-baseline justify-between">
        <h4
          className={`text-[23px] leading-[28px] tracking-[0.02em] ${
            muted ? 'text-white/50' : 'text-white'
          }`}
        >
          {plan.name}
        </h4>
        {muted && (
          <span className="text-[13px] leading-[16px] tracking-[0.04em] text-white/30">
            Скоро
          </span>
        )}
      </div>

      <p className="mt-1 text-[16px] leading-[20px] tracking-[0.04em] text-white/40">
        {plan.price}
      </p>

      {/* Divider */}
      <div className="mt-5 h-px bg-white/[0.06]" />

      {/* Features */}
      <ul className="mt-5 flex flex-col gap-3">
        {plan.features.map((feature, idx) => (
          <li
            key={idx}
            className={`text-[15px] leading-[22px] tracking-[0.04em] ${
              muted ? 'text-white/30' : 'text-white/60'
            }`}
          >
            {feature}
          </li>
        ))}
      </ul>

      {/* Status pill — pushed to bottom */}
      <div className="mt-auto pt-6">
        {isCurrent && !muted ? (
          <span className="inline-flex items-center rounded-[8px] bg-[#9B6BFF]/10 px-3 py-1.5 text-[13px] leading-[16px] tracking-[0.04em] text-[#9B6BFF]">
            Активен
          </span>
        ) : (
          <span className="inline-flex items-center rounded-[8px] bg-white/[0.03] px-3 py-1.5 text-[13px] leading-[16px] tracking-[0.04em] text-white/25">
            {muted ? 'Скоро' : 'Неактивен'}
          </span>
        )}
      </div>
    </div>
  );
}

export default function TariffPlans({ currentTariff }) {
  const currentCode = currentTariff?.code || 'FREE';

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-[20px] leading-[24px] tracking-[0.02em] font-medium">
        Тариф
      </h3>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {PLANS.map((plan) => (
          <PlanCard
            key={plan.code}
            plan={plan}
            isCurrent={plan.code === currentCode}
          />
        ))}
      </div>
    </div>
  );
}
