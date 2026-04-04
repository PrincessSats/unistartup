import { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../../services/api';

const POLL_INTERVAL_MS = 2500;

function useNvdSyncData() {
  const [nvdSync, setNvdSync] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState(null);

  // Fetch the current status
  const fetchStatus = useCallback(async () => {
    try {
      const status = await adminAPI.getNvdSyncStatus();
      setNvdSync(status);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch NVD sync status:', err);
      setError(err.message || 'Failed to fetch status');
    }
  }, []);

  // Trigger a new sync
  const onFetch = useCallback(async () => {
    setIsRunning(true);
    setError(null);
    try {
      const result = await adminAPI.fetchNvd24h();
      setNvdSync(result);
    } catch (err) {
      console.error('Failed to trigger NVD sync:', err);
      setError(err.message || 'Failed to trigger sync');
    } finally {
      setIsRunning(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Auto-refresh while sync is active
  useEffect(() => {
    if (!nvdSync) return;

    const activeStatuses = new Set(['fetching', 'embedding', 'translating']);
    const isActive = activeStatuses.has(nvdSync.status);

    if (!isActive) return;

    const interval = setInterval(() => {
      fetchStatus();
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [nvdSync, fetchStatus]);

  return {
    nvdSync,
    isRunning,
    error,
    onFetch,
  };
}

export default useNvdSyncData;
