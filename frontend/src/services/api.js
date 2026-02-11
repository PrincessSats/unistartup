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

// API профиля (НОВОЕ)
export const profileAPI = {
  // Получить профиль
  getProfile: async () => {
    const response = await api.get('/profile');
    return response.data;
  },

  // Обновить username
  updateUsername: async (username) => {
    const response = await api.put('/profile', { username });
    return response.data;
  },

  // Обновить email
  updateEmail: async (newEmail) => {
    const response = await api.put('/profile/email', { new_email: newEmail });
    return response.data;
  },

  // Сменить пароль
  changePassword: async (currentPassword, newPassword) => {
    const response = await api.put('/profile/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  },

  // Загрузить аватарку
  uploadAvatar: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/profile/avatar', formData);
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
  submitFlag: async (contestId, payload) => {
    const response = await api.post(`/contests/${contestId}/submit`, payload);
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
};

export const feedbackAPI = {
  submitFeedback: async (topic, message) => {
    const response = await api.post('/feedback', { topic, message });
    return response.data;
  },
};

export default api;
