import React, { useEffect, useState, useCallback } from 'react';
import Drawer from '../Widgets/Drawer';
import { adminAPI } from '../../../services/api';
import { SkeletonBlock } from '../../../components/LoadingState';

function getApiErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  const responseData = err?.response?.data;
  if (typeof responseData === 'string' && responseData.trim()) return responseData;
  if (typeof detail === 'string' && detail.trim()) return detail;
  return fallback;
}

const createEmptyTaskForm = () => ({
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
  access_type: 'just_flag',
  chat_system_prompt_template: '',
  chat_user_message_max_chars: 150,
  chat_model_max_output_tokens: 256,
  chat_session_ttl_minutes: 180,
  creation_solution: '',
  llm_raw_response: null,
});

const createEmptyAccessConfig = () => ({
  vpn_config_ip: '',
  vpn_allowed_ips: '',
  vpn_created_at: '',
  vpn_how_to_connect_url: '',
  vpn_download_storage_key: '',
  vpn_download_url: '',
  vm_launch_url: '',
  link_storage_key: '',
  link_label: '',
  file_storage_key: '',
  file_download_url: '',
  file_name: '',
  file_size_label: '',
  file_badge: '',
});

const createDefaultFlags = () => [
  { flag_id: 'main', format: 'FLAG{...}', expected_value: '', description: '' },
];

function TaskEditDrawer({ open, taskId, onClose, onUpdated }) {
  const [taskForm, setTaskForm] = useState(createEmptyTaskForm());
  const [accessConfig, setAccessConfig] = useState(createEmptyAccessConfig());
  const [flags, setFlags] = useState(createDefaultFlags());
  
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStatus('idle');
    setError('');
    setLoading(false);
  }, [open]);

  const loadTask = useCallback(async (id) => {
    setLoading(true);
    setError('');
    try {
      const data = await adminAPI.getTask(id);
      applyTaskData(data);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось загрузить задачу'));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!open || !taskId) return;
    loadTask(taskId);
  }, [open, taskId, loadTask]);

  const parseAccessConfig = (taskData) => {
    const next = createEmptyAccessConfig();
    const taskMaterials = Array.isArray(taskData?.materials) ? taskData.materials : [];
    const declaredAccessType = String(taskData?.access_type || 'just_flag').toLowerCase();
    const inferredAccessType = taskMaterials
      .map((item) => String(item?.type || '').toLowerCase())
      .find((type) => ['vpn', 'vm', 'link', 'file'].includes(type));
    const accessType = declaredAccessType === 'just_flag' && inferredAccessType
      ? inferredAccessType
      : declaredAccessType;

    const findMaterial = (type) => taskMaterials.find((item) => String(item?.type || '').toLowerCase() === type) || null;
    const readMeta = (material) => (material && typeof material.meta === 'object' && !Array.isArray(material.meta) ? material.meta : {});

    if (accessType === 'vpn') {
      const vpnMaterial = findMaterial('vpn') || taskMaterials[0] || null;
      const meta = readMeta(vpnMaterial);
      next.vpn_config_ip = String(meta.config_ip || '').trim();
      next.vpn_allowed_ips = String(meta.allowed_ips || '').trim();
      next.vpn_created_at = String(meta.created_at || '').trim();
      next.vpn_how_to_connect_url = String(meta.how_to_connect_url || vpnMaterial?.url || '').trim();
      const downloadRaw = String(meta.download_storage_key || vpnMaterial?.storage_key || meta.storage_key || meta.download_url || '').trim();
      if (downloadRaw.startsWith('http://') || downloadRaw.startsWith('https://')) {
        next.vpn_download_url = downloadRaw;
      } else {
        next.vpn_download_storage_key = downloadRaw;
      }
    }

    if (accessType === 'vm') {
      const vmMaterial = findMaterial('vm') || taskMaterials[0] || null;
      const meta = readMeta(vmMaterial);
      next.vm_launch_url = String(meta.launch_url || vmMaterial?.url || '').trim();
    }

    if (accessType === 'link') {
      const linkMaterial = findMaterial('link') || taskMaterials[0] || null;
      const meta = readMeta(linkMaterial);
      next.link_storage_key = String(meta.target_storage_key || linkMaterial?.storage_key || meta.storage_key || meta.target_url || linkMaterial?.url || '').trim();
      next.link_label = String(meta.label || linkMaterial?.name || '').trim();
    }

    if (accessType === 'file') {
      const fileMaterial = findMaterial('file') || taskMaterials[0] || null;
      const meta = readMeta(fileMaterial);
      const downloadRaw = String(fileMaterial?.storage_key || meta.download_storage_key || meta.storage_key || meta.download_url || fileMaterial?.url || '').trim();
      if (downloadRaw.startsWith('http://') || downloadRaw.startsWith('https://')) {
        next.file_download_url = downloadRaw;
      } else {
        next.file_storage_key = downloadRaw;
      }
      next.file_name = String(meta.file_name || fileMaterial?.name || '').trim();
      next.file_size_label = String(meta.size_label || meta.file_size_label || '').trim();
      next.file_badge = String(meta.badge || meta.file_ext || '').trim();
    }

    return next;
  };

  const applyTaskData = (taskData) => {
    const taskMaterials = Array.isArray(taskData?.materials) ? taskData.materials : [];
    const declaredAccessType = String(taskData?.access_type || 'just_flag').toLowerCase();
    const inferredAccessType = taskMaterials
      .map((item) => String(item?.type || '').toLowerCase())
      .find((type) => ['vpn', 'vm', 'link', 'file'].includes(type));
    const resolvedAccessType = declaredAccessType === 'just_flag' && inferredAccessType
      ? inferredAccessType
      : declaredAccessType;

    setTaskForm({
      title: taskData?.title || '',
      category: taskData?.category || 'misc',
      difficulty: taskData?.difficulty ?? 3,
      points: taskData?.points ?? 200,
      tags: Array.isArray(taskData?.tags) ? taskData.tags.join(', ') : '',
      language: taskData?.language || 'ru',
      story: taskData?.story || '',
      participant_description: taskData?.participant_description || '',
      state: taskData?.state || 'draft',
      task_kind: taskData?.task_kind || 'contest',
      access_type: resolvedAccessType,
      chat_system_prompt_template: taskData?.chat_system_prompt_template || '',
      chat_user_message_max_chars: Number(taskData?.chat_user_message_max_chars ?? 150),
      chat_model_max_output_tokens: Number(taskData?.chat_model_max_output_tokens ?? 256),
      chat_session_ttl_minutes: Number(taskData?.chat_session_ttl_minutes ?? 180),
      creation_solution: taskData?.creation_solution || '',
      llm_raw_response: taskData?.llm_raw_response || null,
    });

    const taskFlags = Array.isArray(taskData?.flags) && taskData.flags.length > 0
      ? taskData.flags.map((flag) => ({
          flag_id: flag.flag_id || 'main',
          format: flag.format || 'FLAG{...}',
          expected_value: flag.expected_value || '',
          description: flag.description || '',
        }))
      : createDefaultFlags();

    setFlags(taskFlags);
    setAccessConfig(parseAccessConfig(taskData));
  };

  const updateFlag = (index, field, value) => {
    setFlags((prev) => prev.map((flag, idx) => (idx === index ? { ...flag, [field]: value } : flag)));
  };

  const addFlag = () => {
    setFlags((prev) => [...prev, {
      flag_id: `flag${prev.length + 1}`,
      format: 'FLAG{...}',
      expected_value: '',
      description: '',
    }]);
  };

  const removeFlag = (index) => {
    setFlags((prev) => prev.filter((_, idx) => idx !== index));
  };

  const updateAccessConfig = (field, value) => {
    setAccessConfig((prev) => ({ ...prev, [field]: value }));
  };

  const buildMaterialsPayload = () => {
    const accessType = String(taskForm.access_type || 'just_flag').toLowerCase();

    if (accessType === 'vpn') {
      const meta = {};
      const downloadStorageKey = accessConfig.vpn_download_storage_key.trim();
      const downloadUrl = accessConfig.vpn_download_url.trim();
      const howToConnectUrl = accessConfig.vpn_how_to_connect_url.trim();
      if (accessConfig.vpn_config_ip.trim()) meta.config_ip = accessConfig.vpn_config_ip.trim();
      if (accessConfig.vpn_allowed_ips.trim()) meta.allowed_ips = accessConfig.vpn_allowed_ips.trim();
      if (accessConfig.vpn_created_at.trim()) meta.created_at = accessConfig.vpn_created_at.trim();
      if (howToConnectUrl) meta.how_to_connect_url = howToConnectUrl;
      if (downloadStorageKey) meta.download_storage_key = downloadStorageKey;
      if (downloadUrl) meta.download_url = downloadUrl;

      const hasAnyData = Object.keys(meta).length > 0 || Boolean(downloadStorageKey);
      if (!hasAnyData) return [];

      return [{
        type: 'vpn',
        name: 'VPN configuration',
        description: null,
        url: howToConnectUrl || null,
        storage_key: downloadStorageKey || null,
        meta,
      }];
    }

    if (accessType === 'vm') {
      const launchUrl = accessConfig.vm_launch_url.trim();
      if (!launchUrl) return [];
      return [{
        type: 'vm',
        name: 'VM launch',
        description: null,
        url: launchUrl,
        storage_key: null,
        meta: { launch_url: launchUrl },
      }];
    }

    if (accessType === 'link') {
      const storageKey = accessConfig.link_storage_key.trim();
      const label = accessConfig.link_label.trim();
      if (!storageKey && !label) return [];
      return [{
        type: 'link',
        name: label || 'Перейти к заданию',
        description: null,
        url: null,
        storage_key: storageKey || null,
        meta: {
          ...(storageKey ? { target_storage_key: storageKey } : {}),
          ...(label ? { label } : {}),
        },
      }];
    }

    if (accessType === 'file') {
      const storageKey = accessConfig.file_storage_key.trim();
      const downloadUrl = accessConfig.file_download_url.trim();
      const fileName = accessConfig.file_name.trim();
      const sizeLabel = accessConfig.file_size_label.trim();
      const badge = accessConfig.file_badge.trim();

      if (!storageKey && !downloadUrl && !fileName && !sizeLabel && !badge) return [];

      const meta = {
        ...(storageKey ? { download_storage_key: storageKey } : {}),
        ...(downloadUrl ? { download_url: downloadUrl } : {}),
        ...(fileName ? { file_name: fileName } : {}),
        ...(sizeLabel ? { size_label: sizeLabel } : {}),
        ...(badge ? { badge } : {}),
      };

      return [{
        type: 'file',
        name: fileName || 'Файл',
        description: null,
        url: downloadUrl || null,
        storage_key: storageKey || null,
        meta: Object.keys(meta).length > 0 ? meta : null,
      }];
    }

    return [];
  };

  const buildTaskPayload = () => ({
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
    access_type: taskForm.access_type || 'just_flag',
    chat_system_prompt_template: taskForm.chat_system_prompt_template || null,
    chat_user_message_max_chars: Number(taskForm.chat_user_message_max_chars || 150),
    chat_model_max_output_tokens: Number(taskForm.chat_model_max_output_tokens || 256),
    chat_session_ttl_minutes: Number(taskForm.chat_session_ttl_minutes || 180),
    creation_solution: taskForm.creation_solution || null,
    llm_raw_response: taskForm.llm_raw_response || null,
    flags: flags.map((flag) => ({
      flag_id: flag.flag_id || 'main',
      format: flag.format || 'FLAG{...}',
      expected_value: flag.expected_value,
      description: flag.description || null,
    })),
    materials: buildMaterialsPayload(),
  });

  const handleSave = async () => {
    const accessType = String(taskForm.access_type || 'just_flag').toLowerCase();
    if (!taskForm.title.trim()) {
      setError('Заполните название задачи');
      return;
    }
    if (accessType !== 'chat' && flags.some((flag) => !flag.expected_value.trim())) {
      setError('Укажите значение флага');
      return;
    }
    if (accessType === 'chat') {
      const prompt = String(taskForm.chat_system_prompt_template || '').trim();
      const maxChars = Number(taskForm.chat_user_message_max_chars || 150);
      const maxTokens = Number(taskForm.chat_model_max_output_tokens || 256);
      const ttlMinutes = Number(taskForm.chat_session_ttl_minutes || 180);
      if (!prompt || !prompt.includes('{{FLAG}}')) {
        setError('Для Chat укажите системный промпт и добавьте {{FLAG}}');
        return;
      }
      if (!Number.isFinite(maxChars) || maxChars < 20 || maxChars > 500) {
        setError('Лимит символов должен быть в диапазоне 20-500');
        return;
      }
      if (!Number.isFinite(maxTokens) || maxTokens < 32 || maxTokens > 1024) {
        setError('Лимит output tokens должен быть в диапазоне 32-1024');
        return;
      }
      if (!Number.isFinite(ttlMinutes) || ttlMinutes < 15 || ttlMinutes > 720) {
        setError('TTL сессии должен быть в диапазоне 15-720 минут');
        return;
      }
    }

    setStatus('saving');
    setError('');
    try {
      const payload = buildTaskPayload();
      await adminAPI.updateTask(taskId, payload);
      if (onUpdated) onUpdated();
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось обновить задачу'));
    } finally {
      setStatus('idle');
    }
  };

  const handleDelete = async () => {
    const confirmed = window.confirm(`Удалить задачу "${taskForm.title}"? Это действие нельзя отменить.`);
    if (!confirmed) return;

    setStatus('deleting');
    setError('');
    try {
      await adminAPI.deleteTask(taskId);
      if (onUpdated) onUpdated();
      onClose();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось удалить задачу'));
    } finally {
      setStatus('idle');
    }
  };

  if (!open) return null;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Редактирование задачи"
      subtitle={`Задача #${taskId}`}
      width="960px"
      footer={
        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleDelete}
            disabled={status === 'saving' || status === 'deleting'}
            className="h-12 px-5 bg-rose-500/20 border border-rose-400/40 text-rose-100 rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed hover:bg-rose-500/30"
          >
            {status === 'deleting' ? 'Удаление...' : 'Удалить'}
          </button>
          <button
            type="button"
            onClick={onClose}
            disabled={status === 'saving' || status === 'deleting'}
            className="flex-1 h-12 bg-white/[0.03] hover:bg-white/[0.06] text-white rounded-[10px] transition-colors disabled:opacity-60"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={status === 'saving' || status === 'deleting' || loading}
            className="flex-1 h-12 bg-[#9B6BFF] hover:bg-[#8452FF] text-white rounded-[10px] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {status === 'saving' ? 'Сохранение...' : 'Сохранить изменения'}
          </button>
        </div>
      }
    >
      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonBlock key={i} className="h-12 w-full rounded-[12px]" />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {error && (
            <div className="bg-red-500/10 border border-red-500/50 text-red-200 px-4 py-2 rounded-[12px] text-sm">
              {error}
            </div>
          )}

          {/* Basic Info */}
          <div className="border border-white/[0.08] rounded-[16px] p-5">
            <div className="text-[16px] text-white mb-4">Основная информация</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-white text-sm mb-2 block">Название *</label>
                <input
                  type="text"
                  value={taskForm.title}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, title: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                />
              </div>
              <div>
                <label className="text-white text-sm mb-2 block">Категория</label>
                <input
                  type="text"
                  value={taskForm.category}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, category: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                />
              </div>
              <div>
                <label className="text-white text-sm mb-2 block">Сложность</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={taskForm.difficulty}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, difficulty: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                />
              </div>
              <div>
                <label className="text-white text-sm mb-2 block">Баллы</label>
                <input
                  type="number"
                  value={taskForm.points}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, points: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                />
              </div>
              <div>
                <label className="text-white text-sm mb-2 block">Тип задачи</label>
                <select
                  value={taskForm.task_kind}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, task_kind: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                >
                  <option value="contest">Contest</option>
                  <option value="practice">Practice</option>
                </select>
              </div>
              <div>
                <label className="text-white text-sm mb-2 block">Статус</label>
                <select
                  value={taskForm.state}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, state: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                >
                  <option value="draft">Draft</option>
                  <option value="ready">Ready</option>
                  <option value="published">Published</option>
                </select>
              </div>
              <div className="md:col-span-2">
                <label className="text-white text-sm mb-2 block">Теги</label>
                <input
                  type="text"
                  value={taskForm.tags}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, tags: e.target.value }))}
                  className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
                  placeholder="web, xss, cve-2024-..."
                />
              </div>
            </div>
          </div>

          {/* Access Type */}
          <div className="border border-white/[0.08] rounded-[16px] p-5">
            <div className="text-[16px] text-white mb-4">Тип доступа</div>
            <div className="mb-4">
              <select
                value={taskForm.access_type}
                onChange={(e) => setTaskForm((prev) => ({ ...prev, access_type: e.target.value }))}
                className="w-full h-12 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 text-white/80 focus:outline-none focus:border-white/30"
              >
                <option value="vpn">VPN</option>
                <option value="vm">VM</option>
                <option value="link">Link</option>
                <option value="file">File</option>
                <option value="chat">Chat</option>
                <option value="just_flag">Just flag</option>
              </select>
            </div>

            {/* Chat Settings */}
            {taskForm.access_type === 'chat' && (
              <div className="border border-white/[0.08] rounded-[12px] p-4 bg-white/[0.02]">
                <label className="text-white text-sm mb-2 block">Системный промпт (обязательно {`{{FLAG}}`})</label>
                <textarea
                  value={taskForm.chat_system_prompt_template}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, chat_system_prompt_template: e.target.value }))}
                  className="w-full min-h-[120px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                />
                <div className="grid grid-cols-3 gap-3 mt-3">
                  <div>
                    <label className="text-white text-xs mb-1 block">Лимит символов (20-500)</label>
                    <input
                      type="number"
                      min="20"
                      max="500"
                      value={taskForm.chat_user_message_max_chars}
                      onChange={(e) => setTaskForm((prev) => ({ ...prev, chat_user_message_max_chars: e.target.value }))}
                      className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                    />
                  </div>
                  <div>
                    <label className="text-white text-xs mb-1 block">Output tokens (32-1024)</label>
                    <input
                      type="number"
                      min="32"
                      max="1024"
                      value={taskForm.chat_model_max_output_tokens}
                      onChange={(e) => setTaskForm((prev) => ({ ...prev, chat_model_max_output_tokens: e.target.value }))}
                      className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                    />
                  </div>
                  <div>
                    <label className="text-white text-xs mb-1 block">TTL сессии, мин (15-720)</label>
                    <input
                      type="number"
                      min="15"
                      max="720"
                      value={taskForm.chat_session_ttl_minutes}
                      onChange={(e) => setTaskForm((prev) => ({ ...prev, chat_session_ttl_minutes: e.target.value }))}
                      className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* VPN Settings */}
            {taskForm.access_type === 'vpn' && (
              <div className="border border-white/[0.08] rounded-[12px] p-4 bg-white/[0.02] space-y-3">
                <input
                  value={accessConfig.vpn_config_ip}
                  onChange={(e) => updateAccessConfig('vpn_config_ip', e.target.value)}
                  className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                  placeholder="IP-адрес конфигурации"
                />
                <input
                  value={accessConfig.vpn_allowed_ips}
                  onChange={(e) => updateAccessConfig('vpn_allowed_ips', e.target.value)}
                  className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                  placeholder="Разрешенные IP-адреса"
                />
                <input
                  value={accessConfig.vpn_created_at}
                  onChange={(e) => updateAccessConfig('vpn_created_at', e.target.value)}
                  className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                  placeholder="Дата создания (01.11.2025 11:59)"
                />
                <input
                  value={accessConfig.vpn_how_to_connect_url}
                  onChange={(e) => updateAccessConfig('vpn_how_to_connect_url', e.target.value)}
                  className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                  placeholder="URL: Как подключить"
                />
                <input
                  value={accessConfig.vpn_download_storage_key}
                  onChange={(e) => updateAccessConfig('vpn_download_storage_key', e.target.value)}
                  className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                  placeholder="Ключ в Object Storage"
                />
              </div>
            )}

            {/* VM Settings */}
            {taskForm.access_type === 'vm' && (
              <div className="border border-white/[0.08] rounded-[12px] p-4 bg-white/[0.02]">
                <input
                  value={accessConfig.vm_launch_url}
                  onChange={(e) => updateAccessConfig('vm_launch_url', e.target.value)}
                  className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                  placeholder="URL запуска машины"
                />
              </div>
            )}

            {/* Link Settings */}
            {taskForm.access_type === 'link' && (
              <div className="border border-white/[0.08] rounded-[12px] p-4 bg-white/[0.02] space-y-3">
                <input
                  value={accessConfig.link_label}
                  onChange={(e) => updateAccessConfig('link_label', e.target.value)}
                  className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                  placeholder="Текст кнопки/ссылки"
                />
                <input
                  value={accessConfig.link_storage_key}
                  onChange={(e) => updateAccessConfig('link_storage_key', e.target.value)}
                  className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                  placeholder="Ключ в Object Storage"
                />
              </div>
            )}

            {/* File Settings */}
            {taskForm.access_type === 'file' && (
              <div className="border border-white/[0.08] rounded-[12px] p-4 bg-white/[0.02] space-y-3">
                <input
                  value={accessConfig.file_name}
                  onChange={(e) => updateAccessConfig('file_name', e.target.value)}
                  className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                  placeholder="Имя файла"
                />
                <div className="grid grid-cols-2 gap-3">
                  <input
                    value={accessConfig.file_badge}
                    onChange={(e) => updateAccessConfig('file_badge', e.target.value)}
                    className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                    placeholder="Бейдж (ZIP/PDF)"
                  />
                  <input
                    value={accessConfig.file_size_label}
                    onChange={(e) => updateAccessConfig('file_size_label', e.target.value)}
                    className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                    placeholder="Размер (1,23 МБ)"
                  />
                </div>
                <input
                  value={accessConfig.file_storage_key}
                  onChange={(e) => updateAccessConfig('file_storage_key', e.target.value)}
                  className="w-full h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                  placeholder="Ключ в Object Storage"
                />
              </div>
            )}
          </div>

          {/* Description & Story */}
          <div className="border border-white/[0.08] rounded-[16px] p-5">
            <div className="text-[16px] text-white mb-4">Описание и легенда</div>
            <div className="space-y-4">
              <div>
                <label className="text-white text-sm mb-2 block">Описание для участника</label>
                <textarea
                  value={taskForm.participant_description}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, participant_description: e.target.value }))}
                  className="w-full min-h-[100px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                />
              </div>
              <div>
                <label className="text-white text-sm mb-2 block">Легенда (story)</label>
                <textarea
                  value={taskForm.story}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, story: e.target.value }))}
                  className="w-full min-h-[80px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                />
              </div>
              <div>
                <label className="text-white text-sm mb-2 block">Решение для организаторов</label>
                <textarea
                  value={taskForm.creation_solution}
                  onChange={(e) => setTaskForm((prev) => ({ ...prev, creation_solution: e.target.value }))}
                  className="w-full min-h-[100px] bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-4 py-3 text-white/80 focus:outline-none focus:border-white/30"
                />
              </div>
            </div>
          </div>

          {/* Flags */}
          <div className="border border-white/[0.08] rounded-[16px] p-5">
            <div className="text-[16px] text-white mb-4">Флаги</div>
            {taskForm.access_type === 'chat' ? (
              <div className="text-white/60 text-sm">
                Для chat-задач флаг создается динамически на каждую сессию.
              </div>
            ) : (
              <div className="space-y-3">
                {flags.map((flag, index) => (
                  <div key={index} className="grid grid-cols-1 md:grid-cols-5 gap-3">
                    <input
                      value={flag.flag_id}
                      onChange={(e) => updateFlag(index, 'flag_id', e.target.value)}
                      className="h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                      placeholder="ID"
                    />
                    <input
                      value={flag.format}
                      onChange={(e) => updateFlag(index, 'format', e.target.value)}
                      className="h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                      placeholder="Формат"
                    />
                    <input
                      value={flag.expected_value}
                      onChange={(e) => updateFlag(index, 'expected_value', e.target.value)}
                      className="h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                      placeholder="Значение"
                    />
                    <input
                      value={flag.description}
                      onChange={(e) => updateFlag(index, 'description', e.target.value)}
                      className="h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] px-3 text-white/80"
                      placeholder="Описание"
                    />
                    <button
                      type="button"
                      onClick={() => removeFlag(index)}
                      className="h-10 bg-white/[0.03] border border-white/[0.09] rounded-[10px] text-white/60 hover:text-white hover:border-rose-400/40 transition"
                    >
                      Удалить
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addFlag}
                  className="text-[14px] text-[#CBB6FF] hover:text-[#9B6BFF] transition"
                >
                  + Добавить флаг
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}

export default TaskEditDrawer;
