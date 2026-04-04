import { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../../services/api';

const POLL_INTERVAL_MS = 2500;
const ACTIVE_STATUSES = new Set(['fetching', 'embedding', 'translating']);

function useNvdSyncData() {
  const [nvdSync, setNvdSync] = useState(null);
  const [pendingOp, setPendingOp] = useState(null); // 'fetch' | 'translate' | 'embed' | null
  const [error, setError] = useState(null);

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

  const _trigger = useCallback(async (op, apiFn) => {
    setPendingOp(op);
    setError(null);
    try {
      const result = await apiFn();
      setNvdSync(result);
    } catch (err) {
      console.error(`Failed to trigger NVD ${op}:`, err);
      setError(err.message || `Failed to trigger ${op}`);
    } finally {
      setPendingOp(null);
    }
  }, []);

  const onFetch = useCallback(() => _trigger('fetch', adminAPI.fetchNvd24h), [_trigger]);
  const onTranslate = useCallback(() => _trigger('translate', adminAPI.triggerNvdTranslate), [_trigger]);
  const onEmbed = useCallback(() => _trigger('embed', adminAPI.triggerNvdEmbed), [_trigger]);
  const onStop = useCallback(() => _trigger('stop', adminAPI.stopNvdSync), [_trigger]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Auto-poll while any sync is active
  useEffect(() => {
    if (!nvdSync) return;
    if (!ACTIVE_STATUSES.has(nvdSync.status)) return;

    const interval = setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [nvdSync, fetchStatus]);

  const isActive = nvdSync ? ACTIVE_STATUSES.has(nvdSync.status) : false;
  const isBusy = !!pendingOp || isActive;

  return {
    nvdSync,
    isBusy,
    pendingOp,
    isActive,
    error,
    onFetch,
    onTranslate,
    onEmbed,
    onStop,
  };
}

export default useNvdSyncData;
