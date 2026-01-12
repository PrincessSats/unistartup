import axios from 'axios';

// Базовый URL YC backend
const API_URL = 'https://bbaaran2sgmrhuof32h4.containers.yandexcloud.net/';

// Создаем axios instance
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Добавляем токен к каждому запросу (используем X-Auth-Token вместо Authorization)
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers['X-Auth-Token'] = token;  // Изменили заголовок!
  }
  return config;
});

// API методы
export const authAPI = {
  // Регистрация
  register: async (email, username, password) => {
    const response = await api.post('/auth/register', {
      email,
      username,
      password,
    });
    return response.data;
  },

  // Вход
  login: async (email, password) => {
    const response = await api.post('/auth/login', {
      email,
      password,
    });
    // Сохраняем токен
    if (response.data.access_token) {
      localStorage.setItem('token', response.data.access_token);
    }
    return response.data;
  },

  // Выход
  logout: () => {
    localStorage.removeItem('token');
  },

  // Проверка авторизации
  isAuthenticated: () => {
    return !!localStorage.getItem('token');
  },
};

// Запросы к защищенным endpoints
export const userAPI = {
  // Получить welcome страницу
  getWelcome: async () => {
    const response = await api.get('/welcome');
    return response.data;
  },

  // Получить админ панель
  getAdmin: async () => {
    const response = await api.get('/admin');
    return response.data;
  },
};

export default api;