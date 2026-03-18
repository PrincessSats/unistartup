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
    window.sessionStorage.setItem('layout:profile:v1', JSON.stringify({ username: 'stale-user' }));
    authAPI.logout({ remote: false, redirect: false });
    expect(window.localStorage.getItem('token')).toBeNull();
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
