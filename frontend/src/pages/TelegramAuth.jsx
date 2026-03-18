import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

const API_URL = String(process.env.REACT_APP_API_BASE_URL || '').replace(/\/$/, '');

function TelegramAuth() {
  const location = useLocation();

  useEffect(() => {
    const src = new URLSearchParams(location.search);
    const dest = new URLSearchParams({
      intent: src.get('intent') || 'login',
      terms_accepted: src.get('terms_accepted') || 'false',
      marketing_opt_in: src.get('marketing_opt_in') || 'false',
    });
    window.location.replace(`${API_URL}/api/auth/telegram/start?${dest.toString()}`);
  }, [location.search]);

  return null;
}

export default TelegramAuth;
