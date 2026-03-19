// frontend/src/services/api.js

import axios from 'axios';

// local or prod env
const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

function normalizeLocalApiBaseUrl(rawUrl) {
  const configured = String(rawUrl || '').trim();
  if (!configured || !isLocalhost) {
    return configured;
  }

  try {
    const url = new URL(configured);
    const isLocalApiHost = url.hostname === 'localhost' || url.hostname === '127.0.0.1';
    if (!isLocalApiHost) {
      return configured;
    }

    if (url.hostname !== window.location.hostname) {
      url.hostname = window.location.hostname;
      return url.toString().replace(/\/$/, '');
    }
    return configured;
  } catch {
    return configured;
  }
}

const API_URL = normalizeLocalApiBaseUrl(
  process.env.REACT_APP_API_BASE_URL || (isLocalhost ? `http://${window.location.hostname}:8000` : '')
);
const ACCESS_TOKEN_STORAGE_KEY = 'token';
const AUTH_SESSION_HINT_STORAGE_KEY = 'auth_session_hint';
const PROFILE_CACHE_STORAGE_KEY = 'layout:profile:v1';
const parsedTimeout = Number(process.env.REACT_APP_API_TIMEOUT_MS || 15000);
const REQUEST_TIMEOUT_MS = Number.isFinite(parsedTimeout) && parsedTimeout >= 3000 ? parsedTimeout : 15000;
const parsedLoginTimeout = Number(process.env.REACT_APP_AUTH_LOGIN_TIMEOUT_MS || 10000);
const AUTH_LOGIN_TIMEOUT_MS = Number.isFinite(parsedLoginTimeout) && parsedLoginTimeout >= 4000
  ? parsedLoginTimeout
  : 10000;
const parsedRefreshTimeout = Number(process.env.REACT_APP_AUTH_REFRESH_TIMEOUT_MS || REQUEST_TIMEOUT_MS);
export const AUTH_BOOTSTRAP_TIMEOUT_MS = Number.isFinite(parsedRefreshTimeout) && parsedRefreshTimeout >= 4000
  ? parsedRefreshTimeout
  : REQUEST_TIMEOUT_MS;
const ACCESS_TOKEN_CLOCK_SKEW_SECONDS = 30;

if (!API_URL) {
  // Helps catch broken cloud builds where REACT_APP_API_BASE_URL was not provided.
  // eslint-disable-next-line no-console
  console.error('REACT_APP_API_BASE_URL is not configured for this build');
}

function shouldSendAuthorizationHeader() {
  if (!API_URL) return true;
  try {
    const { hostname } = new URL(API_URL);
    // Yandex Serverless Containers may treat Authorization as IAM auth header.
    // Keep app token in X-Auth-Token for this host family to avoid edge 403.
    return !hostname.endsWith('.containers.yandexcloud.net');
  } catch {
    return true;
  }
}

const SEND_AUTHORIZATION_HEADER = shouldSendAuthorizationHeader();

export const getProfile = (token) =>
  fetch(`${API_URL}/profile`, {
    headers: {
      'X-Auth-Token': token,
      ...(SEND_AUTHORIZATION_HEADER ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

// Создаем axios instance
const api = axios.create({
  baseURL: API_URL,
  timeout: REQUEST_TIMEOUT_MS,
});

const inFlightGetRequests = new Map();
const getResponseCache = new Map();
let refreshInFlight = null;

const CACHE_TTLS_MS = {
  profile: 60 * 1000,
  knowledgeFeed: 5 * 60 * 1000,
  knowledgeTags: 10 * 60 * 1000,
  knowledgePaged: 30 * 1000,
  practiceTasks: 90 * 1000,
  myStats: 30 * 1000,
  ratingLeaderboard: 20 * 1000,
  contestActive: 15 * 1000,
  adminDashboard: 15 * 1000,
};

function getStoredAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
}

function hasSessionHint() {
  return localStorage.getItem(AUTH_SESSION_HINT_STORAGE_KEY) === '1';
}

function setSessionHint() {
  localStorage.setItem(AUTH_SESSION_HINT_STORAGE_KEY, '1');
}

function clearSessionHint() {
  localStorage.removeItem(AUTH_SESSION_HINT_STORAGE_KEY);
}

function setStoredAccessToken(token) {
  if (!token) return;
  localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
  setSessionHint();
}

function clearStoredAccessToken() {
  localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
}

function clearProfileSessionCache() {
  try {
    sessionStorage.removeItem(PROFILE_CACHE_STORAGE_KEY);
  } catch {
    // Session storage cleanup is best-effort.
  }
}

function decodeJwtPayload(token) {
  if (!token || typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length < 2) return null;
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    const decoded = window.atob(padded);
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

function getAccessTokenExpiryMs(token) {
  const payload = decodeJwtPayload(token);
  const expSeconds = Number(payload?.exp);
  if (!Number.isFinite(expSeconds)) return null;
  return expSeconds * 1000;
}

function isAccessTokenFresh(token, skewSeconds = ACCESS_TOKEN_CLOCK_SKEW_SECONDS) {
  if (!token) return false;
  const expMs = getAccessTokenExpiryMs(token);
  if (!expMs) return false;
  return Date.now() + skewSeconds * 1000 < expMs;
}

function resolveRequestPath(configOrUrl) {
  const raw = typeof configOrUrl === 'string'
    ? configOrUrl
    : String(configOrUrl?.url || '');
  if (!raw) return '/';
  if (raw.includes('://')) {
    try {
      return new URL(raw).pathname || '/';
    } catch {
      return raw.startsWith('/') ? raw : `/${raw}`;
    }
  }
  return raw.startsWith('/') ? raw : `/${raw}`;
}

function isAuthPath(pathname) {
  return pathname === '/auth'
    || pathname.startsWith('/auth/')
    || pathname === '/api/auth'
    || pathname.startsWith('/api/auth/');
}

function buildApiUrl(pathname) {
  if (!pathname) return API_URL || window.location.origin;
  if (pathname.includes('://')) return pathname;
  const normalizedPath = pathname.startsWith('/') ? pathname : `/${pathname}`;
  if (API_URL) {
    return new URL(normalizedPath, API_URL).toString();
  }
  return new URL(normalizedPath, window.location.origin).toString();
}

function isTimeoutError(error) {
  const code = String(error?.code || '').toUpperCase();
  const message = String(error?.message || '').toLowerCase();
  return code === 'ECONNABORTED' || message.includes('timeout');
}

function isSessionExpiredError(error) {
  return Number(error?.response?.status || 0) === 401;
}

function extractErrorDetail(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item?.message || String(item)).join(', ');
  }
  if (detail && typeof detail === 'object') {
    return detail.msg || detail.message || '';
  }
  return '';
}

function buildLoginHash(reason = '') {
  const encodedReason = String(reason || '').trim();
  if (!encodedReason) return '#/login';
  return `#/login?reason=${encodeURIComponent(encodedReason)}`;
}


function redirectToLogin(reason = '') {
  const target = buildLoginHash(reason);
  if (window.location.hash !== target) {
    window.location.hash = target;
  }
}

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

function clearClientAuthState({ clearHint = true } = {}) {
  clearStoredAccessToken();
  if (clearHint) {
    clearSessionHint();
  }
  clearProfileSessionCache();
  clearAllRequestCache();
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

async function refreshAccessToken({ timeoutMs = AUTH_BOOTSTRAP_TIMEOUT_MS } = {}) {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  refreshInFlight = api
    .post(
      '/auth/refresh',
      null,
      {
        withCredentials: true,
        timeout: timeoutMs,
        __skipAuthRefresh: true,
      }
    )
    .then((response) => {
      const token = response?.data?.access_token;
      if (!token) {
        throw new Error('Refresh response missing access token');
      }
      setStoredAccessToken(token);
      return response.data;
    })
    .finally(() => {
      refreshInFlight = null;
    });

  return refreshInFlight;
}

// Добавляем токен к защищенным запросам (не к /auth/*).
api.interceptors.request.use((config) => {
  const normalizedPath = resolveRequestPath(config);
  const isAuthRequest = isAuthPath(normalizedPath);
  const token = getStoredAccessToken();
  config.headers = config.headers || {};
  if (token && !isAuthRequest) {
    config.headers['X-Auth-Token'] = token;
    if (SEND_AUTHORIZATION_HEADER) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalConfig = error?.config || {};
    const responseStatus = Number(error?.response?.status || 0);
    if (responseStatus === 403) {
      const detail = extractErrorDetail(error).toLowerCase();
      const requestPath = resolveRequestPath(originalConfig);
      if (!isAuthPath(requestPath) && detail.includes('заблокирован')) {
        authAPI.logout({ remote: false, redirect: true, reason: 'account_blocked' });
      }
      return Promise.reject(error);
    }

    if (responseStatus !== 401) {
      return Promise.reject(error);
    }

    const requestPath = resolveRequestPath(originalConfig);
    if (originalConfig.__skipAuthRefresh || isAuthPath(requestPath)) {
      return Promise.reject(error);
    }

    // Гость (нет токена) — не пытаемся рефрешить и не редиректим на логин.
    if (!getStoredAccessToken()) {
      return Promise.reject(error);
    }

    if (originalConfig.__retriedAfterRefresh) {
      authAPI.logout({ remote: false, redirect: true, reason: 'session_expired' });
      return Promise.reject(error);
    }

    try {
      await refreshAccessToken();
      const token = getStoredAccessToken();
      originalConfig.__retriedAfterRefresh = true;
      originalConfig.headers = originalConfig.headers || {};
      if (token) {
        originalConfig.headers['X-Auth-Token'] = token;
        if (SEND_AUTHORIZATION_HEADER) {
          originalConfig.headers.Authorization = `Bearer ${token}`;
        }
      }
      return api(originalConfig);
    } catch (refreshErr) {
      const sessionExpired = isSessionExpiredError(refreshErr);
      const reason = sessionExpired
        ? 'session_expired'
        : (isTimeoutError(refreshErr) ? 'network_timeout' : 'session_unavailable');
      // eslint-disable-next-line no-console
      console.warn('Auth refresh failed after 401', { reason });
      if (sessionExpired) {
        authAPI.logout({ remote: false, redirect: true, reason });
      }
      return Promise.reject(refreshErr);
    }
  }
);

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
    }, {
      withCredentials: true,
      timeout: AUTH_LOGIN_TIMEOUT_MS,
      __skipAuthRefresh: true,
    });
    if (response.data.access_token) {
      setStoredAccessToken(response.data.access_token);
    }
    return response.data;
  },

  startEmailRegistration: async ({ email, termsAccepted, marketingOptIn = false }) => {
    if (!API_URL) {
      throw new Error('API base URL is not configured');
    }
    const response = await api.post('/api/auth/registration/email/start', {
      email,
      terms_accepted: termsAccepted,
      marketing_opt_in: marketingOptIn,
    }, {
      __skipAuthRefresh: true,
    });
    return response.data;
  },

  resendEmailRegistration: async ({ flowToken }) => {
    if (!API_URL) {
      throw new Error('API base URL is not configured');
    }
    const response = await api.post('/api/auth/registration/email/resend', {
      flow_token: flowToken,
    }, {
      __skipAuthRefresh: true,
    });
    return response.data;
  },

  attachEmailToRegistrationFlow: async ({ flowToken, email, termsAccepted, marketingOptIn = false }) => {
    if (!API_URL) {
      throw new Error('API base URL is not configured');
    }
    const response = await api.post('/api/auth/registration/email/attach', {
      flow_token: flowToken,
      email,
      terms_accepted: termsAccepted,
      marketing_opt_in: marketingOptIn,
    }, {
      __skipAuthRefresh: true,
    });
    return response.data;
  },

  getRegistrationFlow: async ({ flowToken }) => {
    if (!API_URL) {
      throw new Error('API base URL is not configured');
    }
    const response = await api.get('/api/auth/registration/flow', {
      params: { flow_token: flowToken },
      __skipAuthRefresh: true,
    });
    return response.data;
  },

  completeRegistration: async (payload) => {
    if (!API_URL) {
      throw new Error('API base URL is not configured');
    }
    clearAllRequestCache();
    const response = await api.post('/api/auth/registration/complete', {
      flow_token: payload.flowToken,
      username: payload.username,
      password: payload.password ?? null,
      profession_tags: payload.professionTags,
      grade: payload.grade,
      interest_tags: payload.interestTags,
    }, {
      withCredentials: true,
      timeout: AUTH_LOGIN_TIMEOUT_MS,
      __skipAuthRefresh: true,
    });
    return response.data;
  },

  startYandexLogin: () => {
    window.location.assign(buildApiUrl('/api/auth/yandex/start?intent=login'));
  },

  startGithubLogin: () => {
    window.location.assign(buildApiUrl('/api/auth/github/start?intent=login'));
  },

  startTelegramLogin: () => {
    window.location.assign(buildApiUrl('/api/auth/telegram/start?intent=login'));
  },

  startYandexRegistration: ({ termsAccepted, marketingOptIn = false }) => {
    const params = new URLSearchParams({
      intent: 'register',
      terms_accepted: String(Boolean(termsAccepted)),
      marketing_opt_in: String(Boolean(marketingOptIn)),
    });
    window.location.assign(buildApiUrl(`/api/auth/yandex/start?${params.toString()}`));
  },

  startGithubRegistration: ({ termsAccepted, marketingOptIn = false }) => {
    const params = new URLSearchParams({
      intent: 'register',
      terms_accepted: String(Boolean(termsAccepted)),
      marketing_opt_in: String(Boolean(marketingOptIn)),
    });
    window.location.assign(buildApiUrl(`/api/auth/github/start?${params.toString()}`));
  },

  startTelegramRegistration: ({ termsAccepted, marketingOptIn = false }) => {
    const params = new URLSearchParams({
      intent: 'register',
      terms_accepted: String(Boolean(termsAccepted)),
      marketing_opt_in: String(Boolean(marketingOptIn)),
    });
    window.location.assign(buildApiUrl(`/api/auth/telegram/start?${params.toString()}`));
  },

  refresh: async ({ timeoutMs = AUTH_BOOTSTRAP_TIMEOUT_MS } = {}) => {
    return refreshAccessToken({ timeoutMs });
  },

  warmup: async ({ timeoutMs = 2000 } = {}) => {
    if (!API_URL) return;
    try {
      await api.get('/health', {
        timeout: timeoutMs,
        __skipAuthRefresh: true,
      });
    } catch {
      // Warmup is best-effort and must not affect UX.
    }
  },

  bootstrapAuth: async ({ timeoutMs = AUTH_BOOTSTRAP_TIMEOUT_MS } = {}) => {
    const startedAt = performance.now();
    const existingToken = getStoredAccessToken();
    if (isAccessTokenFresh(existingToken)) {
      return { authenticated: true, reason: null, elapsedMs: performance.now() - startedAt };
    }

    if (!existingToken && !hasSessionHint()) {
      return { authenticated: false, reason: null, elapsedMs: performance.now() - startedAt };
    }

    try {
      await refreshAccessToken({ timeoutMs });
      return { authenticated: true, reason: null, elapsedMs: performance.now() - startedAt };
    } catch (err) {
      const sessionExpired = isSessionExpiredError(err);
      const reason = sessionExpired
        ? 'session_expired'
        : (isTimeoutError(err) ? 'network_timeout' : 'session_unavailable');
      if (sessionExpired) {
        clearClientAuthState();
      }
      // eslint-disable-next-line no-console
      console.warn('Auth bootstrap failed', { reason, elapsedMs: performance.now() - startedAt });
      if (!sessionExpired && existingToken) {
        return { authenticated: true, reason: null, elapsedMs: performance.now() - startedAt };
      }
      return {
        authenticated: false,
        reason: sessionExpired ? reason : null,
        elapsedMs: performance.now() - startedAt,
      };
    }
  },

  logout: ({ remote = true, redirect = false, reason = '' } = {}) => {
    if (remote && API_URL) {
      api.post('/auth/logout', null, {
        withCredentials: true,
        timeout: 2000,
        __skipAuthRefresh: true,
      }).catch(() => {});
    }
    clearClientAuthState();
    if (redirect) {
      redirectToLogin(reason);
    }
  },

  isAuthenticated: () => {
    return !!getStoredAccessToken();
  },

  hasFreshAccessToken: () => {
    return isAccessTokenFresh(getStoredAccessToken());
  },

  hasSessionHint: () => {
    return !!getStoredAccessToken() || hasSessionHint();
  },

  persistAccessToken: (token) => {
    setStoredAccessToken(token);
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
    return cachedGet('/admin', {
      ttlMs: CACHE_TTLS_MS.adminDashboard,
    });
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
    return cachedGet('/kb_entries/paged', {
      params,
      ttlMs: CACHE_TTLS_MS.knowledgePaged,
    });
  },
  getTags: async (params = {}) => {
    return cachedGet('/kb_entries/tags', {
      params,
      ttlMs: CACHE_TTLS_MS.knowledgeTags,
    });
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
  startPracticeTask: async (taskId) => {
    await api.post(`/education/practice/tasks/${taskId}/start`);
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

  updateOnboardingStatus: async (status) => {
    const response = await api.put('/profile/onboarding', { status });
    invalidateGetCacheByPrefix('/profile');
    return response.data;
  },

  deleteAccount: async (username) => {
    const response = await api.delete('/profile', {
      data: { username },
    });
    invalidateGetCacheByPrefix('/profile');
    return response.data;
  },
};

export const contestAPI = {
  getActiveContest: async () => {
    return cachedGet('/contests/active', {
      ttlMs: CACHE_TTLS_MS.contestActive,
    });
  },
  joinContest: async (contestId) => {
    const response = await api.post(`/contests/${contestId}/join`);
    invalidateGetCacheByPrefix('/contests/active');
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
    invalidateGetCacheByPrefix('/contests/active');
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
  rateTask: async (contestId, taskId, rating) => {
    await api.post(`/contests/${contestId}/tasks/${taskId}/rate`, { rating });
  },
};

export const ratingsAPI = {
  getLeaderboard: async (kind = 'contest') => {
    return cachedGet('/ratings/leaderboard', {
      params: { kind },
      ttlMs: CACHE_TTLS_MS.ratingLeaderboard,
    });
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

export const pipelineAPI = {
  startGeneration: async (payload) => {
    const response = await api.post('/ai-generate/', payload);
    return response.data;
  },
  getBatchStatus: async (batchId) => {
    const response = await api.get(`/ai-generate/batch/${batchId}`);
    return response.data;
  },
  listBatches: async (params = {}) => {
    const response = await api.get('/ai-generate/batches', { params });
    return response.data;
  },
  publishVariant: async (batchId, variantId) => {
    const response = await api.post(`/ai-generate/batch/${batchId}/publish/${variantId}`);
    return response.data;
  },
  getVariantReview: async (batchId, variantId) => {
    const response = await api.get(`/ai-generate/batch/${batchId}/variant/${variantId}/review`);
    return response.data;
  },
  getAnalytics: async () => {
    return cachedGet('/ai-generate/analytics', { ttlMs: CACHE_TTLS_MS.adminDashboard });
  },
};

export default api;
