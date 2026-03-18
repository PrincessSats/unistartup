import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Register from './Register';

const mockNavigate = jest.fn();
let mockSearch = '';

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ search: mockSearch }),
}), { virtual: true });

jest.mock('../services/api', () => ({
  authAPI: {
    getRegistrationFlow: jest.fn(),
    startEmailRegistration: jest.fn(),
    attachEmailToRegistrationFlow: jest.fn(),
    resendEmailRegistration: jest.fn(),
    completeRegistration: jest.fn(),
    startGithubRegistration: jest.fn(),
    startTelegramRegistration: jest.fn(),
    startYandexRegistration: jest.fn(),
    persistAccessToken: jest.fn(),
  },
}));

import { authAPI } from '../services/api';

describe('Register page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearch = '';
  });

  it('starts email registration and shows the sent-link screen', async () => {
    authAPI.startEmailRegistration.mockResolvedValue({ flow_token: 'flow-1', email: 'user@example.com' });

    render(<Register />);

    await userEvent.type(screen.getByPlaceholderText('Твой адрес электронной почты'), 'user@example.com');
    await userEvent.click(screen.getByRole('checkbox', { name: /Я принимаю условия пользования/i }));
    await userEvent.click(screen.getByRole('button', { name: 'Зарегистрироваться' }));

    expect(authAPI.startEmailRegistration).toHaveBeenCalledWith({
      email: 'user@example.com',
      termsAccepted: true,
      marketingOptIn: false,
    });
    expect(await screen.findByText(/Отправили ссылку для входа на указанную почту/i)).toBeInTheDocument();
    expect(mockNavigate).toHaveBeenCalledWith('/register?flow_token=flow-1', { replace: true });
  });

  it('restores the flow, completes the questionnaire, and shows welcome screen', async () => {
    jest.useFakeTimers();
    mockSearch = '?flow_token=flow-2';

    authAPI.getRegistrationFlow.mockResolvedValue({
      flow_token: 'flow-2',
      source: 'yandex',
      intent: 'register',
      email: 'oauth@example.com',
      email_verified: true,
      step: 'details',
      provider: 'yandex',
      username_suggestion: 'yanhero',
      terms_accepted: true,
      marketing_opt_in: true,
    });
    authAPI.completeRegistration.mockResolvedValue({ access_token: 'issued-token' });

    render(<Register />);

    expect(await screen.findByDisplayValue('oauth@example.com')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Придумай пароль')).not.toBeInTheDocument();
    expect(screen.queryByText('Или зарегистрироваться через')).not.toBeInTheDocument();

    await userEvent.clear(screen.getByPlaceholderText('Придумай никнейм'));
    await userEvent.type(screen.getByPlaceholderText('Придумай никнейм'), 'cyberhero');
    await userEvent.click(screen.getByRole('button', { name: 'Продолжить' }));

    expect(await screen.findByText('cyberhero,')).toBeInTheDocument();

    await act(async () => {
      jest.advanceTimersByTime(1300);
    });

    await userEvent.click(screen.getByRole('button', { name: 'Разработчик' }));
    await userEvent.click(screen.getByRole('button', { name: 'Далее' }));

    await userEvent.click(screen.getByRole('button', { name: 'Middle' }));
    await userEvent.click(screen.getByRole('button', { name: 'Далее' }));

    await userEvent.click(screen.getByRole('button', { name: 'OSINT' }));
    await userEvent.click(screen.getByRole('button', { name: 'Завершить регистрацию' }));

    await waitFor(() => {
      expect(authAPI.completeRegistration).toHaveBeenCalledWith({
        flowToken: 'flow-2',
        username: 'cyberhero',
        password: null,
        professionTags: ['Разработчик'],
        grade: 'Middle',
        interestTags: ['OSINT'],
      });
    });

    expect(authAPI.persistAccessToken).toHaveBeenCalledWith('issued-token');
    expect(mockNavigate).toHaveBeenCalledWith('/home', { replace: true });
    jest.useRealTimers();
  });

  it('attaches email for telegram registration flow and sends magic link', async () => {
    mockSearch = '?flow_token=flow-3';
    authAPI.getRegistrationFlow.mockResolvedValue({
      flow_token: 'flow-3',
      source: 'telegram',
      intent: 'register',
      email: null,
      email_verified: false,
      step: 'email',
      provider: 'telegram',
      username_suggestion: 'telehero',
      terms_accepted: true,
      marketing_opt_in: false,
    });
    authAPI.attachEmailToRegistrationFlow.mockResolvedValue({
      flow_token: 'flow-3b',
      email: 'tele@example.com',
    });

    render(<Register />);

    expect(await screen.findByText(/Telegram аккаунт подключен/i)).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText('Твой адрес электронной почты'), 'tele@example.com');
    await userEvent.click(screen.getByRole('button', { name: 'Продолжить' }));

    expect(authAPI.attachEmailToRegistrationFlow).toHaveBeenCalledWith({
      flowToken: 'flow-3',
      email: 'tele@example.com',
      termsAccepted: true,
      marketingOptIn: false,
    });
    expect(await screen.findByText(/Отправили ссылку для входа на указанную почту/i)).toBeInTheDocument();
    expect(mockNavigate).toHaveBeenCalledWith('/register?flow_token=flow-3b', { replace: true });
  });
});
