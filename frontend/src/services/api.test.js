var mockAxiosInstance;

jest.mock('axios', () => {
  mockAxiosInstance = {
    get: jest.fn(),
    post: jest.fn(() => Promise.resolve({ data: {} })),
    put: jest.fn(),
    delete: jest.fn(() => Promise.resolve({ data: {} })),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  };
  return {
    create: jest.fn(() => mockAxiosInstance),
  };
});

import { authAPI, profileAPI } from './api';

function encodeBase64Url(payload) {
  return window.btoa(JSON.stringify(payload))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

function buildToken(expSeconds) {
  const header = encodeBase64Url({ alg: 'HS256', typ: 'JWT' });
  const body = encodeBase64Url({ sub: 'user@example.com', exp: expSeconds });
  return `${header}.${body}.signature`;
}

describe('authAPI token freshness', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    jest.clearAllMocks();
  });

  it('treats future exp token as authenticated', () => {
    const exp = Math.floor(Date.now() / 1000) + 300;
    window.localStorage.setItem('token', buildToken(exp));
    expect(authAPI.hasFreshAccessToken()).toBe(true);
  });

  it('treats expired token as unauthenticated', () => {
    const exp = Math.floor(Date.now() / 1000) - 60;
    window.localStorage.setItem('token', buildToken(exp));
    expect(authAPI.hasFreshAccessToken()).toBe(false);
  });

  it('logout clears stored token', () => {
    const exp = Math.floor(Date.now() / 1000) + 300;
    window.localStorage.setItem('token', buildToken(exp));
    window.localStorage.setItem('auth_session_hint', '1');
    window.sessionStorage.setItem('layout:profile:v1', JSON.stringify({ username: 'stale-user' }));
    authAPI.logout({ remote: false, redirect: false });
    expect(window.localStorage.getItem('token')).toBeNull();
    expect(window.localStorage.getItem('auth_session_hint')).toBeNull();
    expect(window.sessionStorage.getItem('layout:profile:v1')).toBeNull();
  });

  it('bootstrap skips refresh for guests without a session hint', async () => {
    const result = await authAPI.bootstrapAuth();

    expect(result.authenticated).toBe(false);
    expect(result.reason).toBeNull();
    expect(mockAxiosInstance.post).not.toHaveBeenCalled();
  });

  it('bootstrap keeps current session state on refresh timeout', async () => {
    const exp = Math.floor(Date.now() / 1000) - 60;
    const staleToken = buildToken(exp);
    window.localStorage.setItem('token', staleToken);
    window.localStorage.setItem('auth_session_hint', '1');
    mockAxiosInstance.post.mockRejectedValueOnce({
      code: 'ECONNABORTED',
      message: 'timeout of 15000ms exceeded',
    });

    const result = await authAPI.bootstrapAuth();

    expect(result.authenticated).toBe(true);
    expect(result.reason).toBeNull();
    expect(window.localStorage.getItem('token')).toBe(staleToken);
    expect(window.localStorage.getItem('auth_session_hint')).toBe('1');
  });

  it('bootstrap clears auth state after refresh 401', async () => {
    const exp = Math.floor(Date.now() / 1000) - 60;
    window.localStorage.setItem('token', buildToken(exp));
    window.localStorage.setItem('auth_session_hint', '1');
    window.sessionStorage.setItem('layout:profile:v1', JSON.stringify({ username: 'stale-user' }));
    mockAxiosInstance.post.mockRejectedValueOnce({
      response: {
        status: 401,
        data: { detail: 'Сессия истекла. Выполните вход снова.' },
      },
    });

    const result = await authAPI.bootstrapAuth();

    expect(result.authenticated).toBe(false);
    expect(result.reason).toBe('session_expired');
    expect(window.localStorage.getItem('token')).toBeNull();
    expect(window.localStorage.getItem('auth_session_hint')).toBeNull();
    expect(window.sessionStorage.getItem('layout:profile:v1')).toBeNull();
  });

  it('profile delete sends confirmation username', async () => {
    mockAxiosInstance.delete.mockResolvedValue({ data: {} });

    await profileAPI.deleteAccount('cyberhero');

    expect(mockAxiosInstance.delete).toHaveBeenCalledWith('/profile', {
      data: { username: 'cyberhero' },
    });
  });
});
