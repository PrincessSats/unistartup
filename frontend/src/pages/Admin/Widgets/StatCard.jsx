import React from 'react';

const cardBase = 'bg-white/[0.05] border border-white/[0.08] rounded-[18px]';

function StatCard({ label, value, subValue, subLabel, hint, icon, tone }) {
  return (
    <div className={`${cardBase} p-5 flex flex-col gap-3`}>
      <div className="flex items-center justify-between">
        <span className="text-[12px] uppercase tracking-[0.28em] text-white/40">
          {label}
        </span>
        <span className={`w-9 h-9 rounded-full flex items-center justify-center ${tone}`}>
          {icon}
        </span>
      </div>
      <div className="flex items-baseline gap-2 flex-wrap">
        <div className="text-[28px] leading-[32px] font-mono-figma text-white">
          {value}
        </div>
        {subValue != null && (
          <div
            className="text-[20px] leading-[24px] font-mono-figma text-emerald-400"
            title={subLabel}
          >
            {subValue}
          </div>
        )}
      </div>
      <div className="text-[13px] text-white/50">
        {hint}
      </div>
    </div>
  );
}

export default StatCard;
