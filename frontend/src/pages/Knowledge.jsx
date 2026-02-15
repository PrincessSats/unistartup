import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { knowledgeAPI } from '../services/api';
import AppIcon from '../components/AppIcon';
import { getKnowledgeCardVisual } from '../utils/knowledgeVisuals';

const sortTabs = [
  { label: 'Сначала новые', value: 'desc' },
  { label: 'Сначала старые', value: 'asc' },
];

const tagGradients = {
  Web: 'linear-gradient(234.59deg, #7177CB 20.12%, #4049C7 100%)',
  OSINT: 'linear-gradient(234.59deg, #5B3CA8 20.12%, #2B2B3A 100%)',
  Криптография: 'linear-gradient(234.59deg, #6B4AC9 20.12%, #2C367F 100%)',
  Форензика: 'linear-gradient(234.59deg, #4E7C19 20.12%, #1B1B24 100%)',
  default: 'linear-gradient(234.59deg, #7177CB 20.12%, #4049C7 100%)',
};

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' });
}

function estimateReadTime(text) {
  if (!text) return 3;
  const words = text.trim().split(/\s+/).length;
  return Math.max(1, Math.round(words / 160));
}

function shortSummary(text) {
  if (!text) return '';
  const sentences = text
    .replace(/\s+/g, ' ')
    .split(/(?<=[.!?])\s+/)
    .filter(Boolean);
  return sentences.slice(0, 2).join(' ');
}

function getEntryTitle(entry) {
  return entry?.ru_title || entry?.cve_id || entry?.source_id || 'Без названия';
}

function KnowledgeCard({ entry }) {
  const tags = Array.isArray(entry?.tags) ? entry.tags : [];
  const primaryTag = tags[0];
  const secondaryTag = tags[1];
  const gradient = tagGradients[primaryTag] || tagGradients.default;
  const visual = getKnowledgeCardVisual(tags, entry?.id || 0);
  const readTime = estimateReadTime(entry?.ru_explainer || entry?.ru_summary);
  const summary = shortSummary(entry?.ru_summary || entry?.ru_explainer || '');

  return (
    <Link
      to={`/knowledge/${entry.id}`}
      className="block rounded-[16px] border border-white/[0.06] bg-[#0F0F14] transition hover:border-[#9B6BFF]/60"
    >
      <div
        className="relative h-[268px] overflow-hidden rounded-[16px]"
        style={{ backgroundImage: gradient }}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.18),rgba(255,255,255,0)_58%)]" />
        <img
          src={visual.src}
          alt=""
          loading="lazy"
          className={`pointer-events-none absolute inset-0 h-full w-full object-cover ${visual.imageClassName}`}
        />
      </div>

      <div className="flex flex-col gap-6 px-8 py-6">
        <div className="flex flex-wrap items-center justify-between gap-4 text-[14px] text-white/60">
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <AppIcon name="eye" className="h-3.5 w-3.5" />
              {entry?.views ?? 0}
            </span>
            {primaryTag && (
              <span className="rounded-[10px] border border-[#8E51FF]/30 bg-[#8E51FF]/10 px-[13px] py-[9px] text-[16px] tracking-[0.64px] text-[#A684FF]">
                {primaryTag}
              </span>
            )}
            {secondaryTag && (
              <span className="rounded-[10px] border border-[#8E51FF]/30 bg-[#8E51FF]/10 px-[13px] py-[9px] text-[16px] tracking-[0.64px] text-[#A684FF]">
                {secondaryTag}
              </span>
            )}
            <span className="text-white/50">{readTime} мин</span>
          </div>
          <span className="text-white/50">{formatDate(entry?.created_at)}</span>
        </div>

        <div className="flex flex-col gap-2">
          <h3 className="text-[20px] leading-[24px] tracking-[0.4px]">
            {getEntryTitle(entry)}
          </h3>
          <p className="text-[16px] leading-[20px] tracking-[0.64px] text-white/60">
            {summary || 'Описание пока не добавлено'}
          </p>
        </div>
      </div>
    </Link>
  );
}

function Knowledge() {
  const [sortOrder, setSortOrder] = useState('desc');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [entries, setEntries] = useState([]);
  const [categories, setCategories] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const limit = 15;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setPage(1);
  }, [sortOrder, categoryFilter]);

  useEffect(() => {
    let isMounted = true;
    const fetchTags = async () => {
      try {
        const data = await knowledgeAPI.getTags({ only_with_title: true });
        if (isMounted) {
          setCategories(Array.isArray(data) ? data : []);
        }
      } catch (error) {
        console.error('Не удалось загрузить теги базы знаний', error);
        if (isMounted) {
          setCategories([]);
        }
      }
    };

    const fetchEntries = async () => {
      if (isMounted) {
        setLoading(true);
      }
      try {
        setError('');
        const data = await knowledgeAPI.getEntriesPaged({
          limit,
          offset: (page - 1) * limit,
          order: sortOrder,
          tag: categoryFilter || undefined,
          only_with_title: true,
        });
        if (isMounted) {
          setEntries(Array.isArray(data?.items) ? data.items : []);
          setTotal(Number.isFinite(data?.total) ? data.total : 0);
        }
      } catch (error) {
        console.error('Не удалось загрузить статьи базы знаний', error);
        const detail = error?.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Не удалось загрузить статьи');
        if (isMounted) {
          setEntries([]);
          setTotal(0);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchTags();
    fetchEntries();

    return () => {
      isMounted = false;
    };
  }, [sortOrder, categoryFilter, page]);

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const pageNumbers = useMemo(() => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, idx) => idx + 1);
    }
    const pages = new Set([1, totalPages, page - 1, page, page + 1]);
    const filtered = Array.from(pages).filter((p) => p >= 1 && p <= totalPages);
    return filtered.sort((a, b) => a - b);
  }, [page, totalPages]);

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
                onClick={() => setSortOrder(tab.value)}
                className={`h-9 rounded-[10px] px-4 text-[13px] transition ${
                  sortOrder === tab.value
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
                value={categoryFilter}
                onChange={(event) => setCategoryFilter(event.target.value)}
              >
                <option value="">Категория</option>
                {categories.map((tag) => (
                  <option key={tag} value={tag}>{tag}</option>
                ))}
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
        {error && (
          <div className="text-rose-300">{error}</div>
        )}
        {loading && (
          <div className="text-white/60">Загрузка статей...</div>
        )}
        {!loading && !error && entries.length === 0 && (
          <div className="text-white/60">Пока нет статей</div>
        )}
        {!loading && !error && entries.map((entry) => (
          <KnowledgeCard key={entry.id} entry={entry} />
        ))}
      </div>

      {!loading && !error && totalPages > 1 && (
        <div className="mt-10 flex flex-wrap items-center justify-center gap-2 text-white">
          <button
            type="button"
            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            disabled={page === 1}
            className="h-9 rounded-[10px] border border-white/10 px-3 text-[13px] text-white/70 hover:text-white disabled:opacity-40"
          >
            Назад
          </button>
          {pageNumbers.map((pageNumber, index) => {
            const prevPage = pageNumbers[index - 1];
            const showGap = prevPage && pageNumber - prevPage > 1;
            return (
              <React.Fragment key={pageNumber}>
                {showGap && <span className="px-2 text-white/40">…</span>}
                <button
                  type="button"
                  onClick={() => setPage(pageNumber)}
                  className={`h-9 rounded-[10px] border px-3 text-[13px] ${
                    pageNumber === page
                      ? 'border-[#9B6BFF] bg-[#9B6BFF]/20 text-white'
                      : 'border-white/10 text-white/70 hover:text-white'
                  }`}
                >
                  {pageNumber}
                </button>
              </React.Fragment>
            );
          })}
          <button
            type="button"
            onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
            disabled={page === totalPages}
            className="h-9 rounded-[10px] border border-white/10 px-3 text-[13px] text-white/70 hover:text-white disabled:opacity-40"
          >
            Вперёд
          </button>
        </div>
      )}
    </div>
  );
}

export default Knowledge;
