import React, { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
// Критичные для первого рендера экраны грузим сразу; остальное — по требованию (code-splitting),
// чтобы начальный бандл не тащил все 16 страниц (включая админку, которую обычный юзер не видит).
import Login from './pages/Login';
import Home from './pages/Home';
import Layout from './components/Layout';
import { FullScreenLoader } from './components/LoadingState';
import { authAPI } from './services/api';
import MobileBlock from './components/MobileBlock';

const Register = lazy(() => import('./pages/Register'));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));
const AuthBridge = lazy(() => import('./pages/AuthBridge'));
const TelegramAuth = lazy(() => import('./pages/TelegramAuth'));
const Profile = lazy(() => import('./pages/Profile'));
const Championship = lazy(() => import('./pages/Championship'));
const Knowledge = lazy(() => import('./pages/Knowledge'));
const KnowledgeArticle = lazy(() => import('./pages/KnowledgeArticle'));
const Education = lazy(() => import('./pages/Education'));
const EducationTask = lazy(() => import('./pages/EducationTask'));
const Rating = lazy(() => import('./pages/Rating'));
const Admin = lazy(() => import('./pages/Admin/index.jsx'));
const ContestManager = lazy(() => import('./pages/Admin/ContestManager/index.jsx'));
const ContestTasksGen = lazy(() => import('./pages/Admin/ContestTasksGen/index.jsx'));
const Pipeline = lazy(() => import('./pages/Pipeline'));
const CvePipeline = lazy(() => import('./pages/CvePipeline'));
const NvdSync = lazy(() => import('./pages/NvdSync/index.jsx'));

function useMobileDetect() {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 1024);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1023px)');
    const handler = (e) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return isMobile;
}

function ProtectedRoute({ children, authReady, loginTarget }) {
  if (!authReady) {
    return <FullScreenLoader label="Проверяем сессию..." />;
  }
  const isAuth = authAPI.isAuthenticated();
  return isAuth ? children : <Navigate to={loginTarget} replace />;
}

function PublicRoute({ children, authReady }) {
  if (!authReady) {
    return <FullScreenLoader label="Проверяем сессию..." />;
  }
  const isAuth = authAPI.isAuthenticated();
  return !isAuth ? children : <Navigate to="/home" replace />;
}

function MetrikaPageTracker() {
  const location = useLocation();
  const isFirstRender = useRef(true);
  const previousUrl = useRef(typeof window !== 'undefined' ? window.location.href : '');

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.ym !== 'function') return;

    const currentUrl = window.location.href;
    if (isFirstRender.current) {
      isFirstRender.current = false;
      previousUrl.current = currentUrl;
      return;
    }

    window.ym(107200842, 'hit', currentUrl, {
      referrer: previousUrl.current || document.referrer,
      title: document.title,
    });
    previousUrl.current = currentUrl;
  }, [location.pathname, location.search, location.hash]);

  return null;
}

function App() {
  const isMobile = useMobileDetect();
  const [authReady, setAuthReady] = useState(false);
  const [authReason, setAuthReason] = useState('');

  useEffect(() => {
    let cancelled = false;

    // Запустить разминку сразу, чтобы контейнер запустился до взаимодействия пользователя.
    authAPI.warmup();

    const bootstrap = async () => {
      if (!authAPI.hasSessionHint()) {
        // Не аутентифицирован — не нужно проверять сессию, просто позволим браузить.
        setAuthReason('');
        setAuthReady(true);
        return;
      }

      const result = await authAPI.bootstrapAuth();
      if (cancelled) return;

      setAuthReason(result?.reason || '');
      setAuthReady(true);
    };

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, []);

  const loginTarget = useMemo(
    () => (authReason ? `/login?reason=${encodeURIComponent(authReason)}` : '/login'),
    [authReason]
  );

  if (isMobile) {
    return <MobileBlock />;
  }

  if (!authReady) {
    return <FullScreenLoader label="Проверяем сессию..." />;
  }

  return (
    <BrowserRouter>
      <MetrikaPageTracker />
      <Suspense fallback={<FullScreenLoader label="Загрузка..." />}>
      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />

        <Route path="/login" element={<PublicRoute authReady={authReady}><Login /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute authReady={authReady}><Register /></PublicRoute>} />
        <Route path="/forgot-password" element={<PublicRoute authReady={authReady}><ForgotPassword /></PublicRoute>} />
        <Route path="/reset-password" element={<PublicRoute authReady={authReady}><ResetPassword /></PublicRoute>} />
        <Route path="/auth/telegram" element={<PublicRoute authReady={authReady}><TelegramAuth /></PublicRoute>} />
        <Route path="/auth/bridge" element={<AuthBridge />} />

        {/* Layout доступен всем; отдельные маршруты защищены через ProtectedRoute. */}
        <Route element={<Layout />}>
          <Route path="/profile" element={<ProtectedRoute authReady={authReady} loginTarget={loginTarget}><Profile /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute authReady={authReady} loginTarget={loginTarget}><Admin /></ProtectedRoute>} />
          <Route path="/admin/contests" element={<ProtectedRoute authReady={authReady} loginTarget={loginTarget}><ContestManager /></ProtectedRoute>} />
          <Route path="/admin/contest-tasks-gen" element={<ProtectedRoute authReady={authReady} loginTarget={loginTarget}><ContestTasksGen /></ProtectedRoute>} />
          <Route path="/pipeline" element={<ProtectedRoute authReady={authReady} loginTarget={loginTarget}><Pipeline /></ProtectedRoute>} />
          <Route path="/cve-pipeline" element={<ProtectedRoute authReady={authReady} loginTarget={loginTarget}><CvePipeline /></ProtectedRoute>} />
          <Route path="/nvd-sync" element={<ProtectedRoute authReady={authReady} loginTarget={loginTarget}><NvdSync /></ProtectedRoute>} />
          <Route path="/home" element={<Home />} />
          <Route path="/championship" element={<Championship />} />
          <Route path="/education" element={<Education />} />
          <Route path="/education/:id" element={<EducationTask />} />
          <Route path="/rating" element={<Rating />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/knowledge/:id" element={<KnowledgeArticle />} />
          <Route path="/faq" element={<div className="text-white text-2xl">FAQ — скоро будет</div>} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
