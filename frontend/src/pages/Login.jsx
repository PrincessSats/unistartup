import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI, profileAPI } from '../services/api';

function Login() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await authAPI.login(formData.email, formData.password);
      const profile = await profileAPI.getProfile();
      if (profile?.role === 'admin') {
        navigate('/admin');
      } else {
        navigate('/home');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Ошибка входа');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0A10] bg-[radial-gradient(circle_at_top,_rgba(132,82,255,0.14)_0,_rgba(11,10,16,0)_45%)] flex items-center justify-center px-4 font-sans-figma text-white">
      <div className="w-full max-w-[420px]">
        <div className="flex justify-center mb-6">
          <img src="/logo.png" alt="HackNet" className="w-12 h-12" />
        </div>

        <h1 className="text-3xl text-center mb-7 tracking-wide">Вход</h1>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-white/10 bg-[#15141C]/90 px-6 py-7 shadow-[0_30px_80px_-40px_rgba(0,0,0,0.8)] space-y-5"
        >
          {error && (
            <div className="bg-red-500/10 border border-red-500/40 text-red-300 px-4 py-3 rounded-xl text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="text-white/60 text-xs mb-2 block">
              Электронная почта
            </label>
            <input
              type="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="Твой адрес электронной почты"
              required
              className="w-full bg-[#1B1A22] border border-white/5 text-white text-sm px-4 py-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#8452FF]/60 focus:border-transparent placeholder:text-white/30"
            />
          </div>

          <div>
            <label className="text-white/60 text-xs mb-2 block">
              Пароль
            </label>
            <input
              type="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="Твой пароль от этой учетной записи"
              required
              className="w-full bg-[#1B1A22] border border-white/5 text-white text-sm px-4 py-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#8452FF]/60 focus:border-transparent placeholder:text-white/30"
            />
          </div>

          <div className="text-right">
            <button
              type="button"
              className="text-white/50 hover:text-white text-xs transition-colors"
            >
              Не помнишь пароль?
            </button>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-[#1B1A22] border border-white/5 text-white/40 hover:text-white/80 hover:bg-[#23222b] py-3 rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Загрузка...' : 'Войти'}
          </button>

          <div className="flex items-center gap-4 pt-3">
            <div className="flex-1 h-px bg-white/10"></div>
            <span className="text-white/40 text-xs">Или войти через</span>
            <div className="flex-1 h-px bg-white/10"></div>
          </div>

          <div className="space-y-3">
            <button
              type="button"
              className="w-full bg-[#1B1A22] border border-white/5 hover:bg-[#23222b] text-white text-sm py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
              Github
            </button>
            <div className="grid grid-cols-2 gap-3">
              <button type="button" className="bg-[#1B1A22] border border-white/5 hover:bg-[#23222b] text-white text-sm py-3 rounded-xl transition-colors flex items-center justify-center gap-2">
                <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z" />
                </svg>
                Apple
              </button>
              <button type="button" className="bg-[#1B1A22] border border-white/5 hover:bg-[#23222b] text-white text-sm py-3 rounded-xl transition-colors flex items-center justify-center gap-2">
                <svg className="w-4 h-4" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                Google
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <button type="button" className="bg-[#1B1A22] border border-white/5 hover:bg-[#23222b] text-white text-sm py-3 rounded-xl transition-colors flex items-center justify-center gap-2">
                <span className="w-4 h-4 bg-[#FC3F1D] rounded flex items-center justify-center text-[10px] font-semibold text-white">Я</span>
                Яндекс
              </button>
              <button type="button" className="bg-[#1B1A22] border border-white/5 hover:bg-[#23222b] text-white text-sm py-3 rounded-xl transition-colors flex items-center justify-center gap-2">
                <svg className="w-4 h-4 text-[#26A5E4]" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
                </svg>
                Телеграм
              </button>
            </div>
          </div>

          <div className="text-center pt-2 text-xs text-white/50">
            Еще не с нами?{' '}
            <button
              type="button"
              onClick={() => navigate('/register')}
              className="text-white hover:text-[#9B6BFF] transition-colors"
            >
              Зарегистрироваться
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default Login;
