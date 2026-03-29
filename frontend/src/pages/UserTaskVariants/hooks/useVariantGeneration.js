import { useState, useCallback, useEffect, useRef } from 'react';
import { userVariantsAPI } from '../../../services/api';

/**
 * Hook for managing task variant generation
 * 
 * Features:
 * - Start generation
 * - Poll status
 * - Handle errors
 * - Auto-stop polling on completion
 */
export function useVariantGeneration(parentTaskId) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [requestId, setRequestId] = useState(null);
  const [status, setStatus] = useState('idle'); // idle, pending, generating, completed, failed
  const [error, setError] = useState(null);
  const [generatedVariant, setGeneratedVariant] = useState(null);
  const pollIntervalRef = useRef(null);

  /**
   * Stop polling
   */
  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  /**
   * Start generation
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
      
      // Start polling
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
      }, 2500); // Poll every 2.5 seconds
      
    } catch (err) {
      console.error('Start generation error:', err);
      setIsGenerating(false);
      setStatus('failed');
      
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Не удалось запустить генерацию');
    }
  }, [parentTaskId, stopPolling]);

  /**
   * Reset state
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
   * Cleanup on unmount
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
