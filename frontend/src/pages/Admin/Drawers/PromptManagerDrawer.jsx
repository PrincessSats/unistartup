import React, { useEffect, useState, useCallback } from 'react';
import Drawer from '../Widgets/Drawer';
import { adminAPI } from '../../../services/api';
import { SkeletonBlock } from '../../../components/LoadingState';

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

function getApiErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  const responseData = err?.response?.data;
  if (typeof responseData === 'string' && responseData.trim()) return responseData;
  if (typeof detail === 'string' && detail.trim()) return detail;
  return fallback;
}

function PromptManagerDrawer({ open, onClose }) {
  const [prompts, setPrompts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState(null);
  const [editorValue, setEditorValue] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');

  const loadPrompts = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await adminAPI.listPrompts();
      setPrompts(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось загрузить шаблоны'));
      setPrompts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    loadPrompts();
    setSelectedPrompt(null);
    setEditorValue('');
    setStatus('idle');
    setError('');
  }, [open, loadPrompts]);

  const handleSelectPrompt = (prompt) => {
    setSelectedPrompt(prompt);
    setEditorValue(prompt.content || '');
  };

  const handleSave = async () => {
    if (!selectedPrompt) return;
    setStatus('saving');
    setError('');
    try {
      const updated = await adminAPI.updatePrompt(selectedPrompt.code, { content: editorValue });
      setPrompts((prev) => prev.map((p) => (p.code === updated.code ? updated : p)));
      setStatus('idle');
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось сохранить шаблон'));
      setStatus('idle');
    }
  };

  const canSave = selectedPrompt && editorValue.trim() && status !== 'saving';

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Prompt Manager"
      subtitle="Управление шаблонами промптов для LLM"
      width="960px"
      footer={
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
            onClick={handleSave}
            disabled={!canSave}
            className="flex-1 h-12 bg-[#9B6BFF] hover:bg-[#8452FF] text-white rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {status === 'saving' ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      }
    >
      {error && (
        <div className="bg-red-500/10 border border-red-500/50 text-red-200 px-4 py-2 rounded-[12px] mb-4 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
        {/* Prompts List */}
        <div className="border border-white/[0.08] rounded-[16px] p-4 max-h-[560px] overflow-y-auto">
          <div className="text-[14px] text-white/60 mb-3">Шаблоны</div>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, index) => (
                <SkeletonBlock key={`prompts-skeleton-${index}`} className="h-20 w-full rounded-[12px]" />
              ))}
            </div>
          ) : prompts.length === 0 ? (
            <div className="text-white/50 text-[14px]">Шаблонов пока нет</div>
          ) : (
            <div className="flex flex-col gap-2">
              {prompts.map((prompt) => (
                <button
                  key={prompt.code}
                  type="button"
                  onClick={() => handleSelectPrompt(prompt)}
                  className={`text-left rounded-[12px] px-3 py-3 border transition ${
                    selectedPrompt?.code === prompt.code
                      ? 'border-[#9B6BFF]/60 bg-[#9B6BFF]/10 text-white'
                      : 'border-white/10 bg-white/[0.02] text-white/70 hover:border-[#9B6BFF]/40'
                  }`}
                >
                  <div className="text-[14px] text-white font-medium">
                    {prompt.title || prompt.code}
                  </div>
                  {prompt.description && (
                    <div className="text-[12px] text-white/40 mt-1 line-clamp-2">
                      {prompt.description}
                    </div>
                  )}
                  <div className="text-[11px] text-white/30 mt-2 uppercase tracking-[0.15em]">
                    {prompt.code}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Editor */}
        <div className="border border-white/[0.08] rounded-[16px] p-5">
          {!selectedPrompt ? (
            <div className="text-white/50 text-[14px] flex items-center justify-center h-full">
              Выберите шаблон для редактирования
            </div>
          ) : (
            <div className="flex flex-col gap-4 h-full">
              <div>
                <div className="text-white text-[18px] mb-1">
                  {selectedPrompt.title}
                </div>
                <div className="text-white/50 text-[13px]">
                  {selectedPrompt.description || 'Без описания'}
                </div>
              </div>

              <div className="flex items-center gap-4 text-[13px]">
                <span className="text-white/60">
                  Обновлён: {formatDateTime(selectedPrompt.updated_at)}
                </span>
                {selectedPrompt.is_overridden && (
                  <span className="px-2 py-1 rounded-full bg-[#9B6BFF]/15 text-[#CBB6FF] text-[11px] uppercase tracking-[0.15em] border border-[#9B6BFF]/30">
                    Изменён
                  </span>
                )}
              </div>

              <div className="flex-1">
                <label className="text-white text-sm mb-2 block">Содержимое</label>
                <textarea
                  value={editorValue}
                  onChange={(e) => setEditorValue(e.target.value)}
                  className="w-full min-h-[400px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30 font-mono text-[13px] leading-relaxed"
                  placeholder="Содержимое промпта..."
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </Drawer>
  );
}

export default PromptManagerDrawer;
