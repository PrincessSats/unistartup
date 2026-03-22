import { useCallback, useEffect, useState } from 'react';
import { adminAPI, authAPI } from '../../../services/api';

export function useAdminDashboard(navigate) {
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState('');

  const loadDashboard = useCallback(async () => {
    try {
      const data = await adminAPI.getDashboard();
      setDashboard(data);
      setError('');
    } catch (err) {
      if (err.response?.status === 401) {
        authAPI.logout({ remote: false });
        navigate('/login?reason=session_expired', { replace: true });
        return;
      }
      if (err.response?.status === 403) {
        navigate('/home', { replace: true });
        return;
      }
      setError('Не удалось загрузить данные админки');
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const refresh = useCallback(() => {
    setLoading(true);
    loadDashboard();
  }, [loadDashboard]);

  const refreshQuiet = useCallback(() => {
    loadDashboard();
  }, [loadDashboard]);

  return {
    loading,
    dashboard,
    error,
    refresh,
    refreshQuiet,
    setDashboard,
    setError,
  };
}

export function useNvdSync(loadDashboard) {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState('');

  const handleFetch = useCallback(async () => {
    setIsRunning(true);
    setError('');
    try {
      const data = await adminAPI.fetchNvd24h();
      loadDashboard((prev) => ({
        ...(prev || {}),
        nvd_sync: data,
      }));
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось выполнить синхронизацию NVD'));
    } finally {
      setIsRunning(false);
    }
  }, [loadDashboard]);

  return {
    isRunning,
    error,
    handleFetch,
    setIsRunning,
    setError,
  };
}

function getApiErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  const responseData = err?.response?.data;
  if (typeof responseData === 'string' && responseData.trim()) return responseData;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const text = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && typeof item.msg === 'string') return item.msg;
        try {
          return JSON.stringify(item);
        } catch {
          return '';
        }
      })
      .filter(Boolean)
      .join('; ');
    if (text) return text;
  }
  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string' && detail.message.trim()) return detail.message;
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  if (typeof err?.message === 'string' && err.message.trim()) return err.message;
  return fallback;
}

const hooks = { useAdminDashboard, useNvdSync };
export default hooks;
