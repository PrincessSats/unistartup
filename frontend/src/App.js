import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import Welcome from './pages/Welcome';
import { authAPI } from './services/api';

// Защищенный маршрут (только для авторизованных)
function ProtectedRoute({ children }) {
  const isAuth = authAPI.isAuthenticated();
  return isAuth ? children : <Navigate to="/login" />;
}

// Публичный маршрут (только для неавторизованных)
function PublicRoute({ children }) {
  const isAuth = authAPI.isAuthenticated();
  return !isAuth ? children : <Navigate to="/welcome" />;
}

function App() {
  return (
    <HashRouter>
      <Routes>
        {/* Главная страница - редирект */}
        <Route 
          path="/" 
          element={
            authAPI.isAuthenticated() 
              ? <Navigate to="/welcome" /> 
              : <Navigate to="/login" />
          } 
        />

        {/* Публичные страницы */}
        <Route 
          path="/login" 
          element={
            <PublicRoute>
              <Login />
            </PublicRoute>
          } 
        />
        <Route 
          path="/register" 
          element={
            <PublicRoute>
              <Register />
            </PublicRoute>
          } 
        />

        {/* Защищенные страницы */}
        <Route 
          path="/welcome" 
          element={
            <ProtectedRoute>
              <Welcome />
            </ProtectedRoute>
          } 
        />

        {/* 404 - несуществующие страницы */}
        <Route 
          path="*" 
          element={<Navigate to="/" />} 
        />
      </Routes>
    </HashRouter>
  );
}

export default App;