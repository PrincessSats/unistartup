import React from 'react';

const cardBase = 'bg-white/[0.05] border border-white/[0.08] rounded-[18px]';

function SectionCard({ title, subtitle, action, children }) {
  return (
    <div className={`${cardBase} p-6 flex flex-col gap-4`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[18px] leading-[22px] tracking-[0.02em] text-white">
            {title}
          </div>
          {subtitle && (
            <div className="text-[14px] text-white/50 mt-1">
              {subtitle}
            </div>
          )}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

export default SectionCard;
