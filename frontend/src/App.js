import React, { useEffect, useMemo, useRef, useState } from 'react';
import { HashRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import Profile from './pages/Profile';
import Championship from './pages/Championship';
import Knowledge from './pages/Knowledge';
import KnowledgeArticle from './pages/KnowledgeArticle';
import Education from './pages/Education';
import EducationTask from './pages/EducationTask';
import Home from './pages/Home';
import Rating from './pages/Rating';
import Admin from './pages/Admin';
import Layout from './components/Layout';
import { FullScreenLoader } from './components/LoadingState';
import { authAPI } from './services/api';

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
  return !isAuth ? children : <Navigate to="/profile" replace />;
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
  const [authReady, setAuthReady] = useState(false);
  const [authReason, setAuthReason] = useState('');

  useEffect(() => {
    let cancelled = false;

    const bootstrap = async () => {
      if (!authAPI.isAuthenticated()) {
        // Not authenticated — no need to verify session, just let them browse.
        setAuthReason('');
        setAuthReady(true);
        return;
      }

      const result = await authAPI.bootstrapAuth({ timeoutMs: 1500 });
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

  if (!authReady) {
    return <FullScreenLoader label="Проверяем сессию..." />;
  }

  return (
    <HashRouter>
      <MetrikaPageTracker />
      <Routes>
        <Route path="/" element={<Navigate to="/home" replace />} />

        <Route path="/login" element={<PublicRoute authReady={authReady}><Login /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute authReady={authReady}><Register /></PublicRoute>} />

        {/* Layout доступен всем; отдельные маршруты защищены через ProtectedRoute. */}
        <Route element={<Layout />}>
          <Route path="/profile" element={<ProtectedRoute authReady={authReady} loginTarget={loginTarget}><Profile /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute authReady={authReady} loginTarget={loginTarget}><Admin /></ProtectedRoute>} />
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
    </HashRouter>
  );
}

export default App;
