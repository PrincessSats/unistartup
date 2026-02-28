import React from 'react';
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
import { authAPI } from './services/api';

function ProtectedRoute({ children }) {
  const isAuth = authAPI.isAuthenticated();
  return isAuth ? children : <Navigate to="/login" />;
}

function PublicRoute({ children }) {
  const isAuth = authAPI.isAuthenticated();
  return !isAuth ? children : <Navigate to="/profile" />;
}

function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={authAPI.isAuthenticated() ? <Navigate to="/profile" /> : <Navigate to="/login" />} />

        <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />

        {/* Держим единый Layout для всех защищённых страниц, чтобы не перемонтировать его на каждом переходе. */}
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
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

        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
