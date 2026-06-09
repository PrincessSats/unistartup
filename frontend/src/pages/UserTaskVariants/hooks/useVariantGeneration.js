import { useState, useCallback, useEffect, useRef } from 'react';
import { userVariantsAPI } from '../../../services/api';

/**
 * Хук для управления генерацией вариантов задания
 *
 * Возможности:
 * - Запуск генерации
 * - Опрос статуса
 * - Обработка ошибок
 * - Автоматическая остановка опроса после завершения
 */
export function useVariantGeneration(parentTaskId) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [requestId, setRequestId] = useState(null);
  const [status, setStatus] = useState('idle'); // idle, pending, generating, completed, failed — статус
  const [error, setError] = useState(null);
  const [generatedVariant, setGeneratedVariant] = useState(null);
  const pollIntervalRef = useRef(null);

  /**
   * Остановка опроса
   */
  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  /**
   * Запуск генерации
   */
  const startGeneration = useCallback(async (userRequest) => {
    try {
      setError(null);
      setGeneratedVariant(null);
      setStatus('pending');
      setIsGenerating(true);

      const response = await userVariantsAPI.startGeneration(parentTaskId, { user_request: userRequest });
      setRequestId(response.request_id);
      setStatus('pending');

      // Запуск опроса
      pollIntervalRef.current = setInterval(async () => {
        try {
          const statusResponse = await userVariantsAPI.getRequestStatus(response.request_id);
          setStatus(statusResponse.status);

          if (statusResponse.status === 'completed') {
            stopPolling();
            setIsGenerating(false);
            setGeneratedVariant({
              variant_id: statusResponse.generated_variant_id,
            });
          } else if (statusResponse.status === 'failed') {
            stopPolling();
            setIsGenerating(false);
            setError(statusResponse.failure_reason || statusResponse.rejection_reason || 'Генерация не удалась');
          }
        } catch (err) {
          console.error('Polling error:', err);
          stopPolling();
          setIsGenerating(false);
          setError('Ошибка проверки статуса');
        }
      }, 2500); // Опрос каждые 2.5 секунды

    } catch (err) {
      console.error('Start generation error:', err);
      setIsGenerating(false);
      setStatus('failed');

      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Не удалось запустить генерацию');
    }
  }, [parentTaskId, stopPolling]);

  /**
   * Сброс состояния
   */
  const reset = useCallback(() => {
    stopPolling();
    setIsGenerating(false);
    setRequestId(null);
    setStatus('idle');
    setError(null);
    setGeneratedVariant(null);
  }, [stopPolling]);

  /**
   * Очистка при размонтировании
   */
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  return {
    isGenerating,
    requestId,
    status,
    error,
    generatedVariant,
    startGeneration,
    reset,
  };
}

export default useVariantGeneration;
