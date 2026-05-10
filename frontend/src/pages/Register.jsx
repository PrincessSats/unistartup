import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import AppIcon from '../components/AppIcon';
import {
  AuthPrimaryButton,
  AuthShell,
  AuthSurface,
  PasswordVisibilityButton,
  SocialAuthButtons,
} from '../components/AuthUI';
import { authAPI } from '../services/api';
import TermsModal from '../components/TermsModal';

const PROFESSION_OPTIONS = [
  'Студент',
  'Хакер',
  'Разработчик',
  'Тестировщик',
  'Аналитик',
  'Специалист информационной безопасности',
  'Другое',
];

const GRADE_OPTIONS = [
  'Новичок',
  'Junior',
  'Middle',
  'Senior',
  'Lead / Principal',
  'CISO / Руководитель',
];

const INTEREST_OPTIONS = [
  'Веб',
  'Криптография',
  'Форензика',
  'Реверс-инжиниринг',
  'Стеганография',
  'OSINT',
  'PVN',
  'Pentest Machines',
  'Все варианты',
];

function mapRegistrationError(code) {
  switch (code) {
    case 'invalid_magic_link':
      return 'Ссылка недействительна. Запроси письмо повторно и попробуй еще раз.';
    case 'expired_magic_link':
      return 'Срок действия ссылки истек. Отправь письмо заново.';
    case 'registration_already_completed':
      return 'Эта регистрация уже завершена. Войди в учетную запись.';
    case 'yandex_access_denied':
      return 'Авторизация через Яндекс была отменена.';
    case 'yandex_missing_code':
    case 'yandex_state_invalid':
      return 'Сессия входа через Яндекс устарела. Начни регистрацию заново.';
    case 'yandex_oauth_failed':
      return 'Не удалось получить данные из Яндекса. Попробуй еще раз.';
    case 'github_access_denied':
      return 'Авторизация через GitHub была отменена.';
    case 'github_missing_code':
    case 'github_state_invalid':
      return 'Сессия входа через GitHub устарела. Начни регистрацию заново.';
    case 'github_oauth_failed':
      return 'Не удалось получить данные из GitHub. Попробуй еще раз.';
    default:
      return '';
  }
}

function splitIdentityParts(...values) {
  const parts = [];
  values.forEach((value) => {
    const normalized = String(value || '').trim().toLowerCase();
    if (!normalized) return;
    normalized.split(/[^a-z0-9]+/).forEach((part) => {
      if (part.length >= 3 && !parts.includes(part)) {
        parts.push(part);
      }
    });
  });
  return parts;
}

function hasForbiddenSequence(password) {
  const normalized = String(password || '').toLowerCase();
  const sources = ['abcdefghijklmnopqrstuvwxyz', '0123456789'];
  for (let sourceIndex = 0; sourceIndex < sources.length; sourceIndex += 1) {
    const source = sources[sourceIndex];
    for (let length = 4; length <= 6; length += 1) {
      for (let index = 0; index <= source.length - length; index += 1) {
        const chunk = source.slice(index, index + length);
        if (normalized.includes(chunk) || normalized.includes(chunk.split('').reverse().join(''))) {
          return true;
        }
      }
    }
  }
  return Array.from(new Set(normalized)).some((char) => char && normalized.includes(char.repeat(4)));
}

function getPasswordChecks(password, { username, email, providerLogin }) {
  const value = String(password || '');
  const emailLocal = String(email || '').toLowerCase().split('@', 1)[0];
  const identityParts = splitIdentityParts(username, emailLocal, providerLogin);
  const lower = value.toLowerCase();
  const containsPersonalInfo = identityParts.some((part) => lower.includes(part));

  return [
    {
      label: 'Только латинские буквы, цифры и спецсимволы',
      passed: /^[\x21-\x7E]+$/.test(value),
    },
    {
      label: 'Минимум 8 символов',
      passed: value.length >= 8,
    },
    {
      label: 'Минимум одна заглавная буква',
      passed: /[A-Z]/.test(value),
    },
    {
      label: 'Хотя бы одна цифра',
      passed: /\d/.test(value),
    },
    {
      label: 'Есть специальный символ',
      passed: /[^A-Za-z0-9]/.test(value),
    },
    {
      label: 'Не содержит личных данных',
      passed: !containsPersonalInfo,
    },
    {
      label: 'Не повторяет простые последовательности',
      passed: !hasForbiddenSequence(value),
    },
  ];
}

function Banner({ tone = 'error', children }) {
  const classes = tone === 'notice'
    ? 'border-sky-400/25 bg-sky-400/10 text-sky-50'
    : 'border-[#FF5A6E]/35 bg-[#FF5A6E]/10 text-[#FFD6DB]';

  return (
    <div className={`rounded-[18px] border px-4 py-3 text-[14px] leading-6 ${classes}`}>
      {children}
    </div>
  );
}

function ConsentCheckbox({ checked, onChange, children }) {
  return (
    <label className="flex cursor-pointer items-start gap-3">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="sr-only"
      />
      <span
        className={[
          'mt-0.5 flex h-[17px] w-[17px] shrink-0 items-center justify-center rounded-[4px] transition',
          checked ? 'bg-[#8C5EFF] text-white' : 'bg-white/[0.05] text-transparent',
        ].join(' ')}
        aria-hidden="true"
      >
        <AppIcon name="check-circle" className="h-2.5 w-2.5" />
      </span>
      <span>{children}</span>
    </label>
  );
}

function QuestionOption({ label, selected, onToggle, single = false, compact = false }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={[
        'flex w-full items-center gap-4 rounded-[18px] border px-4 text-left transition',
        compact ? 'min-h-[52px] py-3' : 'min-h-[76px] py-4',
        selected
          ? 'border-[#8D63FF] bg-[#1B1430] text-white'
          : 'border-white/10 bg-white/[0.03] text-white/82 hover:border-white/20 hover:bg-white/[0.05]',
      ].join(' ')}
    >
      <span
        className={[
          'flex h-5 w-5 shrink-0 items-center justify-center border transition',
          single ? 'rounded-full' : 'rounded-[6px]',
          selected ? 'border-[#8452FF] bg-[#8452FF]' : 'border-white/24 bg-transparent',
        ].join(' ')}
      >
        {selected ? (
          single ? <span className="h-2.5 w-2.5 rounded-full bg-white" /> : <AppIcon name="check-circle" className="h-3.5 w-3.5" />
        ) : null}
      </span>
      <span className="text-[15px] leading-6">{label}</span>
    </button>
  );
}

function Register() {
  const navigate = useNavigate();
  const location = useLocation();
  const [step, setStep] = useState('email');
  const [registrationSource, setRegistrationSource] = useState('email_magic_link');
  const [loading, setLoading] = useState(false);
  const [loadingFlow, setLoadingFlow] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [flowToken, setFlowToken] = useState('');
  const [providerLogin, setProviderLogin] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showPasswordHints, setShowPasswordHints] = useState(false);
  const [successName, setSuccessName] = useState('CyberNinja');
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
  });
  const [showTerms, setShowTerms] = useState(false);
  const [consents, setConsents] = useState({
    terms: false,
    marketing: false,
  });
  const [questionnaire, setQuestionnaire] = useState({
    professionTags: [],
    grade: '',
    interestTags: [],
  });
  const isOAuthContinuation = registrationSource !== 'email_magic_link';

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const incomingFlowToken = String(params.get('flow_token') || '').trim();
    const incomingError = String(params.get('error') || '').trim();

    if (incomingError) {
      setError(mapRegistrationError(incomingError) || 'Не удалось продолжить регистрацию.');
      setNotice('');
    }

    if (!incomingFlowToken) {
      setLoadingFlow(false);
      return;
    }

    let cancelled = false;
    setLoadingFlow(true);

    authAPI.getRegistrationFlow({ flowToken: incomingFlowToken })
      .then((flow) => {
        if (cancelled) return;
        setFlowToken(flow.flow_token);
        setRegistrationSource(flow.source || 'email_magic_link');
        setProviderLogin(flow.username_suggestion || '');
        setFormData((current) => ({
          ...current,
          email: flow.email || current.email,
          username: current.username || flow.username_suggestion || '',
          password: flow.source === 'email_magic_link' ? current.password : '',
        }));
        setConsents({
          terms: Boolean(flow.terms_accepted),
          marketing: Boolean(flow.marketing_opt_in),
        });
        if (flow.step === 'email_sent') {
          setStep('emailSent');
        } else if (flow.step === 'email') {
          setStep('flowEmail');
        } else {
          setStep('details');
        }
        setError('');
      })
      .catch((err) => {
        if (cancelled) return;
        const detail = err?.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Не удалось продолжить регистрацию. Начни заново.');
        setFlowToken('');
        setStep('email');
        navigate('/register', { replace: true });
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingFlow(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [location.search, navigate]);

  const passwordChecks = getPasswordChecks(formData.password, {
    username: formData.username,
    email: formData.email,
    providerLogin,
  });

  const isPasswordValid = passwordChecks.every((item) => item.passed);

  const handleInputChange = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const handleConsentChange = (event) => {
    const { name, checked } = event.target;
    setConsents((current) => ({
      ...current,
      [name]: checked,
    }));
  };

  const resetToStart = () => {
    setFlowToken('');
    setProviderLogin('');
    setRegistrationSource('email_magic_link');
    setStep('email');
    setNotice('');
    setError('');
    setShowPassword(false);
    setShowPasswordHints(false);
    setFormData((current) => ({
      email: current.email,
      username: '',
      password: '',
    }));
    setQuestionnaire({
      professionTags: [],
      grade: '',
      interestTags: [],
    });
    navigate('/register', { replace: true });
  };

  const handleStartRegistration = async (event) => {
    event.preventDefault();
    if (!formData.email || !consents.terms || loading) {
      return;
    }

    setLoading(true);
    setError('');
    setNotice('');

    try {
      const response = await authAPI.startEmailRegistration({
        email: formData.email,
        termsAccepted: consents.terms,
        marketingOptIn: consents.marketing,
      });
      setFlowToken(response.flow_token);
      setStep('emailSent');
      navigate(`/register?flow_token=${encodeURIComponent(response.flow_token)}`, { replace: true });
    } catch (err) {
      if (err?.message === 'API base URL is not configured') {
        setError('Не настроен REACT_APP_API_BASE_URL для production-сборки.');
      } else if (!err?.response) {
        setError('Не удалось подключиться к серверу. Попробуйте снова.');
      } else {
        setError(err.response?.data?.detail || 'Ошибка регистрации');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (!flowToken || loading) {
      return;
    }

    setLoading(true);
    setError('');
    setNotice('');
    try {
      const response = await authAPI.resendEmailRegistration({ flowToken });
      setFlowToken(response.flow_token);
      setNotice('Письмо отправлено повторно.');
      navigate(`/register?flow_token=${encodeURIComponent(response.flow_token)}`, { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Не удалось отправить письмо повторно.');
    } finally {
      setLoading(false);
    }
  };

  const handleYandexRegistration = () => {
    if (!consents.terms) {
      setError('Нужно принять условия пользования перед регистрацией через Яндекс.');
      setNotice('');
      return;
    }
    authAPI.startYandexRegistration({
      termsAccepted: consents.terms,
      marketingOptIn: consents.marketing,
    });
  };

  const handleGithubRegistration = () => {
    if (!consents.terms) {
      setError('Нужно принять условия пользования перед регистрацией через GitHub.');
      setNotice('');
      return;
    }
    authAPI.startGithubRegistration({
      termsAccepted: consents.terms,
      marketingOptIn: consents.marketing,
    });
  };

  const handleTelegramRegistration = () => {
    if (!consents.terms) {
      setError('Нужно принять условия пользования перед регистрацией через Telegram.');
      setNotice('');
      return;
    }
    authAPI.startTelegramRegistration({
      termsAccepted: consents.terms,
      marketingOptIn: consents.marketing,
    });
  };

  const handleAttachEmailToFlow = async (event) => {
    event.preventDefault();
    if (!flowToken || !formData.email || loading) {
      return;
    }
    if (!consents.terms) {
      setError('Нужно принять условия пользования перед продолжением регистрации.');
      setNotice('');
      return;
    }

    setLoading(true);
    setError('');
    setNotice('');
    try {
      const response = await authAPI.attachEmailToRegistrationFlow({
        flowToken,
        email: formData.email,
        termsAccepted: consents.terms,
        marketingOptIn: consents.marketing,
      });
      setFlowToken(response.flow_token);
      setStep('emailSent');
      navigate(`/register?flow_token=${encodeURIComponent(response.flow_token)}`, { replace: true });
    } catch (err) {
      if (err?.message === 'API base URL is not configured') {
        setError('Не настроен REACT_APP_API_BASE_URL для production-сборки.');
      } else if (!err?.response) {
        setError('Не удалось подключиться к серверу. Попробуйте снова.');
      } else {
        setError(err.response?.data?.detail || 'Не удалось отправить письмо для подтверждения.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleContinueFromDetails = (event) => {
    event.preventDefault();
    setError('');
    setNotice('');

    if (String(formData.username || '').trim().length < 3) {
      setError('Никнейм должен быть не короче 3 символов.');
      return;
    }
    if (!isOAuthContinuation && !isPasswordValid) {
      setError('Проверь пароль. Он должен соответствовать всем требованиям.');
      return;
    }
    setSuccessName(String(formData.username || '').trim() || 'CyberNinja');
    setStep('welcome');
  };

  const toggleMultiValue = (field, value) => {
    setQuestionnaire((current) => {
      const source = current[field];
      const nextValues = source.includes(value)
        ? source.filter((item) => item !== value)
        : [...source, value];
      return {
        ...current,
        [field]: nextValues,
      };
    });
  };

  const completeRegistration = async () => {
    if (!flowToken || loading) {
      return;
    }

    setLoading(true);
    setError('');
    setNotice('');

    try {
      const result = await authAPI.completeRegistration({
        flowToken,
        username: formData.username.trim(),
        password: isOAuthContinuation ? null : formData.password,
        professionTags: questionnaire.professionTags,
        grade: questionnaire.grade,
        interestTags: questionnaire.interestTags,
      });
      authAPI.persistAccessToken(result?.access_token);
      navigate('/home', { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail) && detail.length > 0) {
        setError(String(detail[0]));
      } else if (err?.message === 'API base URL is not configured') {
        setError('Не настроен REACT_APP_API_BASE_URL для production-сборки.');
      } else {
        setError('Не удалось завершить регистрацию.');
      }
    } finally {
      setLoading(false);
    }
  };

  const renderStatus = () => (
    <>
      {notice ? <Banner tone="notice">{notice}</Banner> : null}
      {error ? <Banner>{error}</Banner> : null}
    </>
  );

  const renderEmailForm = () => (
    <AuthShell title="Регистрация">
      <AuthSurface>
        <form onSubmit={handleStartRegistration} className="space-y-8">
          {renderStatus()}

          <div className="space-y-4">
            <label className="block">
              <span className="mb-2 block text-[14px] leading-5 text-white/56">Электронная почта</span>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                placeholder="Твой адрес электронной почты"
                autoComplete="email"
                required
                className="h-14 w-full rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 text-[16px] tracking-[0.04em] text-white outline-none transition placeholder:text-white/40 focus:border-[#8C5EFF]"
              />
            </label>

            <div className="space-y-2 pt-1 text-[14px] leading-5 tracking-[0.04em] text-white/60">
              <ConsentCheckbox
                checked={consents.terms}
                onChange={(event) => handleConsentChange({ target: { name: 'terms', checked: event.target.checked } })}
              >
                {'Я принимаю '}
                <button
                  type="button"
                  onClick={(e) => { e.preventDefault(); setShowTerms(true); }}
                  className="text-[#A87FFF] hover:text-[#C4A3FF] underline underline-offset-2 transition"
                >
                  условия пользования платформой и согласие на обработку персональных данных
                </button>
              </ConsentCheckbox>
              <ConsentCheckbox
                checked={consents.marketing}
                onChange={(event) => handleConsentChange({ target: { name: 'marketing', checked: event.target.checked } })}
              >
                Я даю согласие на получение рекламных и иных маркетинговых рассылок от ООО "Технологии и Решения" и на обработку своих персональных данных для указанной цели
              </ConsentCheckbox>
            </div>
          </div>

          <AuthPrimaryButton type="submit" disabled={loading || !formData.email || !consents.terms}>
            {loading ? 'Загрузка...' : 'Зарегистрироваться'}
          </AuthPrimaryButton>

          <SocialAuthButtons
            mode="register"
            onGithub={handleGithubRegistration}
            onYandex={handleYandexRegistration}
            onTelegram={handleTelegramRegistration}
            githubDisabled={loading}
            yandexDisabled={loading}
            telegramDisabled={loading}
            footerLabel="Уже с нами?"
            footerActionLabel="Войти"
            onFooterAction={() => navigate('/login')}
          />
        </form>
      </AuthSurface>
    </AuthShell>
  );

  const renderEmailSent = () => (
    <AuthShell title="Регистрация" className="justify-center">
      <div className="w-full text-center">
        <div className="mx-auto max-w-[530px] space-y-8">
          {renderStatus()}
          <p className="text-[18px] leading-8 text-white/72">
            Отправили ссылку для входа на указанную почту. Если не найдешь ее в основном ящике, загляни в папку «Спам». Ссылка действительна 24 часа
          </p>

          <div className="mx-auto flex w-full max-w-[268px] flex-col gap-2">
            <AuthPrimaryButton onClick={handleResend} disabled={loading}>
              {loading ? 'Отправляем...' : 'Отправить повторно'}
            </AuthPrimaryButton>
            <button
              type="button"
              onClick={resetToStart}
              className="h-[54px] rounded-[10px] border border-white/[0.06] bg-white/[0.05] text-[18px] tracking-[0.04em] text-white transition hover:bg-white/[0.07]"
            >
              Вернуться назад
            </button>
          </div>
        </div>
      </div>
    </AuthShell>
  );

  const renderFlowEmail = () => (
    <AuthShell title="Регистрация">
      <AuthSurface className="max-w-[520px]">
        <form onSubmit={handleAttachEmailToFlow} className="space-y-8">
          {renderStatus()}

          <div className="rounded-[18px] border border-white/10 bg-white/[0.03] px-4 py-4 text-[14px] leading-6 text-white/74">
            Telegram аккаунт подключен. Укажи электронную почту, подтверди её по magic-link и после этого продолжишь регистрацию без пароля.
          </div>

          <div className="space-y-4">
            <label className="block">
              <span className="mb-2 block text-[14px] leading-5 text-white/56">Электронная почта</span>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                placeholder="Твой адрес электронной почты"
                autoComplete="email"
                required
                className="h-14 w-full rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 text-[16px] tracking-[0.04em] text-white outline-none transition placeholder:text-white/40 focus:border-[#8C5EFF]"
              />
            </label>

            <div className="space-y-2 pt-1 text-[14px] leading-5 tracking-[0.04em] text-white/60">
              <ConsentCheckbox
                checked={consents.terms}
                onChange={(event) => handleConsentChange({ target: { name: 'terms', checked: event.target.checked } })}
              >
                {'Я принимаю '}
                <button
                  type="button"
                  onClick={(e) => { e.preventDefault(); setShowTerms(true); }}
                  className="text-[#A87FFF] hover:text-[#C4A3FF] underline underline-offset-2 transition"
                >
                  условия пользования платформой и согласие на обработку персональных данных
                </button>
              </ConsentCheckbox>
              <ConsentCheckbox
                checked={consents.marketing}
                onChange={(event) => handleConsentChange({ target: { name: 'marketing', checked: event.target.checked } })}
              >
                Я даю согласие на получение рекламных и иных маркетинговых рассылок от ООО "Технологии и Решения" и на обработку своих персональных данных для указанной цели
              </ConsentCheckbox>
            </div>
          </div>

          <AuthPrimaryButton type="submit" disabled={loading || !formData.email || !consents.terms}>
            {loading ? 'Отправляем...' : 'Продолжить'}
          </AuthPrimaryButton>
        </form>
      </AuthSurface>
    </AuthShell>
  );

  const renderDetails = () => (
    <AuthShell title="Регистрация">
      <AuthSurface className={isOAuthContinuation ? 'max-w-[520px]' : ''}>
        <form onSubmit={handleContinueFromDetails} className="space-y-8">
          {renderStatus()}

          <div className="space-y-4">
            <label className="block">
              <span className="mb-2 block text-[14px] leading-5 text-white/56">Электронная почта</span>
              <div className="relative">
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  readOnly
                  className="h-14 w-full rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 pr-12 text-[16px] tracking-[0.04em] text-white/40 outline-none"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[#8C5EFF]">
                  <AppIcon name="check-circle" className="h-3.5 w-3.5" />
                </span>
              </div>
            </label>

            <label className="block">
              <span className="mb-2 block text-[14px] leading-5 text-white/56">Никнейм</span>
              <div className="relative">
                <input
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleInputChange}
                  placeholder="Придумай никнейм"
                  autoComplete="username"
                  required
                  className="h-14 w-full rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 pr-12 text-[16px] tracking-[0.04em] text-white outline-none transition placeholder:text-white/40 focus:border-[#8C5EFF]"
                />
                {formData.username ? (
                  <button
                    type="button"
                    onClick={() => setFormData((current) => ({ ...current, username: '' }))}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-white/45 transition hover:text-white"
                    aria-label="Очистить никнейм"
                  >
                    <AppIcon name="close" className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </div>
            </label>

            {!isOAuthContinuation ? (
              <label className="relative block">
                <span className="mb-2 block text-[14px] leading-5 text-white/56">Пароль</span>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    value={formData.password}
                    onChange={handleInputChange}
                    onFocus={() => setShowPasswordHints(true)}
                    onBlur={() => setShowPasswordHints(false)}
                    placeholder="Придумай пароль"
                    autoComplete="new-password"
                    required
                    className="h-14 w-full rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 pr-20 text-[16px] tracking-[0.04em] text-white outline-none transition placeholder:text-white/40 focus:border-[#8C5EFF]"
                  />
                  <div className="absolute right-4 top-1/2 flex -translate-y-1/2 items-center gap-2">
                    <PasswordVisibilityButton
                      visible={showPassword}
                      onToggle={() => setShowPassword((current) => !current)}
                      inline
                    />
                    {formData.password ? (
                      <button
                        type="button"
                        onClick={() => setFormData((current) => ({ ...current, password: '' }))}
                        className="text-white/45 transition hover:text-white"
                        aria-label="Очистить пароль"
                      >
                        <AppIcon name="close" className="h-3.5 w-3.5" />
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className={`mt-3 rounded-[20px] border border-white/10 bg-[#2B2440] px-4 py-4 text-[12px] leading-5 text-white/80 transition lg:absolute lg:left-[calc(100%+18px)] lg:top-[28px] lg:mt-0 lg:w-[290px] ${showPasswordHints || formData.password ? 'opacity-100' : 'pointer-events-none opacity-0'}`}>
                  <div className="space-y-2">
                    {passwordChecks.map((item) => (
                      <div key={item.label} className={`flex items-start gap-2 ${item.passed ? 'text-[#E9DFFF]' : 'text-white/58'}`}>
                        <span className={`mt-1 h-1.5 w-1.5 rounded-full ${item.passed ? 'bg-[#8452FF]' : 'bg-white/20'}`} />
                        <span>{item.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </label>
            ) : null}
          </div>

          <AuthPrimaryButton
            type="submit"
            disabled={loading || !formData.username || (!isOAuthContinuation && (!formData.password || !isPasswordValid))}
          >
            {isOAuthContinuation ? 'Продолжить' : 'Продолжить'}
          </AuthPrimaryButton>

          {!isOAuthContinuation ? (
            <SocialAuthButtons
              mode="register"
              onGithub={handleGithubRegistration}
              onYandex={handleYandexRegistration}
              onTelegram={handleTelegramRegistration}
              githubDisabled={loading}
              yandexDisabled={loading}
              telegramDisabled={loading}
              footerLabel="Уже с нами?"
              footerActionLabel="Войти"
              onFooterAction={() => navigate('/login')}
            />
          ) : null}
        </form>
      </AuthSurface>
    </AuthShell>
  );

  const renderQuestionnaire = ({
    counter,
    title,
    hint,
    options,
    field,
    single = false,
    nextLabel,
    onNext,
    onBack,
  }) => (
    <AuthShell title={null} className="justify-center">
      <div className="w-full max-w-[480px] space-y-10">
        {renderStatus()}

        <div className="space-y-2 text-center">
          <p className="text-[14px] leading-5 text-white/54">{counter}</p>
          <h2 className="text-[44px] font-medium leading-[1] tracking-[-0.03em] text-white">{title}</h2>
        </div>

        <div className="space-y-4">
          <p className={`text-[14px] leading-5 text-white/54 ${single ? 'text-left' : 'text-center'}`}>{hint}</p>
          <div className="space-y-2">
            {options.map((option) => {
              const selected = single
                ? questionnaire[field] === option
                : questionnaire[field].includes(option);

              return (
                <QuestionOption
                  key={option}
                  label={option}
                  selected={selected}
                  single={single}
                  compact={!single}
                  onToggle={() => {
                    if (single) {
                      setQuestionnaire((current) => ({ ...current, [field]: option }));
                      return;
                    }
                    toggleMultiValue(field, option);
                  }}
                />
              );
            })}
          </div>
        </div>

        <div className={`grid gap-2 ${onBack ? 'grid-cols-2' : 'grid-cols-1'}`}>
          {onBack ? (
            <button
              type="button"
              onClick={onBack}
              className="h-14 rounded-[10px] border border-white/[0.06] bg-white/[0.05] text-[18px] tracking-[0.04em] text-white transition hover:bg-white/[0.07]"
            >
              Назад
            </button>
          ) : null}
          <AuthPrimaryButton
            onClick={onNext}
            disabled={
              loading
              || (single ? !questionnaire[field] : questionnaire[field].length === 0)
            }
          >
            {loading && field === 'interestTags' ? 'Завершаем...' : nextLabel}
          </AuthPrimaryButton>
        </div>
      </div>
    </AuthShell>
  );

  const renderWelcome = () => (
    <AuthShell title={null} className="justify-center">
      <div className="w-full max-w-[334px] text-center">
        <h2 className="text-[64px] font-medium leading-[1] tracking-[-0.05em] text-white">{successName},</h2>
        <p className="mt-5 text-[28px] leading-8 text-white/75">Добро пожаловать в&nbsp;Hacknet!</p>
      </div>
    </AuthShell>
  );

  useEffect(() => {
    if (step !== 'welcome') {
      return undefined;
    }
    const timerId = window.setTimeout(() => {
      setStep('profession');
    }, 1300);
    return () => {
      window.clearTimeout(timerId);
    };
  }, [step]);

  if (loadingFlow) {
    return (
      <AuthShell title="Регистрация">
        <AuthSurface className="max-w-[420px] px-10 py-10 text-center">
          <div className="space-y-3">
            <p className="text-[15px] leading-6 text-white/70">Восстанавливаем шаг регистрации и проверяем ссылку.</p>
            <div className="mx-auto h-10 w-10 animate-spin rounded-full border-2 border-white/15 border-t-[#8452FF]" aria-hidden="true" />
          </div>
        </AuthSurface>
      </AuthShell>
    );
  }

  if (step === 'emailSent') {
    return renderEmailSent();
  }
  if (step === 'flowEmail') {
    return (
      <>
        {renderFlowEmail()}
        <TermsModal open={showTerms} onClose={() => setShowTerms(false)} />
      </>
    );
  }
  if (step === 'details') {
    return renderDetails();
  }
  if (step === 'profession') {
    return renderQuestionnaire({
      counter: '1 / 3 вопросов',
      title: 'Твоя профессия',
      hint: 'Выбери хотя бы один вариант',
      options: PROFESSION_OPTIONS,
      field: 'professionTags',
      nextLabel: 'Далее',
      onNext: () => setStep('grade'),
    });
  }
  if (step === 'grade') {
    return renderQuestionnaire({
      counter: '2 / 3 вопросов',
      title: 'Твой грейд',
      hint: 'Выбери один вариант',
      options: GRADE_OPTIONS,
      field: 'grade',
      single: true,
      nextLabel: 'Далее',
      onNext: () => setStep('interests'),
      onBack: () => setStep('profession'),
    });
  }
  if (step === 'interests') {
    return renderQuestionnaire({
      counter: '3 / 3 вопросов',
      title: 'Что тебя интересует',
      hint: 'Выбери хотя бы один вариант',
      options: INTEREST_OPTIONS,
      field: 'interestTags',
      nextLabel: 'Завершить регистрацию',
      onNext: completeRegistration,
      onBack: () => setStep('grade'),
    });
  }
  if (step === 'welcome') {
    return renderWelcome();
  }

  return (
    <>
      {renderEmailForm()}
      <TermsModal open={showTerms} onClose={() => setShowTerms(false)} />
    </>
  );
}

export default Register;
