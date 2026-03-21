import React from 'react';
import { Link } from 'react-router-dom';
import SectionCard from '../Widgets/SectionCard';
import { FileIcon } from '../Widgets/Icons';

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' });
}

function RecentArticleCard({ article }) {
  return (
    <SectionCard
      title="Последняя статья"
      subtitle="Самая свежая запись из базы знаний"
      action={(
        <div className="w-9 h-9 rounded-full bg-white/10 flex items-center justify-center text-white/60">
          <FileIcon className="w-4 h-4" />
        </div>
      )}
    >
      {article && article.id ? (
        <Link
          to={`/knowledge/${article.id}`}
          className="flex flex-col gap-4 rounded-[14px] border border-white/5 bg-white/[0.02] p-4 transition hover:border-[#9B6BFF]/60"
        >
          <div>
            <div className="text-[20px] leading-[26px] text-white">
              {article.ru_title || 'Без названия'}
            </div>
            {article.ru_summary && (
              <div className="text-[14px] text-white/60 mt-2">
                {article.ru_summary}
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-4 text-[13px] text-white/50">
            <span className="uppercase tracking-[0.2em] px-2 py-1 rounded-full bg-white/5 border border-white/10">
              {article.source || 'Источник'}
            </span>
            <span>Дата: {formatDate(article.created_at)}</span>
            {article.cve_id && <span>{article.cve_id}</span>}
          </div>
        </Link>
      ) : article ? (
        <div className="flex flex-col gap-4">
          <div>
            <div className="text-[20px] leading-[26px] text-white">
              {article.ru_title || 'Без названия'}
            </div>
            {article.ru_summary && (
              <div className="text-[14px] text-white/60 mt-2">
                {article.ru_summary}
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-4 text-[13px] text-white/50">
            <span className="uppercase tracking-[0.2em] px-2 py-1 rounded-full bg-white/5 border border-white/10">
              {article.source || 'Источник'}
            </span>
            <span>Дата: {formatDate(article.created_at)}</span>
            {article.cve_id && <span>{article.cve_id}</span>}
          </div>
        </div>
      ) : (
        <div className="text-[14px] text-white/50">
          Пока нет статей
        </div>
      )}
    </SectionCard>
  );
}

export default RecentArticleCard;
