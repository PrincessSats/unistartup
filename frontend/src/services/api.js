// frontend/src/services/api.js

import axios from 'axios';

// local or prod env
const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_URL = process.env.REACT_APP_API_BASE_URL || (isLocalhost ? 'http://localhost:8000' : '');

if (!API_URL) {
  // Helps catch broken cloud builds where REACT_APP_API_BASE_URL was not provided.
  // eslint-disable-next-line no-console
  console.error('REACT_APP_API_BASE_URL is not configured for this build');
}

export const getProfile = (token) =>
  fetch(`${API_URL}/profile`, {
    headers: {
      'X-Auth-Token': token,
    },
  });

// Создаем axios instance
const api = axios.create({
  baseURL: API_URL,
});

const inFlightGetRequests = new Map();
const getResponseCache = new Map();

const CACHE_TTLS_MS = {
  profile: 60 * 1000,
  knowledgeFeed: 5 * 60 * 1000,
  practiceTasks: 90 * 1000,
  myStats: 30 * 1000,
};

function serializeParams(params = {}) {
  const pairs = [];
  Object.keys(params)
    .sort()
    .forEach((key) => {
      const value = params[key];
      if (value === undefined || value === null) return;
      if (Array.isArray(value)) {
        value.forEach((item) => pairs.push([key, String(item)]));
        return;
      }
      pairs.push([key, String(value)]);
    });

  return new URLSearchParams(pairs).toString();
}

function buildGetCacheKey(url, params = {}) {
  const serialized = serializeParams(params);
  return serialized ? `${url}?${serialized}` : url;
}

function readGetCache(key) {
  const entry = getResponseCache.get(key);
  if (!entry) {
    return { hit: false };
  }
  if (Date.now() > entry.expiresAt) {
    getResponseCache.delete(key);
    return { hit: false };
  }
  return { hit: true, data: entry.data };
}

function writeGetCache(key, data, ttlMs) {
  if (!Number.isFinite(ttlMs) || ttlMs <= 0) return;
  getResponseCache.set(key, {
    data,
    expiresAt: Date.now() + ttlMs,
  });
}

function invalidateGetCacheByPrefix(prefix) {
  for (const key of getResponseCache.keys()) {
    if (key.startsWith(prefix)) {
      getResponseCache.delete(key);
    }
  }
  for (const key of inFlightGetRequests.keys()) {
    if (key.startsWith(prefix)) {
      inFlightGetRequests.delete(key);
    }
  }
}

function clearAllRequestCache() {
  inFlightGetRequests.clear();
  getResponseCache.clear();
}

async function cachedGet(url, { params = {}, ttlMs = 0 } = {}) {
  const cacheKey = buildGetCacheKey(url, params);
  const cached = readGetCache(cacheKey);
  if (cached.hit) {
    return cached.data;
  }

  const inFlight = inFlightGetRequests.get(cacheKey);
  if (inFlight) {
    return inFlight;
  }

  const request = api
    .get(url, { params })
    .then((response) => {
      writeGetCache(cacheKey, response.data, ttlMs);
      return response.data;
    })
    .finally(() => {
      inFlightGetRequests.delete(cacheKey);
    });

  inFlightGetRequests.set(cacheKey, request);
  return request;
}

// Добавляем токен к защищенным запросам (не к /auth/*).
api.interceptors.request.use((config) => {
  const requestPath = String(config.url || '');
  let pathname = requestPath;
  if (requestPath.includes('://')) {
    try {
      pathname = new URL(requestPath).pathname;
    } catch {
      pathname = requestPath;
    }
  }
  const normalizedPath = pathname.startsWith('/') ? pathname : `/${pathname}`;
  const isAuthRequest = normalizedPath === '/auth' || normalizedPath.startsWith('/auth/');
  const token = localStorage.getItem('token');
  if (token && !isAuthRequest) {
    config.headers['X-Auth-Token'] = token;
  }
  return config;
});

// API методы авторизации
export const authAPI = {
  register: async (email, username, password) => {
    if (!API_URL) {
      throw new Error('API base URL is not configured');
    }
    const response = await api.post('/auth/register', {
      email,
      username,
      password,
    });
    return response.data;
  },

  login: async (email, password) => {
    if (!API_URL) {
      throw new Error('API base URL is not configured');
    }
    clearAllRequestCache();
    const response = await api.post('/auth/login', {
      email,
      password,
    });
    if (response.data.access_token) {
      localStorage.setItem('token', response.data.access_token);
    }
    return response.data;
  },

  logout: () => {
    localStorage.removeItem('token');
    clearAllRequestCache();
  },

  isAuthenticated: () => {
    return !!localStorage.getItem('token');
  },
};

// Запросы к защищенным endpoints
export const userAPI = {
  getWelcome: async () => {
    const response = await api.get('/welcome');
    return response.data;
  },

  getAdmin: async () => {
    const response = await api.get('/admin');
    return response.data;
  },
};

export const adminAPI = {
  getDashboard: async () => {
    const response = await api.get('/admin');
    return response.data;
  },
  listTasks: async (params = {}) => {
    const response = await api.get('/admin/tasks', { params });
    return response.data;
  },
  getTask: async (taskId) => {
    const response = await api.get(`/admin/tasks/${taskId}`);
    return response.data;
  },
  generateTask: async (payload) => {
    const response = await api.post('/admin/tasks/generate', payload);
    return response.data;
  },
  createTask: async (payload) => {
    const response = await api.post('/admin/tasks', payload);
    return response.data;
  },
  updateTask: async (taskId, payload) => {
    const response = await api.put(`/admin/tasks/${taskId}`, payload);
    return response.data;
  },
  deleteTask: async (taskId) => {
    const response = await api.delete(`/admin/tasks/${taskId}`);
    return response.data;
  },
  listPrompts: async () => {
    const response = await api.get('/admin/prompts');
    return response.data;
  },
  updatePrompt: async (code, payload) => {
    const response = await api.put(`/admin/prompts/${code}`, payload);
    return response.data;
  },
  listContests: async () => {
    const response = await api.get('/admin/contests');
    return response.data;
  },
  getContest: async (contestId) => {
    const response = await api.get(`/admin/contests/${contestId}`);
    return response.data;
  },
  createContest: async (payload) => {
    const response = await api.post('/admin/contests', payload);
    return response.data;
  },
  updateContest: async (contestId, payload) => {
    const response = await api.put(`/admin/contests/${contestId}`, payload);
    return response.data;
  },
  endContestNow: async (contestId) => {
    const response = await api.post(`/admin/contests/${contestId}/end`);
    return response.data;
  },
  deleteContest: async (contestId) => {
    const response = await api.delete(`/admin/contests/${contestId}`);
    return response.data;
  },
  createArticle: async (payload) => {
    const response = await api.post('/admin/kb_entries', payload);
    return response.data;
  },
  listArticles: async (params = {}) => {
    const response = await api.get('/admin/kb_entries', { params });
    return response.data;
  },
  updateArticle: async (entryId, payload) => {
    const response = await api.put(`/admin/kb_entries/${entryId}`, payload);
    return response.data;
  },
  deleteArticle: async (entryId) => {
    const response = await api.delete(`/admin/kb_entries/${entryId}`);
    return response.data;
  },
  generateArticle: async (payload) => {
    const response = await api.post('/admin/kb_entries/generate', payload);
    return response.data;
  },
  fetchNvd24h: async () => {
    const response = await api.post('/admin/nvd_sync');
    return response.data;
  },
  resolveFeedback: async (feedbackId) => {
    const response = await api.post(`/admin/feedback/${feedbackId}/resolve`);
    return response.data;
  },
};

export const knowledgeAPI = {
  getFeed: async (params = {}) => {
    return cachedGet('/kb_entries/feed', {
      params,
      ttlMs: CACHE_TTLS_MS.knowledgeFeed,
    });
  },
  getEntries: async (params = {}) => {
    const response = await api.get('/kb_entries', { params });
    return response.data;
  },
  getEntriesPaged: async (params = {}) => {
    const response = await api.get('/kb_entries/paged', { params });
    return response.data;
  },
  getTags: async (params = {}) => {
    const response = await api.get('/kb_entries/tags', { params });
    return response.data;
  },
  getEntry: async (entryId) => {
    const response = await api.get(`/kb_entries/${entryId}`);
    return response.data;
  },
  getComments: async (entryId, params = {}) => {
    const response = await api.get(`/kb_entries/${entryId}/comments`, { params });
    return response.data;
  },
  createComment: async (entryId, payload) => {
    const response = await api.post(`/kb_entries/${entryId}/comments`, payload);
    return response.data;
  },
};

export const educationAPI = {
  getPracticeTasks: async (params = {}) => {
    return cachedGet('/education/practice/tasks', {
      params,
      ttlMs: CACHE_TTLS_MS.practiceTasks,
    });
  },
  getPracticeTask: async (taskId) => {
    const response = await api.get(`/education/practice/tasks/${taskId}`);
    return response.data;
  },
  getPracticeMaterialDownload: async (taskId, materialId) => {
    const response = await api.get(`/education/practice/tasks/${taskId}/materials/${materialId}/download`);
    return response.data;
  },
  downloadPracticeMaterialContent: async (taskId, materialId) => {
    const response = await api.get(
      `/education/practice/tasks/${taskId}/materials/${materialId}/download/content`,
      { responseType: 'blob' }
    );
    return response;
  },
  submitPracticeFlag: async (taskId, payload) => {
    const response = await api.post(`/education/practice/tasks/${taskId}/submit`, payload);
    return response.data;
  },
  getPracticeTaskChatSession: async (taskId) => {
    const response = await api.get(`/education/practice/tasks/${taskId}/chat/session`);
    return response.data;
  },
  abortPracticeTaskChatSession: async (taskId) => {
    await api.delete(`/education/practice/tasks/${taskId}/chat/session`);
  },
  restartPracticeTaskChatSession: async (taskId) => {
    const response = await api.post(`/education/practice/tasks/${taskId}/chat/session/restart`);
    return response.data;
  },
  sendPracticeTaskChatMessage: async (taskId, payload) => {
    const response = await api.post(`/education/practice/tasks/${taskId}/chat/messages`, payload);
    return response.data;
  },
};

// API профиля (НОВОЕ)
export const profileAPI = {
  // Получить профиль
  getProfile: async () => {
    return cachedGet('/profile', {
      ttlMs: CACHE_TTLS_MS.profile,
    });
  },

  // Обновить username
  updateUsername: async (username) => {
    const response = await api.put('/profile', { username });
    invalidateGetCacheByPrefix('/profile');
    return response.data;
  },

  // Обновить email
  updateEmail: async (newEmail) => {
    const response = await api.put('/profile/email', { new_email: newEmail });
    invalidateGetCacheByPrefix('/profile');
    return response.data;
  },

  // Сменить пароль
  changePassword: async (currentPassword, newPassword) => {
    const response = await api.put('/profile/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    invalidateGetCacheByPrefix('/profile');
    return response.data;
  },

  // Загрузить аватарку
  uploadAvatar: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/profile/avatar', formData);
    invalidateGetCacheByPrefix('/profile');
    return response.data;
  },
};

export const contestAPI = {
  getActiveContest: async () => {
    const response = await api.get('/contests/active');
    return response.data;
  },
  joinContest: async (contestId) => {
    const response = await api.post(`/contests/${contestId}/join`);
    return response.data;
  },
  getCurrentTask: async (contestId) => {
    const response = await api.get(`/contests/${contestId}/current-task`);
    return response.data;
  },
  getLeaderboard: async (contestId) => {
    const response = await api.get(`/contests/${contestId}/leaderboard`);
    return response.data;
  },
  getMyResults: async (contestId) => {
    const response = await api.get(`/contests/${contestId}/my-results`);
    return response.data;
  },
  submitFlag: async (contestId, payload) => {
    const response = await api.post(`/contests/${contestId}/submit`, payload);
    return response.data;
  },
  getTaskChatSession: async (contestId, taskId) => {
    const response = await api.get(`/contests/${contestId}/tasks/${taskId}/chat/session`);
    return response.data;
  },
  abortTaskChatSession: async (contestId, taskId) => {
    await api.delete(`/contests/${contestId}/tasks/${taskId}/chat/session`);
  },
  sendTaskChatMessage: async (contestId, taskId, payload) => {
    const response = await api.post(`/contests/${contestId}/tasks/${taskId}/chat/messages`, payload);
    return response.data;
  },
};

export const ratingsAPI = {
  getLeaderboard: async (kind = 'contest') => {
    const response = await api.get('/ratings/leaderboard', {
      params: { kind },
    });
    return response.data;
  },
  getMyStatsBundle: async () => {
    return cachedGet('/ratings/my-stats/both', {
      ttlMs: CACHE_TTLS_MS.myStats,
    });
  },
  // Лёгкая статистика только по текущему пользователю (без полной таблицы рейтинга).
  getMyStats: async (kind = 'contest') => {
    return cachedGet('/ratings/my-stats', {
      params: { kind },
      ttlMs: CACHE_TTLS_MS.myStats,
    });
  },
};

export const feedbackAPI = {
  submitFeedback: async (topic, message) => {
    const response = await api.post('/feedback', { topic, message });
    return response.data;
  },
};

export default api;
