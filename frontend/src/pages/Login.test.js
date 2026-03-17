import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Login from './Login';

const mockNavigate = jest.fn();
let mockSearch = '';

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ search: mockSearch }),
}), { virtual: true });

jest.mock('../services/api', () => ({
  authAPI: {
    warmup: jest.fn(),
    login: jest.fn(),
    logout: jest.fn(),
    startYandexLogin: jest.fn(),
  },
  profileAPI: {
    getProfile: jest.fn(),
  },
}));

import { authAPI, profileAPI } from '../services/api';

describe('Login page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearch = '';
  });

  it('toggles password visibility', async () => {
    render(<Login />);

    const passwordInput = screen.getByPlaceholderText('Твой пароль от этой учетной записи');
    expect(passwordInput).toHaveAttribute('type', 'password');

    await userEvent.click(screen.getByLabelText('Показать пароль'));
    expect(passwordInput).toHaveAttribute('type', 'text');
  });

  it('starts Yandex login from the social button', async () => {
    render(<Login />);

    await userEvent.click(screen.getByRole('button', { name: 'Яндекс' }));
    expect(authAPI.startYandexLogin).toHaveBeenCalledTimes(1);
  });

  it('submits email/password login and navigates to home', async () => {
    const testEmail = ['user', 'example.com'].join('@');
    const testAccessPhrase = ['Strong', '!', '9', '2'].join('');

    authAPI.login.mockResolvedValue({ access_token: 'token' });
    profileAPI.getProfile.mockResolvedValue({ role: 'participant' });

    render(<Login />);

    await userEvent.type(screen.getByPlaceholderText('Твой адрес электронной почты'), testEmail);
    await userEvent.type(screen.getByPlaceholderText('Твой пароль от этой учетной записи'), testAccessPhrase);
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }));

    expect(authAPI.login).toHaveBeenCalledWith(testEmail, testAccessPhrase);
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/home', { replace: true });
    });
  });
});
