import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import Profile from './pages/Profile';
import Championship from './pages/Championship';
import Knowledge from './pages/Knowledge';
import Home from './pages/Home';
import Rating from './pages/Rating';
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

        <Route path="/profile" element={<ProtectedRoute><Layout><Profile /></Layout></ProtectedRoute>} />
        
        <Route path="/home" element={<ProtectedRoute><Layout><Home /></Layout></ProtectedRoute>} />
        <Route path="/championship" element={<ProtectedRoute><Layout><Championship /></Layout></ProtectedRoute>} />
        <Route path="/education" element={<ProtectedRoute><Layout><div className="text-white text-2xl">Обучение — скоро будет</div></Layout></ProtectedRoute>} />
        <Route path="/rating" element={<ProtectedRoute><Layout><Rating /></Layout></ProtectedRoute>} />
        <Route path="/knowledge" element={<ProtectedRoute><Layout><Knowledge /></Layout></ProtectedRoute>} />
        <Route path="/faq" element={<ProtectedRoute><Layout><div className="text-white text-2xl">FAQ — скоро будет</div></Layout></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute><Layout><div className="text-white text-2xl">Админка — скоро будет</div></Layout></ProtectedRoute>} />

        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
