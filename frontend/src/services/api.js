// frontend/src/services/api.js

import axios from 'axios';

// local or prod env
const API_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

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

// Добавляем токен к каждому запросу (используем X-Auth-Token вместо Authorization)
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers['X-Auth-Token'] = token;
  }
  return config;
});

// API методы авторизации
export const authAPI = {
  register: async (email, username, password) => {
    const response = await api.post('/auth/register', {
      email,
      username,
      password,
    });
    return response.data;
  },

  login: async (email, password) => {
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
