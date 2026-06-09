import { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../../../services/api';

const POLL_INTERVAL_MS = 2500;

function getApiErrorMessage(err, fallback) {
  const detail = err?.response?.data?.detail;
  const responseData = err?.response?.data;
  if (typeof responseData === 'string' && responseData.trim()) return responseData;
  if (typeof detail === 'string' && detail.trim()) return detail;
  return err?.message || fallback;
}

// Запускает фоновое задание генерации чемпионата и опрашивает прогресс,
// по аналогии с паттерном NVD-синка (useNvdSyncData.js).
export default function useContestTaskGen() {
  const [job, setJob] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);

  const isRunning = job ? job.status === 'running' : false;

  const start = useCallback(async (payload) => {
    setStarting(true);
    setError(null);
    setJob(null);
    setJobId(null);
    try {
      const res = await adminAPI.startChampionshipGeneration(payload);
      setJob({
        id: res.job_id,
        status: 'running',
        total: res.total || 0,
        completed: 0,
        failed: 0,
        events: [],
        created_task_ids: [],
      });
      setJobId(res.job_id);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Не удалось запустить генерацию'));
    } finally {
      setStarting(false);
    }
  }, []);

  useEffect(() => {
    if (!jobId) return undefined;
    let active = true;

    const poll = async () => {
      try {
        const data = await adminAPI.getChampionshipGenJob(jobId);
        if (active) setJob(data);
        return data.status;
      } catch (err) {
        if (active) setError(getApiErrorMessage(err, 'Ошибка получения статуса'));
        return 'failed';
      }
    };

    poll();
    const interval = setInterval(async () => {
      const status = await poll();
      if (status !== 'running') clearInterval(interval);
    }, POLL_INTERVAL_MS);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [jobId]);

  return { job, isRunning, starting, error, start };
}
