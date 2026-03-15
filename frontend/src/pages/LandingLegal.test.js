jest.mock('react-router-dom', () => ({
  Link: ({ to, children, ...rest }) => (
    <a href={to} {...rest}>
      {children}
    </a>
  ),
}), { virtual: true });

import { render, screen } from '@testing-library/react';

import LandingLegal from './LandingLegal';

describe('LandingLegal', () => {
  beforeEach(() => {
    window.scrollTo = jest.fn();
  });

  it('hides current privacy document link in footer', () => {
    render(<LandingLegal documentKey="privacy" />);

    expect(screen.getByRole('heading', { name: 'Политика конфиденциальности' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Согласие на получение рекламных и информационных материалов' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Общие условия использования платформы' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Политика конфиденциальности' })).not.toBeInTheDocument();
  });

  it('shows privacy and terms links on consent page', () => {
    render(<LandingLegal documentKey="marketing-consent" />);

    expect(screen.getByRole('heading', { name: 'Согласие на получение рекламных и информационных материалов' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Политика конфиденциальности' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Общие условия использования платформы' })).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Согласие на получение рекламных и информационных материалов' })
    ).not.toBeInTheDocument();
  });
});
