import React, { useEffect, useMemo, useState } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
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

function App() {
  const [authReady, setAuthReady] = useState(false);
  const [authReason, setAuthReason] = useState('');

  useEffect(() => {
    let cancelled = false;

    const bootstrap = async () => {
      const currentHash = window.location.hash || '#/';
      const isPublicPath = currentHash.startsWith('#/login') || currentHash.startsWith('#/register');
      if (isPublicPath && !authAPI.isAuthenticated()) {
        setAuthReason('');
        setAuthReady(true);
        return;
      }

      const result = await authAPI.bootstrapAuth({ timeoutMs: 1500 });
      if (cancelled) return;

      setAuthReason(result?.reason || '');
      setAuthReady(true);

      if (!result?.authenticated && result?.reason) {
        const nextHash = window.location.hash || '#/';
        const isPublicPath = nextHash.startsWith('#/login') || nextHash.startsWith('#/register');
        if (!isPublicPath) {
          window.location.hash = `#/login?reason=${encodeURIComponent(result.reason)}`;
        }
      }
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
      <Routes>
        <Route
          path="/"
          element={authAPI.isAuthenticated() ? <Navigate to="/profile" replace /> : <Navigate to={loginTarget} replace />}
        />

        <Route path="/login" element={<PublicRoute authReady={authReady}><Login /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute authReady={authReady}><Register /></PublicRoute>} />

        {/* Держим единый Layout для всех защищённых страниц, чтобы не перемонтировать его на каждом переходе. */}
        <Route element={<ProtectedRoute authReady={authReady} loginTarget={loginTarget}><Layout /></ProtectedRoute>}>
          <Route path="/profile" element={<Profile />} />
          <Route path="/home" element={<Home />} />
          <Route path="/championship" element={<Championship />} />
          <Route path="/education" element={<Education />} />
          <Route path="/education/:id" element={<EducationTask />} />
          <Route path="/rating" element={<Rating />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/knowledge/:id" element={<KnowledgeArticle />} />
          <Route path="/faq" element={<div className="text-white text-2xl">FAQ — скоро будет</div>} />
          <Route path="/admin" element={<Admin />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
