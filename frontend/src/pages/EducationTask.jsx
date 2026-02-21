import React, { useMemo, useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import AppIcon from '../components/AppIcon';
import { educationAPI } from '../services/api';
import { getEducationCardVisual } from '../utils/educationVisuals';

const difficultyBadgeClasses = {
  Легко: 'border-[#3FD18A]/30 bg-[#3FD18A]/10 text-[#3FD18A]',
  Средне: 'border-[#F2C94C]/30 bg-[#F2C94C]/10 text-[#F2C94C]',
  Сложно: 'border-[#FF5A6E]/30 bg-[#FF5A6E]/10 text-[#FF5A6E]',
};

const knownAccessTypes = new Set(['vpn', 'vm', 'link', 'file', 'just_flag']);

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

function getFileDownloadUrl(material) {
  const meta = getMaterialMeta(material);
  return firstHttpUrl(meta.download_url, material?.url, meta.url);
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

function triggerDownload(url, filename) {
  const link = document.createElement('a');
  link.href = url;
  if (filename) {
    link.setAttribute('download', filename);
  }
  link.rel = 'noopener noreferrer';
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
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
  const [activeHint, setActiveHint] = useState(0);

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
        setActiveHint(0);
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

  const vmLaunchUrl = useMemo(() => getVmLaunchUrl(task), [task]);
  const linkMaterial = useMemo(() => getLinkMaterial(task), [task]);
  const linkUrl = useMemo(() => getLinkUrl(task), [task]);
  const fileMaterial = useMemo(() => getFileMaterial(task), [task]);
  const fileDownloadUrl = useMemo(() => getFileDownloadUrl(fileMaterial), [fileMaterial]);
  const vpnDownloadMaterial = useMemo(() => getVpnDownloadMaterial(task), [task]);

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setSubmitMessage('Ссылка на задание скопирована');
    } catch {
      setSubmitMessage('Не удалось скопировать ссылку');
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const normalized = flagValue.trim();
    if (!normalized || submitLoading || !task?.id) return;

    try {
      setSubmitLoading(true);
      setSubmitMessage('');
      const response = await educationAPI.submitPracticeFlag(task.id, { flag: normalized });
      setSubmitMessage(response?.message || 'Ответ получен');
      setFlagValue('');
      const refreshed = await educationAPI.getPracticeTask(task.id);
      setTask(refreshed);
    } catch (err) {
      console.error('Не удалось отправить флаг', err);
      const detail = err?.response?.data?.detail;
      setSubmitMessage(typeof detail === 'string' ? detail : 'Не удалось отправить флаг');
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleMaterialDownload = async (material) => {
    if (!task?.id || !material) return;

    const materialId = material?.id;
    const loadingKey = materialId ?? `fallback-${String(material?.type || 'material')}`;

    try {
      setDownloadLoadingId(loadingKey);
      setSubmitMessage('');

      if (materialId) {
        const response = await educationAPI.getPracticeMaterialDownload(task.id, materialId);
        if (!response?.url) {
          throw new Error('Ссылка на скачивание не получена');
        }
        triggerDownload(response.url, response.filename || material.name || 'download');
        return;
      }

      const meta = getMaterialMeta(material);
      const materialType = String(material?.type || '').trim().toLowerCase();
      const fallbackUrl = ['file', 'credentials'].includes(materialType)
        ? firstHttpUrl(meta.download_url, material?.url, meta.url)
        : firstHttpUrl(meta.download_url, meta.url);
      if (!fallbackUrl) {
        throw new Error('Для материала не настроено скачивание');
      }
      triggerDownload(fallbackUrl, material?.name || 'download');
    } catch (err) {
      console.error('Не удалось скачать материал', err);
      setSubmitMessage('Не удалось начать скачивание');
    } finally {
      setDownloadLoadingId(null);
    }
  };

  if (loading) {
    return <div className="font-sans-figma text-white/60">Загрузка задачи...</div>;
  }

  if (error) {
    return <div className="font-sans-figma text-rose-300">{error}</div>;
  }

  if (!task) {
    return null;
  }

  const hintButtons = Array.from({ length: task.hints_count || 0 }, (_, index) => index + 1);
  const activeHintText = task.hints?.[activeHint] || '';
  const linkActionLabel = String(linkMaterial?.name || 'Перейти к заданию').trim() || 'Перейти к заданию';
  const fileDownloadEnabled = Boolean((fileMaterial && fileMaterial.id) || fileDownloadUrl);
  const fileDownloadLoadingKey = fileMaterial?.id ?? 'fallback-file';
  const isFileDownloading = downloadLoadingId === fileDownloadLoadingKey;
  const vpnHowToConnectUrl = firstHttpUrl(task?.vpn?.how_to_connect_url);
  const vpnFallbackDownloadUrl = firstHttpUrl(task?.vpn?.download_url);
  const vpnDownloadEnabled = Boolean(vpnDownloadMaterial || vpnFallbackDownloadUrl);
  const vpnDownloadLoadingKey = vpnDownloadMaterial?.id ?? 'fallback-vpn';
  const isVpnDownloading = downloadLoadingId === vpnDownloadLoadingKey;
  const linkActionEnabled = Boolean(linkMaterial && (linkMaterial.id || linkUrl));
  const linkLoadingKey = linkMaterial?.id ?? 'fallback-link';
  const isLinkLoading = downloadLoadingId === linkLoadingKey;

  return (
    <div className="font-sans-figma text-white">
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_560px]">
        <section>
          <div className="overflow-hidden rounded-[20px] border border-white/[0.06] bg-white/[0.03]">
            <div
              className="relative overflow-hidden px-6 pb-6 pt-4 md:px-8 md:pb-8 md:pt-6"
              style={{ background: 'linear-gradient(86.5deg, #563BA6 1.28%, #9F63FF 98.48%)' }}
            >
              <img
                src={heroVisual}
                alt=""
                className="pointer-events-none absolute right-[-16px] top-[-8px] h-[138px] w-[242px] object-contain opacity-95 md:hidden"
              />
              <div className="pointer-events-none absolute left-[52.2%] top-[20px] hidden h-[173px] w-[304px] md:block">
                <img
                  src={heroVisual}
                  alt=""
                  className="h-full w-full object-contain opacity-95"
                />
              </div>

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

              <h1 className="relative mt-4 max-w-[560px] text-[39px] leading-[44px] tracking-[0.02em] md:max-w-[460px]">
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
              <div className="flex items-start justify-between gap-4">
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
                          className={`rounded-[6px] border px-2.5 py-1 text-[13px] ${
                            activeHint === index
                              ? 'border-[#9B6BFF]/70 bg-[#9B6BFF]/25 text-white'
                              : 'border-white/10 bg-white/[0.03] text-white/70'
                          }`}
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

              {activeHintText && (
                <p className="mt-4 whitespace-pre-line rounded-[10px] border border-white/10 bg-white/[0.03] px-4 py-3 text-[14px] text-white/70">
                  {activeHintText}
                </p>
              )}

              {accessType === 'vm' && (
                <button
                  type="button"
                  disabled={!vmLaunchUrl}
                  onClick={() => vmLaunchUrl && window.open(vmLaunchUrl, '_blank', 'noopener,noreferrer')}
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
                    if (linkMaterial.id) {
                      try {
                        setDownloadLoadingId(linkLoadingKey);
                        const response = await educationAPI.getPracticeMaterialDownload(task.id, linkMaterial.id);
                        if (!response?.url) {
                          throw new Error('Ссылка недоступна');
                        }
                        if (response.expires_in === 0 && !response.filename) {
                          window.open(response.url, '_blank', 'noopener,noreferrer');
                          return;
                        }
                        triggerDownload(response.url, response.filename || linkActionLabel);
                        return;
                      } catch (err) {
                        console.error('Не удалось открыть материал link', err);
                        setSubmitMessage('Не удалось открыть ссылку');
                      } finally {
                        setDownloadLoadingId(null);
                      }
                    } else if (linkUrl) {
                      window.open(linkUrl, '_blank', 'noopener,noreferrer');
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

              <form onSubmit={handleSubmit} className="mt-6 flex flex-wrap gap-2">
                <input
                  type="text"
                  value={flagValue}
                  onChange={(event) => setFlagValue(event.target.value)}
                  placeholder="Введи флаг сюда"
                  className="h-14 min-w-[260px] flex-1 rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 text-[16px] text-white placeholder:text-white/35 outline-none transition focus:border-[#9B6BFF]/70"
                />
                <button
                  type="submit"
                  disabled={submitLoading || !flagValue.trim()}
                  className="h-14 rounded-[10px] bg-white/10 px-6 text-[18px] text-white transition hover:bg-[#9B6BFF]/25 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {submitLoading ? 'Отправка...' : 'Сдать флаг'}
                </button>
              </form>

              {submitMessage && (
                <p className="mt-3 text-[14px] text-white/80">{submitMessage}</p>
              )}
            </div>
          </div>
        </section>

        <aside className="flex flex-col gap-4">
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
                  onClick={() => vpnHowToConnectUrl && window.open(vpnHowToConnectUrl, '_blank', 'noopener,noreferrer')}
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
                      return;
                    }
                    if (vpnFallbackDownloadUrl) {
                      triggerDownload(vpnFallbackDownloadUrl, 'vpn-config');
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
    </div>
  );
}
