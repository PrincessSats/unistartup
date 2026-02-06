import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminAPI, authAPI } from '../services/api';

const cardBase = 'bg-white/[0.05] border border-white/[0.08] rounded-[18px]';

const UsersIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M16.5 19c0-2.5-2-4.5-4.5-4.5S7.5 16.5 7.5 19" />
    <circle cx="12" cy="8.5" r="3.5" />
    <path d="M20 19c0-2-1.1-3.7-2.8-4.4" />
    <path d="M4 19c0-2 1.1-3.7 2.8-4.4" />
  </svg>
);

const ActivityIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M4 12h4l2.5-5 3 10 2-5h4.5" />
  </svg>
);

const CreditIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <rect x="3" y="6" width="18" height="12" rx="2" />
    <path d="M3 10h18" />
    <path d="M7 15h4" />
  </svg>
);

const TrophyIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M8 5h8v3a4 4 0 0 1-8 0V5Z" />
    <path d="M6 5H4v2a4 4 0 0 0 4 4" />
    <path d="M18 5h2v2a4 4 0 0 1-4 4" />
    <path d="M12 12v4" />
    <path d="M8 20h8" />
  </svg>
);

const MessageIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M5 17l-1 4 4-2h9a4 4 0 0 0 4-4V7a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v10a4 4 0 0 0 2 0Z" />
  </svg>
);

const FileIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
    <path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
    <path d="M14 3v5h5" />
  </svg>
);

function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  if (Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('ru-RU');
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
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

function StatCard({ label, value, hint, icon, tone }) {
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
      <div className="text-[28px] leading-[32px] font-mono-figma text-white">
        {value}
      </div>
      <div className="text-[13px] text-white/50">
        {hint}
      </div>
    </div>
  );
}

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

function KnowledgeBaseModal({ open, onClose, onCreated, onUpdated }) {
  const [tab, setTab] = useState('create');
  const [form, setForm] = useState({
    source: '',
    source_id: '',
    cve_id: '',
    raw_en_text: '',
    ru_title: '',
    ru_summary: '',
    ru_explainer: '',
    tags: '',
    difficulty: '',
  });
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [articles, setArticles] = useState([]);
  const [articlesLoading, setArticlesLoading] = useState(false);
  const [articlesError, setArticlesError] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [editForm, setEditForm] = useState({
    source: '',
    source_id: '',
    cve_id: '',
    raw_en_text: '',
    ru_title: '',
    ru_summary: '',
    ru_explainer: '',
    tags: '',
    difficulty: '',
  });
  const [editStatus, setEditStatus] = useState('idle');
  const [editError, setEditError] = useState('');

  useEffect(() => {
    if (!open) return;
    setTab('create');
    setForm({
      source: '',
      source_id: '',
      cve_id: '',
      raw_en_text: '',
      ru_title: '',
      ru_summary: '',
      ru_explainer: '',
      tags: '',
      difficulty: '',
    });
    setStatus('idle');
    setError('');
    setArticles([]);
    setArticlesLoading(false);
    setArticlesError('');
    setSelectedId(null);
    setEditForm({
      source: '',
      source_id: '',
      cve_id: '',
      raw_en_text: '',
      ru_title: '',
      ru_summary: '',
      ru_explainer: '',
      tags: '',
      difficulty: '',
    });
    setEditStatus('idle');
    setEditError('');
  }, [open]);

  const handleOverlayClick = (event) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  const canSubmit = form.source.trim().length > 0 && status !== 'sending';

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setStatus('sending');
    setError('');
    const tags = form.tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    const difficulty = form.difficulty.trim()
      ? Number.parseInt(form.difficulty, 10)
      : null;

    try {
      const article = await adminAPI.createArticle({
        source: form.source.trim(),
        source_id: form.source_id.trim() || null,
        cve_id: form.cve_id.trim() || null,
        raw_en_text: form.raw_en_text.trim() || null,
        ru_title: form.ru_title.trim() || null,
        ru_summary: form.ru_summary.trim() || null,
        ru_explainer: form.ru_explainer.trim() || null,
        tags,
        difficulty: Number.isNaN(difficulty) ? null : difficulty,
      });
      if (onCreated) {
        onCreated(article);
      }
      onClose();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Не удалось создать статью');
      setStatus('idle');
    }
  };

  const loadArticles = async () => {
    setArticlesLoading(true);
    setArticlesError('');
    try {
      const data = await adminAPI.listArticles({ limit: 200, offset: 0 });
      setArticles(Array.isArray(data) ? data : []);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setArticlesError(typeof detail === 'string' ? detail : 'Не удалось загрузить статьи');
      setArticles([]);
    } finally {
      setArticlesLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    if (tab !== 'edit') return;
    loadArticles();
  }, [open, tab]);

  if (!open) return null;

  const handleSelectArticle = (article) => {
    setSelectedId(article.id);
    setEditForm({
      source: article.source || '',
      source_id: article.source_id || '',
      cve_id: article.cve_id || '',
      raw_en_text: article.raw_en_text || '',
      ru_title: article.ru_title || '',
      ru_summary: article.ru_summary || '',
      ru_explainer: article.ru_explainer || '',
      tags: Array.isArray(article.tags) ? article.tags.join(', ') : '',
      difficulty: article.difficulty !== null && article.difficulty !== undefined ? String(article.difficulty) : '',
    });
    setEditError('');
    setEditStatus('idle');
  };

  const canUpdate = editForm.source.trim().length > 0 && editStatus !== 'saving' && selectedId;

  const handleUpdate = async () => {
    if (!canUpdate) return;
    setEditStatus('saving');
    setEditError('');
    const tags = editForm.tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean);
    const difficulty = editForm.difficulty.trim()
      ? Number.parseInt(editForm.difficulty, 10)
      : null;
    try {
      const updated = await adminAPI.updateArticle(selectedId, {
        source: editForm.source.trim(),
        source_id: editForm.source_id.trim() || null,
        cve_id: editForm.cve_id.trim() || null,
        raw_en_text: editForm.raw_en_text.trim() || null,
        ru_title: editForm.ru_title.trim() || null,
        ru_summary: editForm.ru_summary.trim() || null,
        ru_explainer: editForm.ru_explainer.trim() || null,
        tags,
        difficulty: Number.isNaN(difficulty) ? null : difficulty,
      });
      setArticles((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setEditStatus('idle');
      if (onUpdated) {
        onUpdated(updated);
      }
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setEditError(typeof detail === 'string' ? detail : 'Не удалось сохранить изменения');
      setEditStatus('idle');
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 px-4"
      onClick={handleOverlayClick}
    >
      <div className="bg-[#0B0A10] border border-white/[0.09] rounded-[20px] p-8 w-full max-w-5xl mx-4 font-sans-figma">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h3 className="text-white text-[24px] leading-[32px] font-medium">База знаний</h3>
            <p className="text-white/60 text-[14px] mt-2">
              Управление статьями базы знаний
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-white/60 hover:text-white transition-colors"
          >
            Закрыть
          </button>
        </div>

        <div className="flex items-center gap-3 mb-6">
          <button
            type="button"
            onClick={() => setTab('create')}
            className={`h-9 px-4 rounded-[10px] text-[13px] transition ${
              tab === 'create'
                ? 'bg-[#9B6BFF] text-white'
                : 'border border-white/10 text-white/60 hover:text-white'
            }`}
          >
            Создать статью
          </button>
          <button
            type="button"
            onClick={() => setTab('edit')}
            className={`h-9 px-4 rounded-[10px] text-[13px] transition ${
              tab === 'edit'
                ? 'bg-[#9B6BFF] text-white'
                : 'border border-white/10 text-white/60 hover:text-white'
            }`}
          >
            Изменить статью
          </button>
        </div>

        {tab === 'create' && (
          <>
            {error && (
              <div className="bg-red-500/10 border border-red-500/50 text-red-200 px-4 py-2 rounded-[12px] mb-4 text-sm">
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-white text-sm mb-2 block">Источник *</label>
                <input
                  type="text"
                  value={form.source}
                  onChange={(e) => setForm((prev) => ({ ...prev, source: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                  placeholder="nvd / cve / blog / internal"
                />
              </div>
              <div>
                <label className="text-white text-sm mb-2 block">Source ID</label>
                <input
                  type="text"
                  value={form.source_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, source_id: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                  placeholder="ID в источнике"
                />
              </div>
              <div>
                <label className="text-white text-sm mb-2 block">CVE ID</label>
                <input
                  type="text"
                  value={form.cve_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, cve_id: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                  placeholder="CVE-2024-12345"
                />
              </div>
              <div>
                <label className="text-white text-sm mb-2 block">Сложность</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={form.difficulty}
                  onChange={(e) => setForm((prev) => ({ ...prev, difficulty: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                  placeholder="1-10"
                />
              </div>
            </div>

            <div className="mt-4">
              <label className="text-white text-sm mb-2 block">Заголовок (RU)</label>
              <input
                type="text"
                value={form.ru_title}
                onChange={(e) => setForm((prev) => ({ ...prev, ru_title: e.target.value }))}
                className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                placeholder="Короткий заголовок"
              />
            </div>

            <div className="mt-4">
              <label className="text-white text-sm mb-2 block">Summary (RU)</label>
              <textarea
                value={form.ru_summary}
                onChange={(e) => setForm((prev) => ({ ...prev, ru_summary: e.target.value }))}
                className="w-full min-h-[80px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                placeholder="Краткое описание"
              />
            </div>

            <div className="mt-4">
              <label className="text-white text-sm mb-2 block">Explainer (RU)</label>
              <textarea
                value={form.ru_explainer}
                onChange={(e) => setForm((prev) => ({ ...prev, ru_explainer: e.target.value }))}
                className="w-full min-h-[120px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                placeholder="Развернутое объяснение"
              />
            </div>

            <div className="mt-4">
              <label className="text-white text-sm mb-2 block">Raw EN text</label>
              <textarea
                value={form.raw_en_text}
                onChange={(e) => setForm((prev) => ({ ...prev, raw_en_text: e.target.value }))}
                className="w-full min-h-[120px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                placeholder="Оригинальный текст на английском"
              />
            </div>

            <div className="mt-4">
              <label className="text-white text-sm mb-2 block">Теги</label>
              <input
                type="text"
                value={form.tags}
                onChange={(e) => setForm((prev) => ({ ...prev, tags: e.target.value }))}
                className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                placeholder="web, xss, cve-2024-..."
              />
              <div className="text-white/40 text-xs mt-2">
                Разделяйте теги запятыми
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 h-12 bg-white/[0.03] hover:bg-white/[0.06] text-white rounded-[10px] transition-colors"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="flex-1 h-12 bg-[#9B6BFF] hover:bg-[#8452FF] text-white rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {status === 'sending' ? 'Сохранение...' : 'Создать статью'}
              </button>
            </div>
          </>
        )}

        {tab === 'edit' && (
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
            <div className="border border-white/[0.08] rounded-[16px] p-4 max-h-[560px] overflow-y-auto">
              <div className="text-[14px] text-white/60 mb-3">Список статей</div>
              {articlesLoading && (
                <div className="text-[14px] text-white/40">Загрузка...</div>
              )}
              {articlesError && (
                <div className="text-[14px] text-rose-300">{articlesError}</div>
              )}
              {!articlesLoading && !articlesError && articles.length === 0 && (
                <div className="text-[14px] text-white/40">Статей пока нет</div>
              )}
              <div className="flex flex-col gap-2">
                {articles.map((article) => (
                  <button
                    key={article.id}
                    type="button"
                    onClick={() => handleSelectArticle(article)}
                    className={`text-left rounded-[12px] px-3 py-2 border transition ${
                      selectedId === article.id
                        ? 'border-[#9B6BFF]/60 bg-[#9B6BFF]/10 text-white'
                        : 'border-white/10 bg-white/[0.02] text-white/70 hover:border-[#9B6BFF]/40'
                    }`}
                  >
                    <div className="text-[14px] text-white">
                      {article.ru_title || article.cve_id || `Статья #${article.id}`}
                    </div>
                    <div className="text-[12px] text-white/40 mt-1">
                      {formatDate(article.created_at)}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="border border-white/[0.08] rounded-[16px] p-5">
              {!selectedId ? (
                <div className="text-white/50 text-[14px]">
                  Выберите статью для редактирования
                </div>
              ) : (
                <>
                  {editError && (
                    <div className="bg-red-500/10 border border-red-500/50 text-red-200 px-4 py-2 rounded-[12px] mb-4 text-sm">
                      {editError}
                    </div>
                  )}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-white text-sm mb-2 block">Источник *</label>
                      <input
                        type="text"
                        value={editForm.source}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, source: e.target.value }))}
                        className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                        placeholder="nvd / cve / blog / internal"
                      />
                    </div>
                    <div>
                      <label className="text-white text-sm mb-2 block">Source ID</label>
                      <input
                        type="text"
                        value={editForm.source_id}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, source_id: e.target.value }))}
                        className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                        placeholder="ID в источнике"
                      />
                    </div>
                    <div>
                      <label className="text-white text-sm mb-2 block">CVE ID</label>
                      <input
                        type="text"
                        value={editForm.cve_id}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, cve_id: e.target.value }))}
                        className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                        placeholder="CVE-2024-12345"
                      />
                    </div>
                    <div>
                      <label className="text-white text-sm mb-2 block">Сложность</label>
                      <input
                        type="number"
                        min="1"
                        max="10"
                        value={editForm.difficulty}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, difficulty: e.target.value }))}
                        className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                        placeholder="1-10"
                      />
                    </div>
                  </div>

                  <div className="mt-4">
                    <label className="text-white text-sm mb-2 block">Заголовок (RU)</label>
                    <input
                      type="text"
                      value={editForm.ru_title}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, ru_title: e.target.value }))}
                      className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                      placeholder="Короткий заголовок"
                    />
                  </div>

                  <div className="mt-4">
                    <label className="text-white text-sm mb-2 block">Summary (RU)</label>
                    <textarea
                      value={editForm.ru_summary}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, ru_summary: e.target.value }))}
                      className="w-full min-h-[80px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                      placeholder="Краткое описание"
                    />
                  </div>

                  <div className="mt-4">
                    <label className="text-white text-sm mb-2 block">Explainer (RU)</label>
                    <textarea
                      value={editForm.ru_explainer}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, ru_explainer: e.target.value }))}
                      className="w-full min-h-[120px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                      placeholder="Развернутое объяснение"
                    />
                  </div>

                  <div className="mt-4">
                    <label className="text-white text-sm mb-2 block">Raw EN text</label>
                    <textarea
                      value={editForm.raw_en_text}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, raw_en_text: e.target.value }))}
                      className="w-full min-h-[120px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                      placeholder="Оригинальный текст на английском"
                    />
                  </div>

                  <div className="mt-4">
                    <label className="text-white text-sm mb-2 block">Теги</label>
                    <input
                      type="text"
                      value={editForm.tags}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, tags: e.target.value }))}
                      className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                      placeholder="web, xss, cve-2024-..."
                    />
                    <div className="text-white/40 text-xs mt-2">
                      Разделяйте теги запятыми
                    </div>
                  </div>

                  <div className="flex gap-3 mt-6">
                    <button
                      type="button"
                      onClick={onClose}
                      className="flex-1 h-12 bg-white/[0.03] hover:bg-white/[0.06] text-white rounded-[10px] transition-colors"
                    >
                      Закрыть
                    </button>
                    <button
                      type="button"
                      onClick={handleUpdate}
                      disabled={!canUpdate}
                      className="flex-1 h-12 bg-[#9B6BFF] hover:bg-[#8452FF] text-white rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {editStatus === 'saving' ? 'Сохранение...' : 'Сохранить изменения'}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Admin() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState('');
  const [isKbOpen, setIsKbOpen] = useState(false);
  const [isNvdRunning, setIsNvdRunning] = useState(false);
  const [nvdError, setNvdError] = useState('');

  const loadDashboard = useCallback(async () => {
    try {
      const data = await adminAPI.getDashboard();
      setDashboard(data);
    } catch (err) {
      if (err.response?.status === 401) {
        authAPI.logout();
        navigate('/login');
        return;
      }
      if (err.response?.status === 403) {
        navigate('/home');
        return;
      }
      setError('Не удалось загрузить данные админки');
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const stats = dashboard?.stats || {};
  const contest = dashboard?.current_championship || null;
  const lastArticle = dashboard?.last_article || null;
  const feedbacks = dashboard?.latest_feedbacks || [];
  const nvdSync = dashboard?.nvd_sync || null;

  const contestStatus = useMemo(() => {
    if (!contest) {
      return { label: 'Нет данных', tone: 'bg-white/10 text-white/70' };
    }
    const now = Date.now();
    const start = new Date(contest.start_at).getTime();
    const end = new Date(contest.end_at).getTime();
    if (Number.isNaN(start) || Number.isNaN(end)) {
      return { label: 'Неизвестно', tone: 'bg-white/10 text-white/70' };
    }
    if (now < start) {
      return { label: 'Скоро', tone: 'bg-[#9B6BFF]/20 text-[#CBB6FF]' };
    }
    if (now > end) {
      return { label: 'Завершен', tone: 'bg-white/10 text-white/70' };
    }
    return { label: 'Активен', tone: 'bg-emerald-500/20 text-emerald-300' };
  }, [contest]);

  const paidConversion = stats.total_users
    ? ((stats.paid_users / stats.total_users) * 100).toFixed(1)
    : '0.0';

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] text-white/70">
        Загрузка админки...
      </div>
    );
  }

  const handleFetchNvd = async () => {
    if (isNvdRunning) return;
    setIsNvdRunning(true);
    setNvdError('');
    try {
      const data = await adminAPI.fetchNvd24h();
      setDashboard((prev) => ({
        ...(prev || {}),
        nvd_sync: data,
      }));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setNvdError(typeof detail === 'string' ? detail : 'Не удалось выполнить синхронизацию NVD');
    } finally {
      setIsNvdRunning(false);
    }
  };

  return (
    <div className="font-sans-figma text-white flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[28px] leading-[32px] tracking-[0.02em]">
            Админка
          </h1>
          <p className="text-[16px] leading-[20px] text-white/60 mt-2">
            Сводка по пользователям, чемпионатам и контенту платформы
          </p>
        </div>
        <div className="flex flex-col items-end gap-3">
          <div className="flex flex-wrap items-center justify-end gap-3">
            <div className="flex flex-col items-end gap-1">
              <button
                type="button"
                onClick={handleFetchNvd}
                disabled={isNvdRunning}
                className="h-10 px-4 rounded-[12px] bg-white/10 border border-white/10 text-white/80 text-[14px] tracking-[0.04em] transition-colors duration-200 hover:border-[#9B6BFF]/60 hover:text-white disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isNvdRunning ? 'Fetching...' : 'Fetch NVD 24h'}
              </button>
              <span className="text-[12px] text-white/40">
                Last fetch: {formatDateTime(nvdSync?.last_fetch_at)}
              </span>
            </div>
            <button
              type="button"
              className="h-10 px-4 rounded-[12px] bg-[#9B6BFF] text-white text-[14px] tracking-[0.04em] transition-colors duration-200 hover:bg-[#8452FF]"
            >
              + Создать задачу
            </button>
            <button
              type="button"
              onClick={() => setIsKbOpen(true)}
              className="h-10 px-4 rounded-[12px] border border-[#9B6BFF]/60 text-[#CBB6FF] text-[14px] tracking-[0.04em] transition-colors duration-200 hover:bg-[#9B6BFF]/10"
            >
              База знаний
            </button>
          </div>
          {nvdError && (
            <div className="text-[14px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-[12px] px-4 py-2">
              {nvdError}
            </div>
          )}
          {error && (
            <div className="text-[14px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-[12px] px-4 py-2">
              {error}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Всего пользователей"
          value={formatNumber(stats.total_users)}
          hint="Все зарегистрированные аккаунты"
          icon={<UsersIcon className="w-4 h-4" />}
          tone="bg-white/10 text-white"
        />
        <StatCard
          label="Активные 24ч"
          value={formatNumber(stats.active_users_24h)}
          hint="Входили в систему за последние 24 часа"
          icon={<ActivityIcon className="w-4 h-4" />}
          tone="bg-emerald-500/15 text-emerald-300"
        />
        <StatCard
          label="Платные пользователи"
          value={formatNumber(stats.paid_users)}
          hint={`${paidConversion}% конверсия`}
          icon={<CreditIcon className="w-4 h-4" />}
          tone="bg-[#9B6BFF]/15 text-[#CBB6FF]"
        />
        <StatCard
          label="Сабмиты в чемпионате"
          value={formatNumber(stats.current_championship_submissions)}
          hint="Количество отправок в текущем чемпионате"
          icon={<TrophyIcon className="w-4 h-4" />}
          tone="bg-amber-400/15 text-amber-200"
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <SectionCard
          title="Последние отзывы"
          subtitle="Свежие сообщения из формы обратной связи"
          action={(
            <div className="w-9 h-9 rounded-full bg-white/10 flex items-center justify-center text-white/60">
              <MessageIcon className="w-4 h-4" />
            </div>
          )}
        >
          <div className="flex flex-col gap-4">
            {feedbacks.length === 0 && (
              <div className="text-[14px] text-white/50">
                Пока нет отзывов
              </div>
            )}
            {feedbacks.map((feedback) => (
              <div key={`${feedback.user_id}-${feedback.created_at}-${feedback.topic}`} className="border-b border-white/10 last:border-b-0 pb-4 last:pb-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[14px] text-white">
                        {feedback.username || `Пользователь #${feedback.user_id}`}
                      </span>
                      <span className="text-[12px] uppercase tracking-[0.18em] px-2 py-1 rounded-full bg-[#9B6BFF]/15 text-[#CBB6FF] border border-[#9B6BFF]/30">
                        {feedback.topic}
                      </span>
                    </div>
                    <div className="text-[14px] text-white/60 mt-2">
                      {feedback.message}
                    </div>
                    <div className="text-[12px] text-white/40 mt-2">
                      {formatRelativeTime(feedback.created_at)}
                    </div>
                  </div>
                  <MessageIcon className="w-4 h-4 text-white/40" />
                </div>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard
          title="Текущий чемпионат"
          subtitle={contest?.title || 'Нет активного чемпионата'}
          action={(
            <span className={`text-[12px] uppercase tracking-[0.24em] px-3 py-1 rounded-full ${contestStatus.tone}`}>
              {contestStatus.label}
            </span>
          )}
        >
          <div className="flex flex-col gap-3 text-[14px] text-white/70">
            <div className="flex items-center justify-between">
              <span className="text-white/50">Даты проведения</span>
              <span className="text-white">
                {contest ? `${formatDate(contest.start_at)} — ${formatDate(contest.end_at)}` : '—'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-white/50">Сабмиты</span>
              <span className="text-white">
                {formatNumber(stats.current_championship_submissions)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-white/50">Публичный</span>
              <span className="text-white">
                {contest ? (contest.is_public ? 'Да' : 'Нет') : '—'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-white/50">Лидерборд</span>
              <span className="text-white">
                {contest ? (contest.leaderboard_visible ? 'Виден' : 'Скрыт') : '—'}
              </span>
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title="Последняя статья"
        subtitle="Самая свежая запись из базы знаний"
        action={(
          <div className="w-9 h-9 rounded-full bg-white/10 flex items-center justify-center text-white/60">
            <FileIcon className="w-4 h-4" />
          </div>
        )}
      >
        {lastArticle ? (
          <div className="flex flex-col gap-4">
            <div>
              <div className="text-[20px] leading-[26px] text-white">
                {lastArticle.ru_title || 'Без названия'}
              </div>
              {lastArticle.ru_summary && (
                <div className="text-[14px] text-white/60 mt-2">
                  {lastArticle.ru_summary}
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-4 text-[13px] text-white/50">
              <span className="uppercase tracking-[0.2em] px-2 py-1 rounded-full bg-white/5 border border-white/10">
                {lastArticle.source || 'Источник'}
              </span>
              <span>Дата: {formatDate(lastArticle.created_at)}</span>
              {lastArticle.cve_id && <span>{lastArticle.cve_id}</span>}
            </div>
          </div>
        ) : (
          <div className="text-[14px] text-white/50">
            Пока нет статей
          </div>
        )}
      </SectionCard>

      <KnowledgeBaseModal
        open={isKbOpen}
        onClose={() => setIsKbOpen(false)}
        onCreated={() => loadDashboard()}
        onUpdated={() => loadDashboard()}
      />
    </div>
  );
}

export default Admin;
