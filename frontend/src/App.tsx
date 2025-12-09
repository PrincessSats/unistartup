import './App.css';
import { AuthForm } from './components/AuthForm';
import { useCurrentUser } from './hooks/useCurrentUser';
import { supabase } from './lib/supabaseClient';

function AdminDashboard() {
  return (
    <div>
      <h1>Админка</h1>
      <p>Здесь потом будут кнопки:</p>
      <ul>
        <li>Создать задачу</li>
        <li>Список задач</li>
        <li>Knowledge base</li>
        <li>Пользователи</li>
      </ul>
    </div>
  );
}

function App() {
  const { loading, profile } = useCurrentUser();

  if (loading) {
    return <div>Загрузка...</div>;
  }

  if (!profile) {
    return (
      <div style={{ padding: 24 }}>
        <h1>UniStartup</h1>
        <AuthForm />
      </div>
    );
  }

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16 }}>
        <span>
          Вы вошли как <b>{profile.username || profile.id}</b> ({profile.role})
        </span>
        <button style={{ marginLeft: 16 }} onClick={handleLogout}>
          Выйти
        </button>
      </div>

      {profile.role === 'admin' ? (
        <AdminDashboard />
      ) : (
        <div>
          <h2>Нет доступа</h2>
          <p>Эта страница только для админов. Ваш уровень: {profile.role}</p>
        </div>
      )}
    </div>
  );
}

export default App;
