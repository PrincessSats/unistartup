import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
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

function getApiErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  const responseData = err?.response?.data;
  if (typeof responseData === 'string' && responseData.trim()) return responseData;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const text = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && typeof item.msg === 'string') return item.msg;
        try {
          return JSON.stringify(item);
        } catch {
          return '';
        }
      })
      .filter(Boolean)
      .join('; ');
    if (text) return text;
  }
  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string' && detail.message.trim()) return detail.message;
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  if (typeof err?.message === 'string' && err.message.trim()) return err.message;
  return fallback;
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
  const [editGenerateStatus, setEditGenerateStatus] = useState('idle');

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
    setEditGenerateStatus('idle');
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
      setError(getApiErrorMessage(err, 'Не удалось создать статью'));
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
      setArticlesError(getApiErrorMessage(err, 'Не удалось загрузить статьи'));
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

  const isEditBusy = editStatus === 'saving' || editStatus === 'deleting';
  const canUpdate = editForm.source.trim().length > 0 && !isEditBusy && selectedId;

  const handleGenerateArticle = async () => {
    if (!editForm.raw_en_text.trim()) {
      setEditError('Заполните Raw EN text для генерации');
      return;
    }
    setEditGenerateStatus('generating');
    setEditError('');
    try {
      const result = await adminAPI.generateArticle({
        raw_en_text: editForm.raw_en_text.trim(),
      });
      setEditForm((prev) => ({
        ...prev,
        ru_title: result.ru_title || prev.ru_title,
        ru_summary: result.ru_summary || prev.ru_summary,
        ru_explainer: result.ru_explainer || prev.ru_explainer,
        tags: Array.isArray(result.tags) && result.tags.length
          ? result.tags.join(', ')
          : prev.tags,
      }));
      setEditGenerateStatus('idle');
    } catch (err) {
      setEditError(getApiErrorMessage(err, 'Не удалось сгенерировать поля'));
      setEditGenerateStatus('idle');
    }
  };

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
      setEditError(getApiErrorMessage(err, 'Не удалось сохранить изменения'));
      setEditStatus('idle');
    }
  };

  const handleDeleteArticle = async () => {
    if (!selectedId) return;
    const confirmed = window.confirm('Удалить статью? Это действие нельзя отменить.');
    if (!confirmed) return;

    setEditStatus('deleting');
    setEditError('');
    try {
      await adminAPI.deleteArticle(selectedId);
      setArticles((prev) => prev.filter((item) => item.id !== selectedId));
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
      if (onUpdated) {
        onUpdated();
      }
      setEditStatus('idle');
    } catch (err) {
      setEditError(getApiErrorMessage(err, 'Не удалось удалить статью'));
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
                  {editGenerateStatus === 'generating' && (
                    <div className="bg-white/5 border border-white/10 text-white/70 px-4 py-2 rounded-[12px] mb-4 text-sm">
                      Отправляем в модель… это может занять до 20–40 секунд
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
                      onClick={handleGenerateArticle}
                      disabled={editGenerateStatus === 'generating' || !editForm.raw_en_text.trim() || isEditBusy}
                      className="flex-1 h-12 bg-white/[0.03] hover:bg-white/[0.06] text-white rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {editGenerateStatus === 'generating' ? 'Генерация...' : 'Отправить в модель'}
                    </button>
                    <button
                      type="button"
                      onClick={handleDeleteArticle}
                      disabled={!selectedId || isEditBusy}
                      className="flex-1 h-12 bg-rose-500/20 border border-rose-400/40 hover:bg-rose-500/30 text-rose-100 rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {editStatus === 'deleting' ? 'Удаление...' : 'Удалить статью'}
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

function CreateTaskModal({ open, onClose, onCreated }) {
  const [generateForm, setGenerateForm] = useState({
    difficulty: '3',
    tags: '',
    description: '',
  });
  const [taskForm, setTaskForm] = useState({
    title: '',
    category: 'misc',
    difficulty: 3,
    points: 200,
    tags: '',
    language: 'ru',
    story: '',
    participant_description: '',
    state: 'draft',
    task_kind: 'contest',
    creation_solution: '',
    llm_raw_response: null,
  });
  const [flags, setFlags] = useState([
    { flag_id: 'main', format: 'FLAG{...}', expected_value: '', description: '' },
  ]);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setGenerateForm({ difficulty: '3', tags: '', description: '' });
    setTaskForm({
      title: '',
      category: 'misc',
      difficulty: 3,
      points: 200,
      tags: '',
      language: 'ru',
      story: '',
      participant_description: '',
      state: 'draft',
      task_kind: 'contest',
      creation_solution: '',
      llm_raw_response: null,
    });
    setFlags([{ flag_id: 'main', format: 'FLAG{...}', expected_value: '', description: '' }]);
    setStatus('idle');
    setError('');
  }, [open]);

  const handleGenerate = async () => {
    if (!generateForm.description.trim()) {
      setError('Добавьте описание для генерации');
      return;
    }
    setStatus('generating');
    setError('');
    try {
      const payload = {
        difficulty: Number(generateForm.difficulty || 1),
        tags: generateForm.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
        description: generateForm.description.trim(),
      };
      const result = await adminAPI.generateTask(payload);
      const data = result?.task || {};
        setTaskForm((prev) => ({
          ...prev,
          title: data.title || '',
          category: data.category || 'misc',
          difficulty: data.difficulty ?? Number(generateForm.difficulty || 1),
          points: data.points ?? (100 + (Number(data.difficulty || generateForm.difficulty || 1) - 1) * 50),
          tags: Array.isArray(data.tags) ? data.tags.join(', ') : '',
          language: data.language || 'ru',
          story: data.story || '',
          participant_description: data.participant_description || '',
          state: data.state || 'draft',
          creation_solution: data.creation_solution || '',
          llm_raw_response: data.llm_raw_response || {
            model: result.model,
            raw_text: result.raw_text,
            parsed: data,
          },
        }));
      setStatus('generated');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось сгенерировать задачу'));
      setStatus('idle');
    }
  };

  const handleSave = async () => {
    if (!taskForm.title.trim()) {
      setError('Заполните название задачи');
      return;
    }
    if (flags.some((flag) => !flag.expected_value.trim())) {
      setError('Укажите значение флага');
      return;
    }
    setStatus('saving');
    setError('');
    try {
      const payload = {
        title: taskForm.title.trim(),
        category: taskForm.category.trim(),
        difficulty: Number(taskForm.difficulty || 1),
        points: Number(taskForm.points || 0),
        tags: taskForm.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
        language: taskForm.language || 'ru',
        story: taskForm.story || null,
        participant_description: taskForm.participant_description || null,
        state: taskForm.state || 'draft',
        task_kind: taskForm.task_kind || 'contest',
        creation_solution: taskForm.creation_solution || null,
        llm_raw_response: taskForm.llm_raw_response || null,
        flags: flags.map((flag) => ({
          flag_id: flag.flag_id || 'main',
          format: flag.format || 'FLAG{...}',
          expected_value: flag.expected_value,
          description: flag.description || null,
        })),
      };
      await adminAPI.createTask(payload);
      setStatus('idle');
      onCreated?.();
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось создать задачу'));
      setStatus('idle');
    }
  };

  const updateFlag = (index, field, value) => {
    setFlags((prev) => prev.map((flag, idx) => (idx === index ? { ...flag, [field]: value } : flag)));
  };

  const addFlag = () => {
    setFlags((prev) => [...prev, { flag_id: `flag${prev.length + 1}`, format: 'FLAG{...}', expected_value: '', description: '' }]);
  };

  const removeFlag = (index) => {
    setFlags((prev) => prev.filter((_, idx) => idx !== index));
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4 py-8">
      <div className="w-full max-w-4xl bg-[#0B0A10] border border-white/10 rounded-[20px] p-6 text-white">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-[22px] leading-[28px]">Создание задачи</h3>
            <p className="text-[14px] text-white/50 mt-1">Генерация через LLM + ручная правка</p>
          </div>
          <button onClick={onClose} className="text-white/60 hover:text-white">Закрыть</button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <div className="flex flex-col gap-4">
            <div className="text-[14px] uppercase tracking-[0.2em] text-white/40">Параметры генерации</div>
            <div className="grid grid-cols-2 gap-3">
              <input
                value={generateForm.difficulty}
                onChange={(e) => setGenerateForm((prev) => ({ ...prev, difficulty: e.target.value }))}
                className="h-12 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
                placeholder="Сложность 1-10"
              />
              <input
                value={generateForm.tags}
                onChange={(e) => setGenerateForm((prev) => ({ ...prev, tags: e.target.value }))}
                className="h-12 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
                placeholder="Теги через запятую"
              />
            </div>
            <textarea
              value={generateForm.description}
              onChange={(e) => setGenerateForm((prev) => ({ ...prev, description: e.target.value }))}
              className="min-h-[120px] rounded-[12px] bg-white/5 border border-white/10 px-3 py-2 text-white"
              placeholder="Коротко опишите задачу"
            />
            <button
              type="button"
              onClick={handleGenerate}
              disabled={status === 'generating'}
              className="h-11 rounded-[12px] bg-[#9B6BFF] text-white text-[14px] tracking-[0.04em] hover:bg-[#8452FF] disabled:opacity-60"
            >
              {status === 'generating' ? 'Генерация...' : 'Сгенерировать'}
            </button>
          </div>

          <div className="flex flex-col gap-4">
            <div className="text-[14px] uppercase tracking-[0.2em] text-white/40">Данные задачи</div>
            <input
              value={taskForm.title}
              onChange={(e) => setTaskForm((prev) => ({ ...prev, title: e.target.value }))}
              className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
              placeholder="Название задачи"
            />
            <div className="grid grid-cols-2 gap-3">
              <input
                value={taskForm.category}
                onChange={(e) => setTaskForm((prev) => ({ ...prev, category: e.target.value }))}
                className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
                placeholder="Категория"
              />
              <input
                value={taskForm.tags}
                onChange={(e) => setTaskForm((prev) => ({ ...prev, tags: e.target.value }))}
                className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
                placeholder="Теги"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <input
                value={taskForm.difficulty}
                onChange={(e) => setTaskForm((prev) => ({ ...prev, difficulty: e.target.value }))}
                className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
                placeholder="Сложность"
              />
              <input
                value={taskForm.points}
                onChange={(e) => setTaskForm((prev) => ({ ...prev, points: e.target.value }))}
                className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
                placeholder="Очки"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <select
                value={taskForm.task_kind}
                onChange={(e) => setTaskForm((prev) => ({ ...prev, task_kind: e.target.value }))}
                className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
              >
                <option value="contest">Contest</option>
                <option value="practice">Practice</option>
              </select>
              <select
                value={taskForm.state}
                onChange={(e) => setTaskForm((prev) => ({ ...prev, state: e.target.value }))}
                className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
              >
                <option value="draft">Draft</option>
                <option value="ready">Ready</option>
                <option value="published">Published</option>
              </select>
            </div>
            <textarea
              value={taskForm.participant_description}
              onChange={(e) => setTaskForm((prev) => ({ ...prev, participant_description: e.target.value }))}
              className="min-h-[100px] rounded-[12px] bg-white/5 border border-white/10 px-3 py-2 text-white"
              placeholder="Описание для участника"
            />
            <textarea
              value={taskForm.story}
              onChange={(e) => setTaskForm((prev) => ({ ...prev, story: e.target.value }))}
              className="min-h-[80px] rounded-[12px] bg-white/5 border border-white/10 px-3 py-2 text-white"
              placeholder="Легенда (story)"
            />
            <textarea
              value={taskForm.creation_solution}
              onChange={(e) => setTaskForm((prev) => ({ ...prev, creation_solution: e.target.value }))}
              className="min-h-[100px] rounded-[12px] bg-white/5 border border-white/10 px-3 py-2 text-white"
              placeholder="Решение для организаторов"
            />
          </div>
        </div>

        <div className="mt-6">
          <div className="text-[14px] uppercase tracking-[0.2em] text-white/40">Флаги</div>
          <div className="flex flex-col gap-3 mt-3">
            {flags.map((flag, index) => (
              <div key={index} className="grid grid-cols-1 md:grid-cols-5 gap-3 items-center">
                <input
                  value={flag.flag_id}
                  onChange={(e) => updateFlag(index, 'flag_id', e.target.value)}
                  className="h-10 rounded-[10px] bg-white/5 border border-white/10 px-3 text-white"
                  placeholder="flag_id"
                />
                <input
                  value={flag.format}
                  onChange={(e) => updateFlag(index, 'format', e.target.value)}
                  className="h-10 rounded-[10px] bg-white/5 border border-white/10 px-3 text-white"
                  placeholder="FLAG{...}"
                />
                <input
                  value={flag.expected_value}
                  onChange={(e) => updateFlag(index, 'expected_value', e.target.value)}
                  className="h-10 rounded-[10px] bg-white/5 border border-white/10 px-3 text-white"
                  placeholder="Значение"
                />
                <input
                  value={flag.description}
                  onChange={(e) => updateFlag(index, 'description', e.target.value)}
                  className="h-10 rounded-[10px] bg-white/5 border border-white/10 px-3 text-white"
                  placeholder="Описание"
                />
                <button
                  type="button"
                  onClick={() => removeFlag(index)}
                  className="h-10 rounded-[10px] bg-white/5 text-white/60 hover:text-white"
                >
                  Удалить
                </button>
              </div>
            ))}
            <button type="button" onClick={addFlag} className="self-start text-[14px] text-[#CBB6FF]">
              + Добавить флаг
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 text-[14px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-[12px] px-4 py-2">
            {error}
          </div>
        )}

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
            onClick={handleSave}
            disabled={status === 'saving'}
            className="flex-1 h-12 bg-[#9B6BFF] hover:bg-[#8452FF] text-white rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {status === 'saving' ? 'Сохранение...' : 'Сохранить задачу'}
          </button>
        </div>
      </div>
    </div>
  );
}

function ContestPlanningModal({ open, onClose }) {
  const [contests, setContests] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [selectedContestId, setSelectedContestId] = useState(null);
  const [contestForm, setContestForm] = useState({
    title: '',
    description: '',
    start_at: '',
    end_at: '',
    is_public: false,
    leaderboard_visible: true,
  });
  const [selectedTasks, setSelectedTasks] = useState([]);
  const [taskSearch, setTaskSearch] = useState('');
  const [includeDrafts, setIncludeDrafts] = useState(false);

  const loadData = async () => {
    setStatus('loading');
    setError('');
    try {
      const [contestList, taskList] = await Promise.all([
        adminAPI.listContests(),
        adminAPI.listTasks({ task_kind: 'contest' }),
      ]);
      setContests(contestList);
      setTasks(taskList);
      setStatus('idle');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось загрузить данные'));
      setStatus('idle');
    }
  };

  useEffect(() => {
    if (open) {
      loadData();
      setSelectedContestId(null);
      setContestForm({
        title: '',
        description: '',
        start_at: '',
        end_at: '',
        is_public: false,
        leaderboard_visible: true,
      });
      setSelectedTasks([]);
      setTaskSearch('');
      setIncludeDrafts(false);
      setError('');
    }
  }, [open]);

  const formatLocal = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  };

  const handleEditContest = async (contestId) => {
    setStatus('loading');
    setError('');
    try {
      const data = await adminAPI.getContest(contestId);
      setSelectedContestId(contestId);
      setContestForm({
        title: data.title || '',
        description: data.description || '',
        start_at: formatLocal(data.start_at),
        end_at: formatLocal(data.end_at),
        is_public: data.is_public,
        leaderboard_visible: data.leaderboard_visible,
      });
      setSelectedTasks(
        (data.tasks || []).map((task) => ({
          task_id: task.task_id,
          order_index: task.order_index,
          base: task,
          points_override: task.points_override ?? '',
          override_title: task.override_title ?? '',
          override_participant_description: task.override_participant_description ?? '',
          override_tags: Array.isArray(task.override_tags) ? task.override_tags.join(', ') : '',
          override_category: task.override_category ?? '',
          override_difficulty: task.override_difficulty ?? '',
        }))
      );
      setStatus('idle');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось загрузить контест'));
      setStatus('idle');
    }
  };

  const addTask = (task) => {
    if (selectedTasks.some((item) => item.task_id === task.id)) return;
    setSelectedTasks((prev) => [
      ...prev,
      {
        task_id: task.id,
        order_index: prev.length,
        base: task,
        points_override: '',
        override_title: '',
        override_participant_description: '',
        override_tags: '',
        override_category: '',
        override_difficulty: '',
      },
    ]);
  };

  const removeTask = (taskId) => {
    setSelectedTasks((prev) => prev.filter((item) => item.task_id !== taskId));
  };

  const moveTask = (index, direction) => {
    setSelectedTasks((prev) => {
      const next = [...prev];
      const targetIndex = index + direction;
      if (targetIndex < 0 || targetIndex >= next.length) return prev;
      const temp = next[index];
      next[index] = next[targetIndex];
      next[targetIndex] = temp;
      return next.map((item, idx) => ({ ...item, order_index: idx }));
    });
  };

  const updateSelectedTask = (taskId, field, value) => {
    setSelectedTasks((prev) =>
      prev.map((item) => (item.task_id === taskId ? { ...item, [field]: value } : item))
    );
  };

  const handleSave = async () => {
    if (!contestForm.title.trim()) {
      setError('Укажите название контеста');
      return;
    }
    if (selectedTasks.length < 2 || selectedTasks.length > 10) {
      setError('Контест должен содержать 2-10 задач');
      return;
    }
    if (!contestForm.start_at || !contestForm.end_at) {
      setError('Укажите даты начала и конца');
      return;
    }
    setStatus('saving');
    setError('');
    try {
      const tasksPayload = selectedTasks.map((task, index) => ({
        task_id: task.task_id,
        order_index: index,
        points_override: task.points_override === '' ? null : Number(task.points_override),
        override_title: task.override_title || null,
        override_participant_description: task.override_participant_description || null,
        override_tags: task.override_tags
          ? task.override_tags.split(',').map((tag) => tag.trim()).filter(Boolean)
          : null,
        override_category: task.override_category || null,
        override_difficulty: task.override_difficulty === '' ? null : Number(task.override_difficulty),
      }));
      const payload = {
        title: contestForm.title.trim(),
        description: contestForm.description || null,
        start_at: new Date(contestForm.start_at).toISOString(),
        end_at: new Date(contestForm.end_at).toISOString(),
        is_public: contestForm.is_public,
        leaderboard_visible: contestForm.leaderboard_visible,
        tasks: tasksPayload,
      };
      if (selectedContestId) {
        await adminAPI.updateContest(selectedContestId, payload);
      } else {
        await adminAPI.createContest(payload);
      }
      await loadData();
      setStatus('idle');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось сохранить контест'));
      setStatus('idle');
    }
  };

  const handleDeleteContest = async (contestId) => {
    const confirmed = window.confirm('Удалить чемпионат? Это действие нельзя отменить.');
    if (!confirmed) return;
    setStatus('saving');
    setError('');
    try {
      await adminAPI.deleteContest(contestId);
      if (selectedContestId === contestId) {
        setSelectedContestId(null);
        setContestForm({
          title: '',
          description: '',
          start_at: '',
          end_at: '',
          is_public: false,
          leaderboard_visible: true,
        });
        setSelectedTasks([]);
      }
      await loadData();
      setStatus('idle');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось удалить контест'));
      setStatus('idle');
    }
  };

  const handleDeleteTaskFromGallery = async (task) => {
    const taskTitle = task?.title || `#${task?.id}`;
    const confirmed = window.confirm(`Удалить задачу "${taskTitle}"? Это действие нельзя отменить.`);
    if (!confirmed) return;
    setStatus('saving');
    setError('');
    try {
      await adminAPI.deleteTask(task.id);
      setTasks((prev) => prev.filter((item) => item.id !== task.id));
      setSelectedTasks((prev) =>
        prev
          .filter((item) => item.task_id !== task.id)
          .map((item, idx) => ({ ...item, order_index: idx }))
      );
      setStatus('idle');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось удалить задачу'));
      setStatus('idle');
    }
  };

  if (!open) return null;

  const filteredTasks = tasks.filter((task) => {
    if (!includeDrafts && task.state === 'draft') return false;
    if (!taskSearch.trim()) return true;
    return task.title?.toLowerCase().includes(taskSearch.toLowerCase());
  });

  const activeContest = contests.find((contest) => contest.status === 'active');
  const previousContests = contests.filter((contest) => contest.status === 'finished');
  const upcomingContests = contests.filter((contest) => contest.status === 'upcoming');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4 py-8">
      <div className="w-full max-w-6xl bg-[#0B0A10] border border-white/10 rounded-[20px] p-6 text-white max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-[22px] leading-[28px]">Планирование контеста</h3>
            <p className="text-[14px] text-white/50 mt-1">Соберите цепочку задач и настройте параметры</p>
          </div>
          <button onClick={onClose} className="text-white/60 hover:text-white">Закрыть</button>
        </div>

        {activeContest && (
          <div className="mt-4 p-4 rounded-[16px] border border-white/10 bg-white/5">
            <div className="flex items-center justify-between gap-3">
              <div className="text-[12px] uppercase tracking-[0.2em] text-white/40">Текущий контест</div>
              <button
                type="button"
                onClick={() => handleDeleteContest(activeContest.id)}
                className="px-3 h-8 rounded-[10px] border border-rose-400/40 bg-rose-500/15 text-rose-200 text-[12px]"
              >
                Удалить
              </button>
            </div>
            <div className="text-[18px] mt-2">{activeContest.title}</div>
            <div className="text-[13px] text-white/50 mt-1">
              {formatDate(activeContest.start_at)} — {formatDate(activeContest.end_at)}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          <div className="flex flex-col gap-4">
            <div className="text-[14px] uppercase tracking-[0.2em] text-white/40">Контесты</div>
            <div className="flex flex-col gap-3">
              {upcomingContests.map((contest) => (
                <div key={contest.id} className="flex items-stretch gap-2">
                  <button
                    type="button"
                    onClick={() => handleEditContest(contest.id)}
                    className="flex-1 text-left p-3 rounded-[12px] bg-white/5 hover:bg-white/10"
                  >
                    <div className="text-[16px]">{contest.title}</div>
                    <div className="text-[12px] text-white/50">Скоро</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteContest(contest.id)}
                    className="px-3 rounded-[12px] border border-rose-400/40 bg-rose-500/15 text-rose-200 text-[12px]"
                  >
                    Удалить
                  </button>
                </div>
              ))}
              {previousContests.map((contest) => (
                <div key={contest.id} className="flex items-stretch gap-2">
                  <button
                    type="button"
                    onClick={() => handleEditContest(contest.id)}
                    className="flex-1 text-left p-3 rounded-[12px] bg-white/5 hover:bg-white/10"
                  >
                    <div className="text-[16px]">{contest.title}</div>
                    <div className="text-[12px] text-white/50">Завершен</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteContest(contest.id)}
                    className="px-3 rounded-[12px] border border-rose-400/40 bg-rose-500/15 text-rose-200 text-[12px]"
                  >
                    Удалить
                  </button>
                </div>
              ))}
              {upcomingContests.length === 0 && previousContests.length === 0 && (
                <div className="text-[13px] text-white/50">Контестов пока нет</div>
              )}
            </div>
          </div>

          <div className="lg:col-span-2 flex flex-col gap-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                value={contestForm.title}
                onChange={(e) => setContestForm((prev) => ({ ...prev, title: e.target.value }))}
                className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
                placeholder="Название контеста"
              />
              <input
                value={contestForm.description}
                onChange={(e) => setContestForm((prev) => ({ ...prev, description: e.target.value }))}
                className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
                placeholder="Описание"
              />
              <input
                type="datetime-local"
                value={contestForm.start_at}
                onChange={(e) => setContestForm((prev) => ({ ...prev, start_at: e.target.value }))}
                className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
              />
              <input
                type="datetime-local"
                value={contestForm.end_at}
                onChange={(e) => setContestForm((prev) => ({ ...prev, end_at: e.target.value }))}
                className="h-11 rounded-[12px] bg-white/5 border border-white/10 px-3 text-white"
              />
            </div>
            <div className="flex items-center gap-4 text-[14px] text-white/70">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={contestForm.is_public}
                  onChange={(e) => setContestForm((prev) => ({ ...prev, is_public: e.target.checked }))}
                />
                Публичный
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={contestForm.leaderboard_visible}
                  onChange={(e) => setContestForm((prev) => ({ ...prev, leaderboard_visible: e.target.checked }))}
                />
                Лидерборд виден
              </label>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="flex flex-col gap-3">
                <div className="text-[14px] uppercase tracking-[0.2em] text-white/40">Галерея задач</div>
                <input
                  value={taskSearch}
                  onChange={(e) => setTaskSearch(e.target.value)}
                  className="h-10 rounded-[10px] bg-white/5 border border-white/10 px-3 text-white"
                  placeholder="Поиск по названию"
                />
                <label className="flex items-center gap-2 text-[12px] text-white/50">
                  <input
                    type="checkbox"
                    checked={includeDrafts}
                    onChange={(e) => setIncludeDrafts(e.target.checked)}
                  />
                  Показывать черновики
                </label>
                <div className="flex flex-col gap-2 max-h-[320px] overflow-y-auto pr-2">
                  {filteredTasks.map((task) => (
                    <div key={task.id} className="flex items-center justify-between gap-2 rounded-[12px] bg-white/5 px-3 py-2">
                      <div>
                        <div className="text-[14px]">{task.title}</div>
                        <div className="text-[12px] text-white/50">{task.category} · {task.points} pts</div>
                      </div>
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => addTask(task)}
                          className="text-[12px] text-[#CBB6FF]"
                        >
                          Добавить
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteTaskFromGallery(task)}
                          className="text-[12px] text-rose-300"
                        >
                          Удалить
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex flex-col gap-3">
                <div className="text-[14px] uppercase tracking-[0.2em] text-white/40">Задачи контеста</div>
                <div className="flex flex-col gap-3 max-h-[320px] overflow-y-auto pr-2">
                  {selectedTasks.map((task, index) => (
                    <div key={task.task_id} className="rounded-[12px] bg-white/5 p-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-[14px]">{task.base?.title || `Task #${task.task_id}`}</div>
                          <div className="text-[12px] text-white/50">Позиция {index + 1}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button onClick={() => moveTask(index, -1)} className="text-white/60">↑</button>
                          <button onClick={() => moveTask(index, 1)} className="text-white/60">↓</button>
                          <button onClick={() => removeTask(task.task_id)} className="text-rose-300">Удалить</button>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2 mt-3">
                        <input
                          value={task.override_title}
                          onChange={(e) => updateSelectedTask(task.task_id, 'override_title', e.target.value)}
                          className="h-9 rounded-[10px] bg-white/5 border border-white/10 px-2 text-white"
                          placeholder="Override title"
                        />
                        <input
                          value={task.points_override}
                          onChange={(e) => updateSelectedTask(task.task_id, 'points_override', e.target.value)}
                          className="h-9 rounded-[10px] bg-white/5 border border-white/10 px-2 text-white"
                          placeholder="Points override"
                        />
                        <input
                          value={task.override_category}
                          onChange={(e) => updateSelectedTask(task.task_id, 'override_category', e.target.value)}
                          className="h-9 rounded-[10px] bg-white/5 border border-white/10 px-2 text-white"
                          placeholder="Override category"
                        />
                        <input
                          value={task.override_difficulty}
                          onChange={(e) => updateSelectedTask(task.task_id, 'override_difficulty', e.target.value)}
                          className="h-9 rounded-[10px] bg-white/5 border border-white/10 px-2 text-white"
                          placeholder="Override difficulty"
                        />
                      </div>
                      <input
                        value={task.override_tags}
                        onChange={(e) => updateSelectedTask(task.task_id, 'override_tags', e.target.value)}
                        className="mt-2 h-9 rounded-[10px] bg-white/5 border border-white/10 px-2 text-white"
                        placeholder="Override tags"
                      />
                      <textarea
                        value={task.override_participant_description}
                        onChange={(e) => updateSelectedTask(task.task_id, 'override_participant_description', e.target.value)}
                        className="mt-2 min-h-[80px] rounded-[10px] bg-white/5 border border-white/10 px-2 py-1 text-white"
                        placeholder="Override description"
                      />
                    </div>
                  ))}
                  {selectedTasks.length === 0 && (
                    <div className="text-[13px] text-white/50">Добавьте задачи из галереи</div>
                  )}
                </div>
              </div>
            </div>

            {error && (
              <div className="text-[14px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-[12px] px-4 py-2">
                {error}
              </div>
            )}

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => {
                  setSelectedContestId(null);
                  setContestForm({
                    title: '',
                    description: '',
                    start_at: '',
                    end_at: '',
                    is_public: false,
                    leaderboard_visible: true,
                  });
                  setSelectedTasks([]);
                }}
                className="flex-1 h-11 rounded-[12px] bg-white/5 text-white/70"
              >
                Новый контест
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={status === 'saving'}
                className="flex-1 h-11 rounded-[12px] bg-[#9B6BFF] text-white hover:bg-[#8452FF] disabled:opacity-60"
              >
                {status === 'saving' ? 'Сохранение...' : 'Сохранить контест'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PromptManagerModal({ open, onClose }) {
  const [prompts, setPrompts] = useState([]);
  const [selectedCode, setSelectedCode] = useState('');
  const [editorValue, setEditorValue] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');

  const loadPrompts = useCallback(async () => {
    setStatus('loading');
    setError('');
    try {
      const data = await adminAPI.listPrompts();
      const list = Array.isArray(data) ? data : [];
      setPrompts(list);
      if (list.length > 0) {
        const preferred = list.find((item) => item.code === 'task_prompt') || list[0];
        setSelectedCode(preferred.code);
        setEditorValue(preferred.content || '');
      } else {
        setSelectedCode('');
        setEditorValue('');
      }
      setStatus('idle');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось загрузить промпты'));
      setPrompts([]);
      setSelectedCode('');
      setEditorValue('');
      setStatus('idle');
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    loadPrompts();
  }, [open, loadPrompts]);

  const selectedPrompt = useMemo(
    () => prompts.find((item) => item.code === selectedCode) || null,
    [prompts, selectedCode]
  );

  const handleSelect = (prompt) => {
    setSelectedCode(prompt.code);
    setEditorValue(prompt.content || '');
    setError('');
  };

  const handleSave = async () => {
    if (!selectedPrompt) return;
    if (!editorValue.trim()) {
      setError('Промпт не может быть пустым');
      return;
    }
    setStatus('saving');
    setError('');
    try {
      const updated = await adminAPI.updatePrompt(selectedPrompt.code, { content: editorValue });
      setPrompts((prev) =>
        prev.map((item) => (item.code === updated.code ? { ...item, ...updated } : item))
      );
      setEditorValue(updated.content || '');
      setStatus('idle');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось сохранить промпт'));
      setStatus('idle');
    }
  };

  const hasChanges = selectedPrompt
    ? editorValue.trim() !== (selectedPrompt.content || '').trim()
    : false;

  const handleOverlayClick = (event) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 px-4"
      onClick={handleOverlayClick}
    >
      <div className="bg-[#0B0A10] border border-white/[0.09] rounded-[20px] p-8 w-full max-w-6xl mx-4 font-sans-figma">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h3 className="text-white text-[24px] leading-[32px] font-medium">Prompt Manager</h3>
            <p className="text-white/60 text-[14px] mt-2">
              Изменения применяются к следующей генерации без деплоя
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

        {error && (
          <div className="bg-red-500/10 border border-red-500/50 text-red-200 px-4 py-2 rounded-[12px] mb-4 text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
          <div className="border border-white/[0.08] rounded-[16px] p-4 max-h-[560px] overflow-y-auto">
            <div className="text-[14px] text-white/60 mb-3">Промпты</div>
            {status === 'loading' && (
              <div className="text-[14px] text-white/40">Загрузка...</div>
            )}
            {status !== 'loading' && prompts.length === 0 && (
              <div className="text-[14px] text-white/40">Промпты не найдены</div>
            )}
            <div className="flex flex-col gap-2">
              {prompts.map((prompt) => (
                <button
                  key={prompt.code}
                  type="button"
                  onClick={() => handleSelect(prompt)}
                  className={`text-left rounded-[12px] px-3 py-3 border transition ${
                    selectedCode === prompt.code
                      ? 'border-[#9B6BFF]/60 bg-[#9B6BFF]/10 text-white'
                      : 'border-white/10 bg-white/[0.02] text-white/70 hover:border-[#9B6BFF]/40'
                  }`}
                >
                  <div className="text-[14px] text-white">{prompt.title}</div>
                  <div className="text-[12px] text-white/50 mt-1">{prompt.code}</div>
                  <div className="mt-2 text-[11px]">
                    {prompt.is_overridden ? (
                      <span className="px-2 py-1 rounded-full bg-[#9B6BFF]/20 text-[#CBB6FF] border border-[#9B6BFF]/30">
                        DB override
                      </span>
                    ) : (
                      <span className="px-2 py-1 rounded-full bg-white/10 text-white/60 border border-white/10">
                        Built-in default
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="border border-white/[0.08] rounded-[16px] p-5">
            {!selectedPrompt ? (
              <div className="text-white/50 text-[14px]">Выберите промпт для редактирования</div>
            ) : (
              <>
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div>
                    <div className="text-[16px] text-white">{selectedPrompt.title}</div>
                    <div className="text-[13px] text-white/50 mt-1">
                      {selectedPrompt.description || 'Описание не задано'}
                    </div>
                  </div>
                  <div className="text-[12px] text-white/40">
                    Updated: {formatDateTime(selectedPrompt.updated_at)}
                  </div>
                </div>
                <textarea
                  value={editorValue}
                  onChange={(e) => setEditorValue(e.target.value)}
                  className="w-full min-h-[420px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30 font-mono text-[13px]"
                  placeholder="Введите системный промпт"
                />
                <div className="flex gap-3 mt-4">
                  <button
                    type="button"
                    onClick={() => setEditorValue(selectedPrompt.content || '')}
                    disabled={!hasChanges || status === 'saving'}
                    className="h-11 px-4 rounded-[10px] bg-white/[0.03] hover:bg-white/[0.06] text-white transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    Сбросить
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={!hasChanges || status === 'saving'}
                    className="h-11 px-4 rounded-[10px] bg-[#9B6BFF] hover:bg-[#8452FF] text-white transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {status === 'saving' ? 'Сохранение...' : 'Сохранить промпт'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
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
  const [isTaskOpen, setIsTaskOpen] = useState(false);
  const [isContestPlanningOpen, setIsContestPlanningOpen] = useState(false);
  const [isPromptManagerOpen, setIsPromptManagerOpen] = useState(false);
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
      setNvdError(getApiErrorMessage(err, 'Не удалось выполнить синхронизацию NVD'));
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
              onClick={() => setIsContestPlanningOpen(true)}
              className="h-10 px-4 rounded-[12px] bg-white/10 border border-white/10 text-white/80 text-[14px] tracking-[0.04em] transition-colors duration-200 hover:border-[#9B6BFF]/60 hover:text-white"
            >
              Планирование контеста
            </button>
            <button
              type="button"
              onClick={() => setIsPromptManagerOpen(true)}
              className="h-10 px-4 rounded-[12px] bg-white/10 border border-white/10 text-white/80 text-[14px] tracking-[0.04em] transition-colors duration-200 hover:border-[#9B6BFF]/60 hover:text-white"
            >
              Prompt Manager
            </button>
            <button
              type="button"
              onClick={() => setIsTaskOpen(true)}
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
          lastArticle.id ? (
            <Link
              to={`/knowledge/${lastArticle.id}`}
              className="flex flex-col gap-4 rounded-[14px] border border-white/5 bg-white/[0.02] p-4 transition hover:border-[#9B6BFF]/60"
            >
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
            </Link>
          ) : (
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
          )
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
      <CreateTaskModal
        open={isTaskOpen}
        onClose={() => setIsTaskOpen(false)}
        onCreated={() => loadDashboard()}
      />
      <ContestPlanningModal
        open={isContestPlanningOpen}
        onClose={() => setIsContestPlanningOpen(false)}
      />
      <PromptManagerModal
        open={isPromptManagerOpen}
        onClose={() => setIsPromptManagerOpen(false)}
      />
    </div>
  );
}

export default Admin;
