import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

import { LandingFooter, LandingHeader } from '../components/landing/LandingChrome';
import LandingPromoModal from '../components/landing/LandingPromoModal';
import {
  landingAudienceTabs,
  landingBenefitCards,
  landingChampionshipSlides,
  landingFaqItems,
  landingHeroDesign,
  landingLearningCards,
  landingLearningPanel,
  landingTrackerIcon,
  landingWaitlistCloud,
} from '../lib/landingDesign';
import {
  LANDING_HUNT_SESSION_STORAGE_KEY,
  landingHuntBugs,
} from '../lib/landingConfig';
import { landingAPI } from '../services/api';

const COOKIE_STORAGE_KEY = 'landing:cookie-banner-dismissed:v1';

function RevealBlock({ children, className = '', delay = 0 }) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setVisible(true);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.16 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`landing-figma-reveal ${visible ? 'is-visible' : ''} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

function BugButton({ bug, found, onFound, className = '' }) {
  return (
    <button
      type="button"
      aria-label={bug.label}
      className={`landing-figma-bug ${found ? 'is-found' : ''} ${className}`}
      onClick={() => onFound(bug.key)}
      disabled={found}
    >
      {found ? (
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

function SectionHeading({ tag, title, description, className = '' }) {
  return (
    <div className={`landing-figma-section-heading ${className}`.trim()}>
      <span className="landing-figma-tag">{tag}</span>
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
    </div>
  );
}

function BenefitCard({ card }) {
  if (card.id === 'championships') {
    return (
      <article className="landing-figma-benefit-card landing-figma-benefit-card--violet">
        <div className="landing-figma-benefit-card__avatars">
          {card.participantAvatars.map((avatar) => (
            <img key={avatar} src={avatar} alt="" />
          ))}
          <span className="landing-figma-benefit-card__avatars-more">
            <img src={card.extraAvatar} alt="" />
            <strong>{card.participantsValue}</strong>
          </span>
        </div>
        <p className="landing-figma-benefit-card__muted">{card.participantsLabel}</p>
        <h3>{card.title}</h3>
      </article>
    );
  }

  if (card.id === 'progress') {
    return (
      <article className="landing-figma-benefit-card landing-figma-benefit-card--blue">
        <div>
          <h3>{card.title}</h3>
          <p className="landing-figma-benefit-card__body">{card.description}</p>
        </div>
        <div className="landing-figma-score-list">
          {card.stats.map((stat) => (
            <div key={stat.label} className="landing-figma-score-list__row">
              <div className="landing-figma-score-list__value">
                <span>{stat.value}</span>
                <small className={stat.deltaTone === 'up' ? 'is-up' : 'is-down'}>{stat.delta}</small>
              </div>
              <span className="landing-figma-score-list__label">{stat.label}</span>
            </div>
          ))}
        </div>
      </article>
    );
  }

  if (card.id === 'practice') {
    return (
      <article className="landing-figma-benefit-card landing-figma-benefit-card--dark">
        <img src={card.figureImage} alt="" className="landing-figma-benefit-card__figure" />
        <h3>{card.title}</h3>
        <div className="landing-figma-benefit-card__badge">
          <strong>{card.badgeTitle}</strong>
          <span>{card.badgeSubtitle}</span>
        </div>
      </article>
    );
  }

  return (
    <article className="landing-figma-benefit-card landing-figma-benefit-card--light">
      <div>
        <h3>{card.title}</h3>
        <p className="landing-figma-benefit-card__body landing-figma-benefit-card__body--dark">
          {card.description}
        </p>
      </div>
      <div className="landing-figma-benefit-card__stack">
        {card.figureImages.map((image, index) => (
          <img
            key={image}
            src={image}
            alt=""
            className={index === 0 ? 'is-back' : 'is-front'}
          />
        ))}
      </div>
    </article>
  );
}

function ChampionshipPanel({ slide }) {
  if (slide.composition === 'flow') {
    return (
      <div className="landing-figma-championship__visual landing-figma-championship__visual--flow">
        {slide.panelLayers.map((layer) => (
          <img key={layer.image} src={layer.image} alt="" className={layer.className} />
        ))}
      </div>
    );
  }

  if (slide.composition === 'formats') {
    return (
      <div className="landing-figma-championship__visual landing-figma-championship__visual--formats">
        <div className="landing-figma-chip-grid">
          {slide.badges.map((badge) => (
            <span key={badge} className="landing-figma-chip-grid__item">
              {badge}
            </span>
          ))}
        </div>
        <img src={slide.panelImage} alt="" className="landing-figma-championship__screen" />
      </div>
    );
  }

  if (slide.composition === 'rating') {
    return (
      <div className="landing-figma-championship__visual landing-figma-championship__visual--rating">
        <img src={slide.panelImage} alt="" className="landing-figma-championship__screen landing-figma-championship__screen--rating" />
        <div className="landing-figma-rating-float">
          <span>{slide.floatingScore.place}</span>
          <strong>{slide.floatingScore.user}</strong>
          <span>{slide.floatingScore.score}</span>
          <span>{slide.floatingScore.firstBlood}</span>
          <span>{slide.floatingScore.solved}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="landing-figma-championship__visual landing-figma-championship__visual--fallback">
      <img src={slide.panelImage} alt="" className="landing-figma-championship__screen landing-figma-championship__screen--fallback" />
      <div className="landing-figma-hint-popup">
        <div className="landing-figma-hint-popup__art">
          <img src={slide.hintPopup.imageOne} alt="" className="landing-figma-hint-popup__art-main" />
          <img src={slide.hintPopup.imageTwo} alt="" className="landing-figma-hint-popup__art-side" />
        </div>
        <div className="landing-figma-hint-popup__body">
          <strong>{slide.hintPopup.title}</strong>
          <p>{slide.hintPopup.body}</p>
          <button type="button">{slide.hintPopup.action}</button>
        </div>
      </div>
    </div>
  );
}

function LearningCard({ card }) {
  return (
    <article className="landing-figma-learning-card">
      <p className="landing-figma-learning-card__body">{card.body}</p>
      <strong className="landing-figma-learning-card__title">{card.title}</strong>

      <div className={`landing-figma-learning-card__stack ${card.id === 'practice' ? 'is-reversed' : ''}`}>
        <div className={`landing-figma-learning-card__mini landing-figma-learning-card__mini--back ${card.id === 'practice' ? 'is-light' : 'is-violet'}`}>
          <span>{card.backLabel}</span>
          <img src={card.backImage} alt="" />
        </div>
        <div className={`landing-figma-learning-card__mini landing-figma-learning-card__mini--front ${card.id === 'practice' ? 'is-blue' : 'is-light'}`}>
          <span>{card.frontLabel}</span>
          <img src={card.frontImage} alt="" />
        </div>
      </div>
    </article>
  );
}

function AudienceCard({ card }) {
  return (
    <article className={`landing-figma-audience-card landing-figma-audience-card--${card.tone}`}>
      <div className="landing-figma-audience-card__dots" aria-hidden="true" />
      <div className="landing-figma-audience-card__copy">
        <h3>{card.title}</h3>
        <p>{card.body}</p>
      </div>
      <img src={card.image} alt="" className="landing-figma-audience-card__image" />
      {card.locked ? (
        <span className="landing-figma-audience-card__lock">
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
            <rect x="5.5" y="9" width="9" height="6.8" rx="1.8" />
            <path d="M7.6 9V7.3A2.4 2.4 0 0 1 10 4.9a2.4 2.4 0 0 1 2.4 2.4V9" strokeLinecap="round" />
          </svg>
        </span>
      ) : null}
    </article>
  );
}

function FaqItem({ item, open, onToggle }) {
  return (
    <article className={`landing-figma-faq-item ${open ? 'is-open' : ''}`}>
      <button type="button" className="landing-figma-faq-item__trigger" onClick={onToggle}>
        <span>{item.question}</span>
        <span className="landing-figma-faq-item__chevron">
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6">
            <path d="m6 8 4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </button>

      <div className="landing-figma-faq-item__panel">
        <p>{item.answer}</p>
      </div>
    </article>
  );
}

function HuntTracker({ huntState, huntError }) {
  return (
    <>
      <div className="landing-figma-tracker">
        <div className="landing-figma-tracker__icon">
          <img src={landingTrackerIcon} alt="" />
        </div>
        <span className="landing-figma-tracker__label">Найдено багов</span>
        <span className="landing-figma-tracker__divider" aria-hidden="true" />
        <span className="landing-figma-tracker__count">
          {huntState.found_count}/{huntState.total_count}
        </span>
      </div>
      {huntError ? <p className="landing-figma-tracker-error">{huntError}</p> : null}
    </>
  );
}

export default function Landing() {
  const benefitsRef = useRef(null);
  const championshipsRef = useRef(null);
  const learningRef = useRef(null);
  const audienceRef = useRef(null);
  const faqRef = useRef(null);
  const audienceRailRef = useRef(null);

  const [championshipIndex, setChampionshipIndex] = useState(0);
  const [audienceTab, setAudienceTab] = useState(landingAudienceTabs[0].id);
  const [openFaqIndex, setOpenFaqIndex] = useState(0);
  const [promoModalOpen, setPromoModalOpen] = useState(false);
  const [cookieDismissed, setCookieDismissed] = useState(() =>
    window.localStorage.getItem(COOKIE_STORAGE_KEY) === '1'
  );
  const [huntBusy, setHuntBusy] = useState(false);
  const [huntError, setHuntError] = useState('');
  const [huntState, setHuntState] = useState({
    session_token: '',
    found_bug_keys: [],
    found_count: 0,
    total_count: landingHuntBugs.length,
    completed: false,
    promo_code: '',
  });

  const audienceCards = landingAudienceTabs.find((tab) => tab.id === audienceTab)?.cards || [];
  const activeSlide = landingChampionshipSlides[championshipIndex];

  useEffect(() => {
    window.document.title = 'HackNet | Главная';
    window.scrollTo(0, 0);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const bootstrapHunt = async () => {
      try {
        const storedSessionToken = window.localStorage.getItem(LANDING_HUNT_SESSION_STORAGE_KEY);
        const response = await landingAPI.getHuntSession(storedSessionToken);
        if (cancelled) return;

        window.localStorage.setItem(LANDING_HUNT_SESSION_STORAGE_KEY, response.session_token);
        setHuntState(response);
        if (response.completed && response.promo_code) {
          setPromoModalOpen(true);
        }
      } catch (error) {
        if (cancelled) return;
        setHuntError(
          error?.response?.data?.detail || 'Не удалось инициализировать интерактив. Попробуйте обновить страницу.'
        );
      }
    };

    bootstrapHunt();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const rail = audienceRailRef.current;
    if (rail) {
      rail.scrollTo({ left: 0, behavior: 'smooth' });
    }
  }, [audienceTab]);

  const handleNavigateSection = (sectionId) => {
    const mapping = {
      benefits: benefitsRef,
      championships: championshipsRef,
      learning: learningRef,
      audience: audienceRef,
      faq: faqRef,
    };
    mapping[sectionId]?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const handleFoundBug = async (bugKey) => {
    if (huntBusy || huntState.found_bug_keys.includes(bugKey)) return;
    setHuntBusy(true);
    setHuntError('');

    try {
      const response = await landingAPI.markBugFound(huntState.session_token, bugKey);
      window.localStorage.setItem(LANDING_HUNT_SESSION_STORAGE_KEY, response.session_token);
      setHuntState(response);
      if (response.just_completed && response.promo_code) {
        setPromoModalOpen(true);
      }
    } catch (error) {
      setHuntError(error?.response?.data?.detail || 'Не удалось зафиксировать находку.');
    } finally {
      setHuntBusy(false);
    }
  };

  const handleDismissCookies = () => {
    setCookieDismissed(true);
    window.localStorage.setItem(COOKIE_STORAGE_KEY, '1');
  };

  const scrollAudience = (direction) => {
    const rail = audienceRailRef.current;
    if (!rail) return;
    const offset = rail.clientWidth * 0.72 * direction;
    rail.scrollBy({ left: offset, behavior: 'smooth' });
  };

  const getBug = (key) => landingHuntBugs.find((item) => item.key === key);
  const isBugFound = (key) => huntState.found_bug_keys.includes(key);

  return (
    <div className="landing-figma-page font-sans-figma text-white">
      <LandingHeader onNavigateSection={handleNavigateSection} />

      <main className="landing-figma-main">
        <section className="landing-figma-hero">
          <div
            className="landing-figma-hero__background"
            style={{ backgroundImage: `url(${landingHeroDesign.backgroundImage})` }}
          />
          <div className="landing-figma-hero__overlay" />

          <div className="landing-figma-shell landing-figma-hero__content">
            <BugButton
              bug={getBug('hero_console')}
              found={isBugFound('hero_console')}
              onFound={handleFoundBug}
              className="landing-figma-bug--hero"
            />

            <RevealBlock className="landing-figma-hero__copy">
              <span className="landing-figma-hero__eyebrow">{landingHeroDesign.eyebrow}</span>
              <h1>{landingHeroDesign.title}</h1>

              <div className="landing-figma-hero__pills">
                <span className="is-active">Чемпионаты по хакингу</span>
                <span>Реальные задачи</span>
                <span>База знаний</span>
              </div>

              <p className="landing-figma-hero__subtitle">{landingHeroDesign.subtitle}</p>
            </RevealBlock>

            {!cookieDismissed ? (
              <div className="landing-figma-cookie">
                <p>{landingHeroDesign.cookies}</p>
                <button type="button" onClick={handleDismissCookies}>
                  Принять
                </button>
              </div>
            ) : null}
          </div>
        </section>

        <section ref={benefitsRef} className="landing-figma-section landing-figma-section--benefits">
          <div className="landing-figma-shell">
            <RevealBlock>
              <SectionHeading
                tag="Наши преимущества"
                title="Все в одном месте: обучение и практика для хакеров!"
                description="Растащи карточки"
              />
            </RevealBlock>

            <RevealBlock className="landing-figma-benefits-layout" delay={90}>
              <div className="landing-figma-benefits-layout__purple">
                <BenefitCard card={landingBenefitCards[0]} />
              </div>
              <div className="landing-figma-benefits-layout__dark">
                <BenefitCard card={landingBenefitCards[1]} />
              </div>
              <div className="landing-figma-benefits-layout__blue">
                <BenefitCard card={landingBenefitCards[2]} />
              </div>
              <div className="landing-figma-benefits-layout__light">
                <BenefitCard card={landingBenefitCards[3]} />
              </div>
            </RevealBlock>
          </div>
        </section>

        <section ref={championshipsRef} className="landing-figma-section">
          <div className="landing-figma-shell">
            <RevealBlock>
              <SectionHeading
                tag="Чемпионаты"
                title="Соревнуйся регулярно"
                description="Турнир состоит из заданий на поиск флагов. Тебе предстоит найти уязвимости в системе: чем больше флагов найдешь — тем больше баллов получишь"
              />
            </RevealBlock>

            <RevealBlock className="landing-figma-championship" delay={70}>
              <div className="landing-figma-championship__tabs">
                {landingChampionshipSlides.map((slide, index) => (
                  <button
                    key={slide.id}
                    type="button"
                    className={index === championshipIndex ? 'is-active' : ''}
                    onClick={() => setChampionshipIndex(index)}
                  >
                    {slide.tabLabel}
                  </button>
                ))}
              </div>

              <div className="landing-figma-championship__card">
                <div className="landing-figma-championship__copy">
                  <BugButton
                    bug={getBug('championship_card')}
                    found={isBugFound('championship_card')}
                    onFound={handleFoundBug}
                    className="landing-figma-bug--championship"
                  />

                  <span className="landing-figma-championship__tag">{activeSlide.tagLabel}</span>
                  <p>{activeSlide.title}</p>
                </div>

                <ChampionshipPanel slide={activeSlide} />
              </div>

              <div className="landing-figma-dots" aria-hidden="true">
                {landingChampionshipSlides.map((slide, index) => (
                  <span key={slide.id} className={index === championshipIndex ? 'is-active' : ''} />
                ))}
              </div>
            </RevealBlock>
          </div>
        </section>

        <section ref={learningRef} className="landing-figma-section">
          <div className="landing-figma-shell">
            <RevealBlock>
              <SectionHeading
                tag="Теория и практика"
                title="У нас обучение не заканчивается на теории"
                description="После каждого модуля тебя ждет боевое задание, чтобы проверить знания на практике. Решай сам - совмещать разделы или учиться только теории. Успехи в обучении можешь отслеживать в отдельном рейтинге"
                className="landing-figma-section-heading--wide"
              />
            </RevealBlock>

            <div className="landing-figma-learning-grid">
              <RevealBlock className="landing-figma-learning-grid__cards" delay={70}>
                {landingLearningCards.map((card) => (
                  <LearningCard key={card.id} card={card} />
                ))}
              </RevealBlock>

              <RevealBlock className="landing-figma-learning-panel" delay={120}>
                <BugButton
                  bug={getBug('learning_split')}
                  found={isBugFound('learning_split')}
                  onFound={handleFoundBug}
                  className="landing-figma-bug--learning"
                />

                <p className="landing-figma-learning-panel__title">{landingLearningPanel.title}</p>
                <div className="landing-figma-learning-panel__progress">
                  <span />
                  <span />
                  <span className="is-active" />
                  <span />
                </div>
                <img src={landingLearningPanel.decorImage} alt="" className="landing-figma-learning-panel__decor" />
                <img src={landingLearningPanel.glowImage} alt="" className="landing-figma-learning-panel__glow" />
                <div className="landing-figma-learning-panel__toast">
                  <strong>{landingLearningPanel.toastTitle}</strong>
                  <p>{landingLearningPanel.toastBody}</p>
                </div>
              </RevealBlock>
            </div>
          </div>
        </section>

        <section ref={audienceRef} className="landing-figma-section">
          <div className="landing-figma-shell">
            <RevealBlock>
              <SectionHeading
                tag="Для кого платформа"
                title="Собрали все, что тебе нужно сейчас. Выбери свой опыт и проверь!"
                description=""
              />
            </RevealBlock>

            <RevealBlock className="landing-figma-audience" delay={70}>
              <div className="landing-figma-audience__tabs">
                {landingAudienceTabs.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={tab.id === audienceTab ? 'is-active' : ''}
                    onClick={() => setAudienceTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="landing-figma-audience__rail-wrap">
                <BugButton
                  bug={getBug('audience_slider')}
                  found={isBugFound('audience_slider')}
                  onFound={handleFoundBug}
                  className="landing-figma-bug--audience"
                />

                <div ref={audienceRailRef} className="landing-figma-audience__rail">
                  {audienceCards.map((card) => (
                    <AudienceCard key={`${audienceTab}-${card.title}`} card={card} />
                  ))}
                </div>
              </div>

              <div className="landing-figma-audience__controls">
                <button type="button" onClick={() => scrollAudience(-1)} aria-label="Назад">
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7">
                    <path d="m12 5-5 5 5 5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
                <button type="button" onClick={() => scrollAudience(1)} aria-label="Вперед">
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7">
                    <path d="m8 5 5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </div>
            </RevealBlock>
          </div>
        </section>

        <section ref={faqRef} className="landing-figma-section landing-figma-section--faq">
          <div className="landing-figma-shell">
            <div className="landing-figma-faq">
              <RevealBlock className="landing-figma-faq__hero">
                <div className="landing-figma-faq__hero-content">
                  <span className="landing-figma-tag">FAQ</span>
                  <h2>Все, что хочется узнать, но страшно спросить</h2>
                  <p>
                    Остались вопросы? Напиши в <a href="https://t.me/hacknet_support" target="_blank" rel="noreferrer">поддержку</a>
                  </p>
                </div>
              </RevealBlock>

              <RevealBlock className="landing-figma-faq__list" delay={70}>
                <BugButton
                  bug={getBug('faq_console')}
                  found={isBugFound('faq_console')}
                  onFound={handleFoundBug}
                  className="landing-figma-bug--faq"
                />

                {landingFaqItems.map((item, index) => (
                  <FaqItem
                    key={item.question}
                    item={item}
                    open={index === openFaqIndex}
                    onToggle={() => setOpenFaqIndex(index === openFaqIndex ? -1 : index)}
                  />
                ))}
              </RevealBlock>
            </div>
          </div>
        </section>

        <section className="landing-figma-section landing-figma-section--waitlist">
          <div className="landing-figma-shell">
            <RevealBlock className="landing-figma-waitlist">
              <div className="landing-figma-waitlist__badge">
                <span className="landing-figma-waitlist__badge-avatar" />
                Осталось мест: 624 / 1000
              </div>

              <h2>Для первых 1000 участников оставим платформу бесплатной навсегда</h2>
              <p>
                Присоединись сейчас, пройди верификацию и пользуйся платформой и всеми новыми фишками
                бесплатно
              </p>

              <Link to="/register" className="landing-figma-waitlist__cta">
                Регистрация
              </Link>

              <div className="landing-figma-waitlist__cloud" aria-hidden="true">
                {landingWaitlistCloud.map((chip) => (
                  <span key={chip.label} style={{ left: chip.left, top: chip.top }}>
                    {chip.label}
                  </span>
                ))}
              </div>
            </RevealBlock>
          </div>
        </section>
      </main>

      <LandingFooter
        secretBug={getBug('footer_logo')}
        secretFound={isBugFound('footer_logo')}
        onSecretFound={handleFoundBug}
      />

      <HuntTracker huntState={huntState} huntError={huntError} />
      <LandingPromoModal
        open={promoModalOpen}
        promoCode={huntState.promo_code}
        onClose={() => setPromoModalOpen(false)}
      />
    </div>
  );
}
