import React, { useEffect, useState, useCallback } from 'react';
import Drawer from '../Widgets/Drawer';
import { adminAPI } from '../../../services/api';
import { SkeletonBlock } from '../../../components/LoadingState';

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' });
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

const initialFormState = {
  source: '',
  source_id: '',
  cve_id: '',
  raw_en_text: '',
  ru_title: '',
  ru_summary: '',
  ru_explainer: '',
  tags: '',
  difficulty: '',
};

function KnowledgeBaseDrawer({ open, onClose, onCreated, onUpdated }) {
  const [tab, setTab] = useState('create');
  const [form, setForm] = useState(initialFormState);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [articles, setArticles] = useState([]);
  const [articlesLoading, setArticlesLoading] = useState(false);
  const [articlesError, setArticlesError] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [editForm, setEditForm] = useState(initialFormState);
  const [editStatus, setEditStatus] = useState('idle');
  const [editError, setEditError] = useState('');
  const [editGenerateStatus, setEditGenerateStatus] = useState('idle');

  useEffect(() => {
    if (!open) return;
    setTab('create');
    setForm(initialFormState);
    setStatus('idle');
    setError('');
    setArticles([]);
    setArticlesLoading(false);
    setArticlesError('');
    setSelectedId(null);
    setEditForm(initialFormState);
    setEditStatus('idle');
    setEditError('');
    setEditGenerateStatus('idle');
  }, [open]);

  const loadArticles = useCallback(async () => {
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
  }, []);

  useEffect(() => {
    if (!open) return;
    if (tab !== 'edit') return;
    loadArticles();
  }, [open, tab, loadArticles]);

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
      setEditForm(initialFormState);
      if (onUpdated) {
        onUpdated();
      }
      setEditStatus('idle');
    } catch (err) {
      setEditError(getApiErrorMessage(err, 'Не удалось удалить статью'));
      setEditStatus('idle');
    }
  };

  const renderCreateTab = () => (
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
    </>
  );

  const renderEditTab = () => (
    <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6">
      <div className="border border-white/[0.08] rounded-[16px] p-4 max-h-[480px] overflow-y-auto">
        <div className="text-[14px] text-white/60 mb-3">Список статей</div>
        {articlesLoading && (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, index) => (
              <SkeletonBlock key={`articles-skeleton-${index}`} className="h-16 w-full rounded-[12px]" />
            ))}
          </div>
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
              <div className="flex gap-2">
                <textarea
                  value={editForm.raw_en_text}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, raw_en_text: e.target.value }))}
                  className="w-full min-h-[120px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                  placeholder="Оригинальный текст на английском"
                />
              </div>
              <button
                type="button"
                onClick={handleGenerateArticle}
                disabled={editGenerateStatus === 'generating' || !editForm.raw_en_text.trim()}
                className="mt-2 h-9 px-4 rounded-[10px] bg-[#9B6BFF] hover:bg-[#8452FF] text-white text-[13px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {editGenerateStatus === 'generating' ? 'Генерация...' : 'Сгенерировать поля'}
              </button>
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
          </>
        )}
      </div>
    </div>
  );

  const renderFooter = () => {
    if (tab === 'create') {
      return (
        <div className="flex gap-3">
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
      );
    }

    if (tab === 'edit' && selectedId) {
      return (
        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleDeleteArticle}
            disabled={isEditBusy}
            className="h-12 px-6 bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/40 rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            Удалить
          </button>
          <button
            type="button"
            onClick={handleUpdate}
            disabled={!canUpdate}
            className="flex-1 h-12 bg-[#9B6BFF] hover:bg-[#8452FF] text-white rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {editStatus === 'saving' ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      );
    }

    return null;
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="База знаний"
      subtitle="Управление статьями базы знаний"
      width="960px"
      footer={renderFooter()}
    >
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

      {tab === 'create' && renderCreateTab()}
      {tab === 'edit' && renderEditTab()}
    </Drawer>
  );
}

export default KnowledgeBaseDrawer;
