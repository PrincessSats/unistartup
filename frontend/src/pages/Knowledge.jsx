import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { knowledgeAPI } from '../services/api';

const sortTabs = [
  { label: 'Сначала новые', value: 'desc' },
  { label: 'Сначала старые', value: 'asc' },
];

const panelGlass = 'https://www.figma.com/api/mcp/asset/3a49cdeb-e88b-4e55-802a-766906beba34';
const eyeIcon = 'https://www.figma.com/api/mcp/asset/a348367d-ce0d-41b5-a110-8518938db3c4';

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

function getEntryTitle(entry) {
  return entry?.ru_title || entry?.cve_id || entry?.source_id || 'Без названия';
}

function KnowledgeCard({ entry }) {
  const tags = Array.isArray(entry?.tags) ? entry.tags : [];
  const primaryTag = tags[0];
  const secondaryTag = tags[1];
  const gradient = tagGradients[primaryTag] || tagGradients.default;
  const readTime = estimateReadTime(entry?.ru_explainer || entry?.ru_summary);

  return (
    <Link
      to={`/knowledge/${entry.id}`}
      className="block rounded-[16px] border border-white/[0.06] bg-[#0F0F14] transition hover:border-[#9B6BFF]/60"
    >
      <div
        className="relative h-[268px] overflow-hidden rounded-[16px]"
        style={{ backgroundImage: gradient }}
      >
        <img
          src={panelGlass}
          alt=""
          aria-hidden="true"
          className="absolute -left-10 top-3 h-[315px] w-[554px] opacity-90"
        />
      </div>

      <div className="flex flex-col gap-6 px-8 py-6">
        <div className="flex flex-wrap items-center justify-between gap-4 text-[14px] text-white/60">
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <img src={eyeIcon} alt="" className="h-3.5 w-3.5" />
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
            {entry?.ru_summary || entry?.ru_explainer || 'Описание пока не добавлено'}
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let isMounted = true;
    const fetchEntries = async () => {
      if (isMounted) {
        setLoading(true);
      }
      try {
        setError('');
        const data = await knowledgeAPI.getEntries({
          limit: 18,
          order: sortOrder,
          tag: categoryFilter || undefined,
        });
        if (isMounted) {
          setEntries(Array.isArray(data) ? data : []);
        }
      } catch (error) {
        console.error('Не удалось загрузить статьи базы знаний', error);
        const detail = error?.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Не удалось загрузить статьи');
        if (isMounted) {
          setEntries([]);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchEntries();

    return () => {
      isMounted = false;
    };
  }, [sortOrder, categoryFilter]);

  const categories = useMemo(() => {
    const unique = new Set();
    entries.forEach((entry) => {
      (entry?.tags || []).forEach((tag) => unique.add(tag));
    });
    return Array.from(unique);
  }, [entries]);

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
    </div>
  );
}

export default Knowledge;
