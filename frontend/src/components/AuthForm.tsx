import { useState } from 'react';
import { supabase } from '../lib/supabaseClient';

export function AuthForm() {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [msg, setMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);

    if (mode === 'signup') {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
      });

      if (error) {
        setMsg(`Ошибка регистрации: ${error.message}`);
      } else {
        const user = data.user;
        if (user) {
          const { error: profileError } = await supabase
            .from('user_profiles')
            .insert({
              id: user.id,
              username: email.split('@')[0],
              role: 'participant', // все новые юзеры - участники
            });

          if (profileError) {
            console.error('Ошибка создания профиля', profileError);
          }
        }

        setMsg('Регистрация успешна. Теперь войдите.');
        setMode('signin');
      }
    } else {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        setMsg(`Ошибка входа: ${error.message}`);
      } else {
        setMsg('Вход выполнен.');
      }
    }
  };

  return (
    <div style={{ maxWidth: 320 }}>
      <h2>{mode === 'signin' ? 'Вход' : 'Регистрация'}</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label>Email</label><br />
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            style={{ width: '100%' }}
          />
        </div>

        <div>
          <label>Пароль</label><br />
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            style={{ width: '100%' }}
          />
        </div>

        <button type="submit" style={{ marginTop: 12 }}>
          {mode === 'signin' ? 'Войти' : 'Зарегистрироваться'}
        </button>
      </form>

      <button
        style={{ marginTop: 8 }}
        onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
      >
        {mode === 'signin' ? 'Перейти к регистрации' : 'Перейти к входу'}
      </button>

      {msg && <p style={{ marginTop: 8 }}>{msg}</p>}
    </div>
  );
}
