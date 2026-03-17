import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Profile from './Profile';

const mockNavigate = jest.fn();
let mockCurrentUser = null;

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useOutletContext: () => ({ currentUser: mockCurrentUser }),
}), { virtual: true });

jest.mock('../services/api', () => ({
  authAPI: {
    logout: jest.fn(),
  },
  profileAPI: {
    getProfile: jest.fn(),
    updateUsername: jest.fn(),
    updateEmail: jest.fn(),
    changePassword: jest.fn(),
    uploadAvatar: jest.fn(),
    deleteAccount: jest.fn(),
  },
}));

import { authAPI, profileAPI } from '../services/api';

describe('Profile page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCurrentUser = {
      username: 'cyberhero',
      email: 'user@example.com',
      contest_rating: 120,
      practice_rating: 80,
    };
  });

  it('requires matching username before deleting the account', async () => {
    profileAPI.deleteAccount.mockResolvedValue({ message: 'Аккаунт удалён' });

    render(<Profile />);

    await userEvent.click(screen.getByRole('button', { name: 'Удалить аккаунт' }));

    const confirmButton = screen.getByRole('button', { name: 'Удалить' });
    expect(confirmButton).toBeDisabled();

    await userEvent.type(screen.getByPlaceholderText('Впиши свой никнейм'), 'wrong-user');
    expect(confirmButton).toBeDisabled();

    await userEvent.clear(screen.getByPlaceholderText('Впиши свой никнейм'));
    await userEvent.type(screen.getByPlaceholderText('Впиши свой никнейм'), 'cyberhero');
    expect(confirmButton).toBeEnabled();

    await userEvent.click(confirmButton);

    await waitFor(() => {
      expect(profileAPI.deleteAccount).toHaveBeenCalledWith('cyberhero');
    });
    expect(authAPI.logout).toHaveBeenCalledWith({ remote: false, redirect: false });
    expect(mockNavigate).toHaveBeenCalledWith('/login?reason=account_deleted', { replace: true });
  });
});
