import React from 'react';
import { Link } from 'react-router-dom';

import AppIcon from '../AppIcon';
import HacknetLogo from '../HacknetLogo';
import {
  LANDING_ROUTE_PREFIX,
  companyInfo,
  getVisibleLegalLinks,
  landingNavItems,
} from '../../lib/landingConfig';

function SecretTrigger({ secretBug, secretFound, onSecretFound, className = '' }) {
  if (!secretBug) return null;

  return (
    <button
      type="button"
      aria-label={secretBug.label}
      className={`landing-figma-bug ${secretFound ? 'is-found' : ''} ${className}`}
      onClick={() => onSecretFound?.(secretBug.key)}
      disabled={secretFound}
    >
      {secretFound ? (
        <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="m4.5 10.5 3.3 3.3L15.5 6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
          <path d="M10 3.75v12.5M3.75 10h12.5" strokeLinecap="round" />
        </svg>
      )}
    </button>
  );
}

function HeaderNav({ onNavigateSection }) {
  return (
    <nav className="landing-figma-header__nav" aria-label="Навигация по лендингу">
      {landingNavItems.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onNavigateSection?.(item.id)}
          className="landing-figma-header__link"
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}

function AuthActions() {
  return (
    <div className="landing-figma-header__actions">
      <Link to="/login" className="landing-figma-header__action landing-figma-header__action--light">
        Вход
      </Link>
      <Link to="/register" className="landing-figma-header__action landing-figma-header__action--accent">
        Регистрация
      </Link>
    </div>
  );
}

export function LandingHeader({ mode = 'home', onNavigateSection, currentLegalKey = null }) {
  return (
    <header className={`landing-figma-header ${mode === 'legal' ? 'is-legal' : ''}`}>
      <div className="landing-figma-header__inner">
        <Link to={LANDING_ROUTE_PREFIX} className="landing-figma-header__logo" aria-label="HackNet landing">
          <HacknetLogo className="h-[30px] w-[30px]" />
        </Link>

        {mode === 'home' ? (
          <>
            <HeaderNav onNavigateSection={onNavigateSection} />
            <AuthActions />
          </>
        ) : (
          <div className="landing-figma-header__legal-group">
            <span className="landing-figma-header__legal-badge">
              {currentLegalKey === 'privacy'
                ? 'Политика'
                : currentLegalKey === 'marketing-consent'
                  ? 'Согласие'
                  : 'Условия'}
            </span>
            <Link to={LANDING_ROUTE_PREFIX} className="landing-figma-header__action landing-figma-header__action--light">
              К лендингу
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}

export function LandingFooter({
  currentLegalKey = null,
  secretBug = null,
  secretFound = false,
  onSecretFound = null,
}) {
  const legalLinks = getVisibleLegalLinks(currentLegalKey);

  return (
    <footer className="landing-figma-footer">
      <div className="landing-figma-footer__top">
        <div className="landing-figma-footer__brand-card">
          <SecretTrigger
            secretBug={secretBug}
            secretFound={secretFound}
            onSecretFound={onSecretFound}
            className="landing-figma-footer__bug"
          />

          <div className="landing-figma-footer__brand-logo">
            <HacknetLogo className="h-[34px] w-[34px]" />
          </div>

          <div className="landing-figma-footer__brand-bottom">
            <p className="landing-figma-footer__brand-text">
              Чемпионаты по хакингу, обучение и База знаний для профессионалов, новичков и бизнеса
            </p>

            <div className="landing-figma-footer__contact-buttons">
              <a
                href={companyInfo.telegramUrl}
                target="_blank"
                rel="noreferrer"
                className="landing-figma-footer__contact-button"
              >
                <AppIcon name="support" className="h-5 w-5" />
                <span>Телеграм</span>
              </a>
              <a href={`mailto:${companyInfo.email}`} className="landing-figma-footer__contact-button">
                <AppIcon name="doc" className="h-5 w-5" />
                <span>Почта</span>
              </a>
            </div>
          </div>
        </div>

        <div className="landing-figma-footer__info-card">
          <div className="landing-figma-footer__info-columns">
            <section className="landing-figma-footer__info-block">
              <h3>О компании</h3>
              <p>{companyInfo.company}</p>
            </section>

            <section className="landing-figma-footer__info-block">
              <h3>При поддержке</h3>
              <p>{companyInfo.support}</p>
            </section>
          </div>

          <div className="landing-figma-footer__meta">
            <div className="landing-figma-footer__legal-links">
              {legalLinks.map((document) => (
                <Link key={document.key} to={document.path} className="landing-figma-footer__legal-link">
                  {document.title}
                </Link>
              ))}
            </div>

            <div className="landing-figma-footer__socials">
              <a
                href="https://github.com/"
                target="_blank"
                rel="noreferrer"
                className="landing-figma-footer__social"
                aria-label="GitHub"
              >
                <AppIcon name="knowledge" className="h-5 w-5" />
              </a>
              <a
                href={`mailto:${companyInfo.email}`}
                className="landing-figma-footer__social"
                aria-label="Email"
              >
                <AppIcon name="doc" className="h-5 w-5" />
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className="landing-figma-footer__wordmark">HackNet</div>
    </footer>
  );
}
