import React, { useMemo, useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import AppIcon from '../components/AppIcon';
import { InlineLoader, PageLoader } from '../components/LoadingState';
import { educationAPI, authAPI } from '../services/api';
import { getEducationCardVisual } from '../utils/educationVisuals';
import { clampChatInput, getChatRemaining } from '../utils/chatInput';
import TaskVariantGenerator from './UserTaskVariants/TaskVariantGenerator';
import VariantList from './UserTaskVariants/VariantList';

const difficultyBadgeClasses = {
  Легко: 'border-[#3FD18A]/30 bg-[#3FD18A]/10 text-[#3FD18A]',
  Средне: 'border-[#F2C94C]/30 bg-[#F2C94C]/10 text-[#F2C94C]',
  Сложно: 'border-[#FF5A6E]/30 bg-[#FF5A6E]/10 text-[#FF5A6E]',
};

const knownAccessTypes = new Set(['vpn', 'vm', 'link', 'file', 'chat', 'just_flag']);

function getStatusLabel(value) {
  if (value === 'solved') return 'Решено';
  if (value === 'in_progress') return 'В процессе';
  return 'Не начато';
}

function normalizeAccessType(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (knownAccessTypes.has(normalized)) return normalized;
  return 'just_flag';
}

function firstHttpUrl(...values) {
  for (const value of values) {
    const text = String(value || '').trim();
    if (text.startsWith('http://') || text.startsWith('https://')) {
      return text;
    }
  }
  return null;
}

function getTaskMaterials(task) {
  return Array.isArray(task?.materials) ? task.materials : [];
}

function getMaterialMeta(material) {
  if (material && typeof material.meta === 'object' && !Array.isArray(material.meta)) {
    return material.meta;
  }
  return {};
}

function getFirstMaterialByType(task, type) {
  return getTaskMaterials(task).find((item) => String(item?.type || '').trim().toLowerCase() === type);
}

function getVmLaunchUrl(task) {
  const material = getFirstMaterialByType(task, 'vm');
  const meta = getMaterialMeta(material);
  return firstHttpUrl(meta.launch_url, meta.connect_url, material?.url, meta.url);
}

function getLinkMaterial(task) {
  const typed = getFirstMaterialByType(task, 'link');
  if (typed) return typed;

  return getTaskMaterials(task).find((item) => {
    const text = [item?.type, item?.name, item?.description]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return text.includes('link') || text.includes('url') || text.includes('перейт') || text.includes('ссылк');
  });
}

function getLinkUrl(task) {
  const material = getLinkMaterial(task);
  const meta = getMaterialMeta(material);
  return firstHttpUrl(meta.target_url, material?.url, meta.url);
}

function getFileMaterial(task) {
  return getFirstMaterialByType(task, 'file');
}

function getMaterialStorageKey(material) {
  const meta = getMaterialMeta(material);
  return String(
    material?.storage_key
      || meta.download_storage_key
      || meta.target_storage_key
      || meta.storage_key
      || ''
  ).trim();
}

function hasExplicitDownloadSource(material) {
  const meta = getMaterialMeta(material);
  const materialType = String(material?.type || '').trim().toLowerCase();
  const storageKey = String(
    material?.storage_key || meta.download_storage_key || meta.storage_key || ''
  ).trim();
  const externalUrl = ['file', 'credentials'].includes(materialType)
    ? firstHttpUrl(meta.download_url, material?.url, meta.url)
    : firstHttpUrl(meta.download_url, meta.url);
  return Boolean(storageKey || externalUrl);
}

function hasMaterialDownloadSource(material) {
  return hasExplicitDownloadSource(material) || Boolean(material?.id);
}

function getVpnDownloadMaterial(task) {
  const materials = getTaskMaterials(task);
  const preferredTypes = ['vpn', 'file', 'credentials'];

  for (const type of preferredTypes) {
    const candidate = materials.find(
      (item) => String(item?.type || '').trim().toLowerCase() === type && hasExplicitDownloadSource(item)
    );
    if (candidate) {
      return candidate;
    }
  }

  for (const type of preferredTypes) {
    const candidate = materials.find(
      (item) => String(item?.type || '').trim().toLowerCase() === type && hasMaterialDownloadSource(item)
    );
    if (candidate) {
      return candidate;
    }
  }

  return materials.find((item) => hasMaterialDownloadSource(item)) || null;
}

function triggerBlobDownload(blob, filename) {
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.setAttribute('download', String(filename || 'download').trim() || 'download');
  link.rel = 'noopener noreferrer';
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
}

function parseFilenameFromContentDisposition(value) {
  const text = String(value || '');
  const utf8Match = text.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]).trim();
    } catch {
      return utf8Match[1].trim();
    }
  }
  const basicMatch = text.match(/filename="?([^";]+)"?/i);
  return basicMatch?.[1]?.trim() || null;
}

async function parseDownloadErrorMessage(err, fallbackMessage) {
  const blob = err?.response?.data;
  if (blob && typeof blob.text === 'function') {
    try {
      const rawText = await blob.text();
      const payload = JSON.parse(rawText);
      if (typeof payload?.detail === 'string' && payload.detail.trim()) {
        return payload.detail;
      }
    } catch {
      // noop
    }
  }
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  return fallbackMessage;
}

function formatTimeLeft(value) {
  if (!value) return 'Сессия не активна';
  const target = new Date(value).getTime();
  if (Number.isNaN(target)) return 'Сессия не активна';
  const diffMs = target - Date.now();
  if (diffMs <= 0) return 'Сессия истекла';
  const totalMinutes = Math.floor(diffMs / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours > 0) return `${hours} ч ${minutes} мин`;
  return `${minutes} мин`;
}

function isObjectStorageUrl(urlValue) {
  const value = String(urlValue || '').trim();
  if (!value) return false;
  try {
    const parsed = new URL(value);
    return parsed.hostname.includes('storage.yandexcloud.net');
  } catch {
    return value.includes('storage.yandexcloud.net');
  }
}

function getFileBadge(material) {
  const meta = getMaterialMeta(material);
  const explicit = String(meta.badge || meta.file_ext || meta.extension || '').trim();
  if (explicit) return explicit.toUpperCase();

  const fileName = String(material?.name || '').trim();
  const parts = fileName.split('.').filter(Boolean);
  if (parts.length > 1) {
    return String(parts[parts.length - 1]).slice(0, 4).toUpperCase();
  }

  return 'FILE';
}

function getFileSizeLabel(material) {
  const meta = getMaterialMeta(material);
  const explicit = [meta.size_label, meta.file_size_label, meta.size_human, meta.size]
    .map((value) => String(value || '').trim())
    .find(Boolean);

  if (explicit) return explicit;

  const description = String(material?.description || '');
  const sizeMatch = description.match(/(\d+(?:[.,]\d+)?\s*(?:КБ|МБ|ГБ|KB|MB|GB))/i);
  return sizeMatch ? sizeMatch[1] : null;
}

function extractFlagTokenContent(value) {
  const text = String(value || '').trim();
  if (!text) return '';
  const match = text.match(/\{([^{}]+)\}/);
  return match?.[1]?.trim() || text;
}

export default function EducationTask() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [flagValue, setFlagValue] = useState('');
  const [submitMessage, setSubmitMessage] = useState('');
  const [submitLoading, setSubmitLoading] = useState(false);
  const [downloadLoadingId, setDownloadLoadingId] = useState(null);
  const [activeHint, setActiveHint] = useState(null);
  const [chatSession, setChatSession] = useState(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [chatSending, setChatSending] = useState(false);
  const [chatAborting, setChatAborting] = useState(false);
  const [startLoading, setStartLoading] = useState(false);
  const [generatorOpen, setGeneratorOpen] = useState(false);
  const chatMessagesRef = useRef(null);

  useEffect(() => {
    let isMounted = true;

    const fetchTask = async () => {
      if (isMounted) {
        setLoading(true);
      }
      try {
        setError('');
        const data = await educationAPI.getPracticeTask(id);
        if (!isMounted) return;
        setTask(data);
      } catch (err) {
        console.error('Не удалось загрузить практическую задачу', err);
        if (!isMounted) return;
        const detail = err?.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Не удалось загрузить задачу');
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    if (id) {
      fetchTask();
    } else {
      setLoading(false);
      setError('Не указан идентификатор задачи');
    }

    return () => {
      isMounted = false;
    };
  }, [id]);

  const difficultyClass = useMemo(() => (
    difficultyBadgeClasses[task?.difficulty_label] || difficultyBadgeClasses.Средне
  ), [task?.difficulty_label]);
  const heroVisual = useMemo(() => getEducationCardVisual(task), [task]);
  const accessType = useMemo(() => normalizeAccessType(task?.access_type), [task?.access_type]);
  const isChatTask = accessType === 'chat';
  const chatInputMaxChars = Number(
    chatSession?.limits?.user_message_max_chars
      ?? task?.chat_limits?.user_message_max_chars
      ?? 150
  );
  const chatInputRemaining = getChatRemaining(chatInput, chatInputMaxChars);

  const vmLaunchUrl = useMemo(() => getVmLaunchUrl(task), [task]);
  const linkMaterial = useMemo(() => getLinkMaterial(task), [task]);
  const linkUrl = useMemo(() => getLinkUrl(task), [task]);
  const fileMaterial = useMemo(() => getFileMaterial(task), [task]);
  const vpnDownloadMaterial = useMemo(() => getVpnDownloadMaterial(task), [task]);

  useEffect(() => {
    if (!task?.id || !isChatTask) {
      setChatSession(null);
      setChatInput('');
      setChatError('');
      setChatLoading(false);
      return;
    }
    let isCancelled = false;
    const loadChatSession = async () => {
      setChatLoading(true);
      setChatError('');
      try {
        const data = await educationAPI.getPracticeTaskChatSession(task.id);
        if (isCancelled) return;
        setChatSession(data?.session || null);
      } catch (err) {
        if (isCancelled) return;
        const detail = err?.response?.data?.detail;
        setChatSession(null);
        setChatError(typeof detail === 'string' ? detail : 'Не удалось загрузить чат задачи');
      } finally {
        if (!isCancelled) {
          setChatLoading(false);
        }
      }
    };
    loadChatSession();
    return () => {
      isCancelled = true;
    };
  }, [task?.id, isChatTask]);

  useEffect(() => {
    if (!isChatTask) return;
    const container = chatMessagesRef.current;
    if (!container) return;
    const frame = window.requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [isChatTask, chatSession?.messages?.length, chatSending, chatLoading]);

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setSubmitMessage('Ссылка на задание скопирована');
    } catch {
      setSubmitMessage('Не удалось скопировать ссылку');
    }
  };

  const handleStartTask = async () => {
    if (startLoading || !task?.id) return;
    try {
      setStartLoading(true);
      await educationAPI.startPracticeTask(task.id);
      setTask((prev) => ({ ...prev, my_status: 'in_progress' }));
    } catch (err) {
      console.error('Не удалось начать задание', err);
    } finally {
      setStartLoading(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const normalized = isChatTask
      ? extractFlagTokenContent(flagValue)
      : flagValue.trim();
    if (!normalized || submitLoading || !task?.id) return;

    try {
      setSubmitLoading(true);
      setSubmitMessage('');
      const response = await educationAPI.submitPracticeFlag(task.id, { flag: normalized });
      setSubmitMessage(response?.message || 'Ответ получен');
      setFlagValue('');
      const refreshed = await educationAPI.getPracticeTask(task.id);
      setTask(refreshed);
      if (isChatTask && response?.is_correct) {
        try {
          const chatPayload = await educationAPI.getPracticeTaskChatSession(task.id);
          setChatSession(chatPayload?.session || null);
        } catch {
          // Keep flag submit successful even if chat refresh failed.
        }
      }
    } catch (err) {
      console.error('Не удалось отправить флаг', err);
      const detail = err?.response?.data?.detail;
      setSubmitMessage(typeof detail === 'string' ? detail : 'Не удалось отправить флаг');
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleSendChatMessage = async () => {
    const trimmed = chatInput.trim();
    if (!task?.id || !isChatTask || !trimmed || chatSending || chatAborting) return;
    const optimisticCreatedAt = new Date().toISOString();

    try {
      setChatSession((prev) => {
        const fallbackTtlMinutes = Number(
          prev?.limits?.session_ttl_minutes
            ?? task?.chat_limits?.session_ttl_minutes
            ?? 180
        );
        const fallbackLimits = {
          user_message_max_chars: Number(
            prev?.limits?.user_message_max_chars
              ?? task?.chat_limits?.user_message_max_chars
              ?? 150
          ),
          model_max_output_tokens: Number(
            prev?.limits?.model_max_output_tokens
              ?? task?.chat_limits?.model_max_output_tokens
              ?? 256
          ),
          session_ttl_minutes: fallbackTtlMinutes,
        };
        const base = prev || {
          session_id: 0,
          status: 'active',
          read_only: false,
          expires_at: new Date(Date.now() + fallbackTtlMinutes * 60 * 1000).toISOString(),
          limits: fallbackLimits,
          messages: [],
        };
        return {
          ...base,
          read_only: false,
          messages: [
            ...(Array.isArray(base.messages) ? base.messages : []),
            { role: 'user', content: trimmed, created_at: optimisticCreatedAt },
          ],
        };
      });
      setChatInput('');
      setChatSending(true);
      setChatError('');
      const response = await educationAPI.sendPracticeTaskChatMessage(task.id, { message: trimmed });
      setChatSession(response?.session || null);
    } catch (err) {
      setChatSession((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          messages: (prev.messages || []).filter(
            (item) => !(item.role === 'user' && item.content === trimmed && item.created_at === optimisticCreatedAt)
          ),
        };
      });
      setChatInput(trimmed);
      const detail = err?.response?.data?.detail;
      setChatError(typeof detail === 'string' ? detail : 'Не удалось отправить сообщение');
    } finally {
      setChatSending(false);
    }
  };

  const handleRestartPracticeChatSession = async () => {
    if (!task?.id || !isChatTask || chatLoading || chatSending || chatAborting) return;

    try {
      setChatLoading(true);
      setChatError('');
      const response = await educationAPI.restartPracticeTaskChatSession(task.id);
      setChatSession(response?.session || null);
      setChatInput('');
      setSubmitMessage('Новая чат-сессия запущена');
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setChatError(typeof detail === 'string' ? detail : 'Не удалось перезапустить чат-сессию');
    } finally {
      setChatLoading(false);
    }
  };

  const handleAbortPracticeChatSession = async () => {
    if (!task?.id || !isChatTask || chatLoading || chatSending || chatAborting) return;

    try {
      setChatAborting(true);
      setChatError('');
      await educationAPI.abortPracticeTaskChatSession(task.id);
      setChatSession(null);
      setChatInput('');
      setSubmitMessage('Чат прерван. Сессия и сообщения удалены.');
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setChatError(typeof detail === 'string' ? detail : 'Не удалось прервать чат');
    } finally {
      setChatAborting(false);
    }
  };

  const handleMaterialDownload = async (material) => {
    if (!task?.id || !material) return;

    const materialId = material?.id;
    const loadingKey = materialId ?? `fallback-${String(material?.type || 'material')}`;

    try {
      setDownloadLoadingId(loadingKey);
      setSubmitMessage('');

      if (!materialId) {
        throw new Error('Материал не поддерживает безопасное скачивание');
      }
      const response = await educationAPI.downloadPracticeMaterialContent(task.id, materialId);
      const disposition = response?.headers?.['content-disposition'] || '';
      const resolvedFilename = parseFilenameFromContentDisposition(disposition) || material.name || 'download';
      triggerBlobDownload(response.data, resolvedFilename);
    } catch (err) {
      console.error('Не удалось скачать материал', err);
      const message = await parseDownloadErrorMessage(err, 'Не удалось начать скачивание');
      setSubmitMessage(message);
    } finally {
      setDownloadLoadingId(null);
    }
  };

  if (loading) {
    return <PageLoader label="Загружаем задачу..." variant="education-task" />;
  }

  if (error) {
    return <div className="font-sans-figma text-rose-300">{error}</div>;
  }

  if (!task) {
    return null;
  }

  const hintButtons = Array.from({ length: task.hints_count || 0 }, (_, index) => index + 1);
  const activeHintText = activeHint !== null ? (task.hints?.[activeHint] || '') : '';
  const linkActionLabel = String(linkMaterial?.name || 'Перейти к заданию').trim() || 'Перейти к заданию';
  const fileDownloadEnabled = Boolean(fileMaterial?.id);
  const fileDownloadLoadingKey = fileMaterial?.id ?? 'fallback-file';
  const isFileDownloading = downloadLoadingId === fileDownloadLoadingKey;
  const vpnHowToConnectUrl = firstHttpUrl(task?.vpn?.how_to_connect_url);
  const vpnDownloadEnabled = Boolean(vpnDownloadMaterial?.id);
  const vpnDownloadLoadingKey = vpnDownloadMaterial?.id ?? 'fallback-vpn';
  const isVpnDownloading = downloadLoadingId === vpnDownloadLoadingKey;
  const linkHasStorageKey = Boolean(getMaterialStorageKey(linkMaterial));
  const linkCanOpenDirect = Boolean(linkUrl) && !isObjectStorageUrl(linkUrl);
  const linkActionEnabled = Boolean(linkMaterial && (linkHasStorageKey || linkCanOpenDirect));
  const linkLoadingKey = linkMaterial?.id ?? 'fallback-link';
  const isLinkLoading = downloadLoadingId === linkLoadingKey;

  return (
    <div className="font-sans-figma text-white">
      <div className={`grid grid-cols-1 gap-4 transition-all duration-300 2xl:grid-cols-[minmax(0,1fr)_560px] ${activeHint !== null ? 'blur-sm' : ''}`}>
        <section>
          <div className="overflow-hidden rounded-[20px] border border-white/[0.06] bg-white/[0.03]">
            <div
              className="relative overflow-hidden px-6 pb-6 pt-4 md:px-8 md:pb-8 md:pt-6"
              style={{ background: 'linear-gradient(86.5deg, #563BA6 1.28%, #9F63FF 98.48%)' }}
            >
              <img
                src={heroVisual}
                alt=""
                className="pointer-events-none absolute right-0 top-0 h-full w-auto object-contain opacity-95"
              />

              <button
                type="button"
                onClick={() => navigate('/education')}
                className="relative inline-flex items-center gap-2 text-[13px] text-white/70 transition hover:text-white"
              >
                <AppIcon name="arrow-left" className="h-4 w-4" />
                Назад
              </button>

              <div className="relative mt-6 flex flex-wrap items-center gap-2">
                <span className="rounded-[8px] border border-white/20 bg-white/10 px-2.5 py-1 text-[12px] text-white/90">
                  {task.category}
                </span>
                <span className={`rounded-[8px] border px-2.5 py-1 text-[12px] ${difficultyClass}`}>
                  {task.difficulty_label}
                </span>
                <span className="rounded-[8px] border border-white/20 bg-white/10 px-2.5 py-1 text-[12px] text-white/80">
                  {getStatusLabel(task.my_status)}
                </span>
              </div>

              <h1 className="relative mt-4 max-w-[560px] text-[30px] leading-[36px] tracking-[0.02em] sm:text-[39px] sm:leading-[44px] md:max-w-[460px]">
                {task.title}
              </h1>

              <button
                type="button"
                onClick={handleShare}
                className="relative mt-6 rounded-[8px] border border-white/20 bg-white/10 px-4 py-2 text-[13px] text-white/90 transition hover:border-white/40"
              >
                Поделиться
              </button>
            </div>

            <div className="bg-[#111118] px-6 py-8 md:px-8">
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <p className="max-w-[650px] whitespace-pre-line text-[18px] leading-[24px] tracking-[0.04em] text-white/70">
                  {task.participant_description || task.story || 'Описание задачи пока не добавлено.'}
                </p>
                <div className="shrink-0 text-right">
                  <p className="text-[18px] leading-[24px] tracking-[0.04em] text-white/65">Подсказки</p>
                  {hintButtons.length > 0 ? (
                    <div className="mt-2 flex items-center justify-end gap-1">
                      {hintButtons.map((number, index) => (
                        <button
                          key={number}
                          type="button"
                          onClick={() => setActiveHint(index)}
                          className="rounded-[6px] border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[13px] text-white/70 transition hover:border-[#9B6BFF]/50 hover:bg-[#9B6BFF]/15 hover:text-white"
                        >
                          {number}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-[13px] text-white/40">Нет подсказок</p>
                  )}
                </div>
              </div>


              {accessType === 'vm' && (
                <button
                  type="button"
                  disabled={!vmLaunchUrl}
                  onClick={() => {
                    if (vmLaunchUrl && !isObjectStorageUrl(vmLaunchUrl)) {
                      window.open(vmLaunchUrl, '_blank', 'noopener,noreferrer');
                    } else {
                      setSubmitMessage('Ссылка недоступна');
                    }
                  }}
                  className="mt-6 h-12 rounded-[10px] bg-[#9B6BFF] px-5 text-[18px] text-white transition hover:bg-[#A97CFF] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  Запустить машину
                </button>
              )}

              {accessType === 'link' && (
                <button
                  type="button"
                  disabled={!linkActionEnabled || isLinkLoading}
                  onClick={async () => {
                    if (!linkMaterial) return;
                    if (linkHasStorageKey) {
                      await handleMaterialDownload(linkMaterial);
                      return;
                    }
                    if (linkCanOpenDirect && linkUrl) {
                      window.open(linkUrl, '_blank', 'noopener,noreferrer');
                    } else {
                      setSubmitMessage('Ссылка недоступна');
                    }
                  }}
                  className="mt-6 text-left text-[20px] leading-[24px] tracking-[0.03em] text-white/85 underline-offset-4 transition hover:text-white hover:underline disabled:cursor-not-allowed disabled:text-white/35 disabled:no-underline"
                >
                  {isLinkLoading ? 'Открытие...' : linkActionLabel}
                </button>
              )}

              {accessType === 'file' && fileMaterial && (
                <div className="mt-6 flex h-[76px] items-center gap-3 rounded-[12px] border border-white/[0.09] px-4">
                  <div className="rounded-[8px] bg-[#2FCF95] px-2 py-1 text-[12px] tracking-[0.04em] text-white">
                    {getFileBadge(fileMaterial)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[16px] tracking-[0.02em] text-white">
                      {fileMaterial.name || 'Файл'}
                      {getFileSizeLabel(fileMaterial) && (
                        <span className="ml-2 text-white/50">{getFileSizeLabel(fileMaterial)}</span>
                      )}
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={!fileDownloadEnabled || isFileDownloading}
                    onClick={() => {
                      if (!fileMaterial) return;
                      handleMaterialDownload(fileMaterial);
                    }}
                    className="rounded-[8px] border border-white/[0.12] bg-white/[0.03] px-4 py-2 text-[14px] text-white/85 transition hover:border-[#9B6BFF]/60 hover:bg-[#9B6BFF]/20 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    {isFileDownloading ? 'Скачивание...' : 'Скачать'}
                  </button>
                </div>
              )}

              {accessType === 'vpn' && task.connection_ip && (
                <p className="mt-6 text-[18px] leading-[24px] tracking-[0.04em] text-white/80">
                  IP: <span className="text-white">{task.connection_ip}</span>
                </p>
              )}

              {isChatTask && (
                <div className="mt-6 rounded-[12px] border border-white/[0.09] bg-white/[0.03] p-4">
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <div className="text-[16px] leading-[20px] text-white">Чат с ассистентом</div>
                    <div className="flex items-center gap-2">
                      <div className="text-[12px] text-white/60">{formatTimeLeft(chatSession?.expires_at)}</div>
                      {chatSession?.session_id && !chatSession?.read_only ? (
                        <button
                          type="button"
                          onClick={handleAbortPracticeChatSession}
                          disabled={chatLoading || chatSending || chatAborting}
                          className="inline-flex h-8 items-center rounded-[8px] border border-rose-400/40 bg-rose-500/10 px-3 text-[12px] text-rose-200 transition-colors hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {chatAborting ? 'Прерывание...' : 'Прервать Чат'}
                        </button>
                      ) : null}
                    </div>
                  </div>
                  <div
                    ref={chatMessagesRef}
                    className="max-h-[380px] overflow-y-auto rounded-[10px] border border-white/[0.06] bg-[#0B0A10]/60 p-3 space-y-2"
                  >
                    {chatLoading ? (
                      <InlineLoader label="Загрузка чата..." />
                    ) : chatSession?.messages?.length ? (
                      chatSession.messages.map((item, index) => (
                        <div
                          key={`${item.created_at}-${index}`}
                          className={`rounded-[10px] px-3 py-2 text-[13px] leading-[18px] ${
                            item.role === 'assistant'
                              ? 'bg-white/[0.06] text-white/85'
                              : 'bg-[#9B6BFF]/20 text-white'
                          }`}
                        >
                          <div className="text-[11px] uppercase tracking-[0.08em] opacity-60 mb-1">
                            {item.role === 'assistant' ? 'Ассистент' : 'Вы'}
                          </div>
                          <div className="whitespace-pre-wrap break-words">{item.content}</div>
                        </div>
                      ))
                    ) : (
                      <div className="text-[13px] text-white/50">Пока сообщений нет</div>
                    )}
                    {chatSending ? (
                      <div className="rounded-[10px] px-3 py-2 text-[13px] leading-[18px] bg-white/[0.06] text-white/85 animate-pulse">
                        <div className="text-[11px] uppercase tracking-[0.08em] opacity-60 mb-1">
                          Ассистент
                        </div>
                        <div>Печатает ответ...</div>
                      </div>
                    ) : null}
                  </div>

                  <div className="mt-3">
                    <textarea
                      value={chatInput}
                      onChange={(event) => {
                        setChatInput(clampChatInput(event.target.value, chatInputMaxChars));
                      }}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' && !event.shiftKey) {
                          event.preventDefault();
                          handleSendChatMessage();
                        }
                      }}
                      disabled={chatLoading || chatSending || chatAborting || chatSession?.read_only}
                      className="w-full min-h-[120px] rounded-[10px] border border-white/[0.09] bg-white/[0.02] px-3 py-2 text-[14px] text-white placeholder:text-white/50 focus:outline-none focus:border-white/30 disabled:opacity-60"
                      placeholder="Напишите сообщение ассистенту"
                    />
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <span className="text-[12px] text-white/55">{chatInputRemaining}/{chatInputMaxChars}</span>
                      <button
                        type="button"
                        onClick={handleSendChatMessage}
                        disabled={chatLoading || chatSending || chatAborting || chatSession?.read_only || !chatInput.trim()}
                        className="inline-flex h-10 items-center rounded-[10px] bg-white/[0.08] px-4 text-[14px] text-white transition-colors hover:bg-white/[0.12] disabled:opacity-60 disabled:cursor-not-allowed"
                      >
                        Отправить в чат
                      </button>
                    </div>
                    {chatSession?.read_only ? (
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <div className="text-[12px] text-emerald-300">
                          Сессия завершена после успешной сдачи флага.
                        </div>
                        <button
                          type="button"
                          onClick={handleRestartPracticeChatSession}
                          disabled={chatLoading || chatSending || chatAborting}
                          className="inline-flex h-8 items-center rounded-[8px] border border-emerald-300/40 bg-emerald-400/10 px-3 text-[12px] text-emerald-200 transition-colors hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Пройти задание еще раз
                        </button>
                      </div>
                    ) : null}
                    {chatError ? (
                      <div className="mt-2 text-[12px] text-rose-300">{chatError}</div>
                    ) : null}
                  </div>
                </div>
              )}

              {authAPI.isAuthenticated() ? (
                task?.my_status === 'not_started' ? (
                  <div className="mt-6 flex items-center justify-center py-8">
                    <button
                      onClick={handleStartTask}
                      disabled={startLoading}
                      className="rounded-[14px] bg-[#9B6BFF] px-10 py-5 text-[20px] leading-[24px] tracking-[0.4px] text-white transition hover:bg-[#8452FF] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {startLoading ? 'Начинаем...' : 'Начать задание'}
                    </button>
                  </div>
                ) : (
                  <form onSubmit={handleSubmit} className="mt-6 flex flex-wrap gap-2">
                    <input
                      type="text"
                      value={flagValue}
                      onChange={(event) => setFlagValue(event.target.value)}
                      placeholder={isChatTask ? 'Введи только код между { }' : 'Введи флаг сюда'}
                      className="h-14 min-w-[200px] flex-1 rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 text-[16px] text-white placeholder:text-white/35 outline-none transition focus:border-[#9B6BFF]/70 sm:min-w-[260px]"
                    />
                    <button
                      type="submit"
                      disabled={submitLoading || !flagValue.trim()}
                      className="h-14 rounded-[10px] bg-white/10 px-6 text-[18px] text-white transition hover:bg-[#9B6BFF]/25 disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      {submitLoading ? 'Отправка...' : 'Сдать флаг'}
                    </button>
                  </form>
                )
              ) : (
                <div className="mt-6 flex items-center gap-4 rounded-[12px] border border-[#9B6BFF]/30 bg-[#9B6BFF]/10 px-5 py-4">
                  <span className="flex-1 text-[16px] leading-[20px] text-white/80">
                    Войдите в аккаунт, чтобы сдать флаг
                  </span>
                  <a
                    href="#/login"
                    className="inline-flex h-10 items-center rounded-[8px] bg-[#9B6BFF] px-5 text-[15px] text-white transition-colors hover:bg-[#8452FF]"
                  >
                    Войти
                  </a>
                </div>
              )}

              {submitMessage && (
                <p className="mt-3 text-[14px] text-white/80">{submitMessage}</p>
              )}
            </div>
          </div>
        </section>

        <aside className="flex flex-col gap-4">
          {/* UGC Variants Section (for Crypto/Forensics/Web) */}
          {task?.category && ['Crypto', 'Forensics', 'Web'].includes(task.category) && (
            <div className="rounded-[20px] border border-white/[0.06] bg-white/[0.03] px-6 py-5">
              <div className="flex items-start justify-between gap-3 mb-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <AppIcon name="variants" className="w-5 h-5 text-[#9B6BFF]" />
                    <h2 className="text-base font-bold text-white">
                      Варианты от пользователей
                    </h2>
                  </div>
                  {/* Parent task link (if this is a UGC task) */}
                  {task?.parent_task_id && (
                    <a
                      href={`#/education/${task.parent_task_id}`}
                      className="text-sm text-white/60 hover:text-[#9B6BFF] hover:underline transition-colors block mt-1"
                      onClick={(e) => {
                        e.preventDefault();
                        navigate(`/education/${task.parent_task_id}`);
                      }}
                    >
                      {task.title}
                    </a>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => setGeneratorOpen(true)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#9B6BFF] hover:bg-[#A97CFF]
                           rounded-[8px] text-xs font-medium text-white transition shrink-0"
                >
                  <AppIcon name="plus" className="h-3.5 w-3.5" />
                  Создать
                </button>
              </div>
              <VariantList taskId={task.id} parentTaskId={task.parent_task_id} parentTaskTitle={task.title} />
            </div>
          )}
          <div className="rounded-[20px] border border-white/[0.06] bg-white/[0.03] px-6 py-5">
            <div className="flex items-center justify-between text-[16px] leading-[20px] tracking-[0.04em] text-white/65">
              <span>{task.passed_users_count} прошли</span>
              <span className="inline-flex items-center gap-2 font-mono-figma text-white">
                <AppIcon name="star" className="h-4 w-4 text-white/80" />
                {task.points}
              </span>
            </div>
            <p className="mt-4 text-[14px] text-white/50">
              Флаги: {task.solved_flags_count}/{task.required_flags_count}
            </p>
          </div>

          {accessType === 'vpn' && (
            <div className="rounded-[20px] border border-white/[0.06] bg-white/[0.03] px-6 py-6">
              <h2 className="text-[26px] leading-[32px] tracking-[0.02em]">VPN-конфигурация</h2>
              <div className="mt-6 space-y-2 text-[18px] leading-[24px] tracking-[0.04em] text-white">
                <p>
                  <span className="text-white/50">IP-адрес конфигурации:</span>{' '}
                  {task?.vpn?.config_ip || '—'}
                </p>
                <p>
                  <span className="text-white/50">Разрешенные IP-адреса:</span>{' '}
                  {task?.vpn?.allowed_ips || '—'}
                </p>
                <p>
                  <span className="text-white/50">Дата создания конфигурации:</span>{' '}
                  {task?.vpn?.created_at || '—'}
                </p>
              </div>

              <div className="mt-8 grid grid-cols-1 gap-2 md:grid-cols-2">
                <button
                  type="button"
                  disabled={!vpnHowToConnectUrl}
                  onClick={() => {
                    if (vpnHowToConnectUrl && !isObjectStorageUrl(vpnHowToConnectUrl)) {
                      window.open(vpnHowToConnectUrl, '_blank', 'noopener,noreferrer');
                    } else {
                      setSubmitMessage('Ссылка недоступна');
                    }
                  }}
                  className="h-14 rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 text-[18px] text-white/85 transition hover:border-[#9B6BFF]/60 hover:bg-[#9B6BFF]/20 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  Как подключить
                </button>
                <button
                  type="button"
                  disabled={!vpnDownloadEnabled || isVpnDownloading}
                  onClick={() => {
                    if (vpnDownloadMaterial) {
                      handleMaterialDownload(vpnDownloadMaterial);
                    }
                  }}
                  className="h-14 rounded-[10px] bg-[#9B6BFF] px-4 text-[18px] text-white transition hover:bg-[#A97CFF] disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {isVpnDownloading ? 'Скачивание...' : 'Скачать'}
                </button>
              </div>
            </div>
          )}
        </aside>
      </div>

      {activeHint !== null && activeHintText && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="relative w-full max-w-[470px] overflow-hidden rounded-[20px] bg-gradient-to-b from-[#563BA6] to-[#2a1f5c]">
            <button
              type="button"
              onClick={() => setActiveHint(null)}
              className="absolute right-6 top-6 z-10 text-white/70 transition hover:text-white"
            >
              <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <div className="aspect-video overflow-hidden bg-gradient-to-br from-[#9B6BFF] to-[#6B4BA8]">
              <div className="flex h-full items-center justify-center">
                <svg className="h-32 w-32 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5a4 4 0 100-8 4 4 0 000 8z" />
                </svg>
              </div>
            </div>

            <div className="px-6 py-6">
              <h3 className="text-[20px] font-semibold leading-[28px] text-white">
                Подсказка {activeHint + 1}
              </h3>
              <p className="mt-4 whitespace-pre-line text-[16px] leading-[24px] text-white/85">
                {activeHintText}
              </p>

              <button
                type="button"
                onClick={() => setActiveHint(null)}
                className="mt-6 w-full rounded-[10px] bg-[#9B6BFF] px-4 py-3 text-[16px] font-medium text-white transition hover:bg-[#A97CFF]"
              >
                Понятно
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Task Variant Generator */}
      <TaskVariantGenerator
        isOpen={generatorOpen}
        onClose={() => setGeneratorOpen(false)}
        parentTask={task}
        onGenerationComplete={() => {
          // Refresh could be implemented here if needed
        }}
      />
    </div>
  );
}
