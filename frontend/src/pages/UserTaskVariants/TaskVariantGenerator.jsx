import React, { useState, useCallback } from 'react';
import AppIcon from '../../components/AppIcon';
import TicTacToe from './TicTacToe';
import Snake from './Snake';
import useVariantGeneration from './hooks/useVariantGeneration';

/**
 * Suggested wishes for quick selection
 */
const SUGGESTED_WISHES = [
  { label: 'Полегче', text: 'Немного полегче' },
  { label: 'Посложнее', text: 'Немного сложнее' },
  { label: 'Больше этапов', text: 'Больше этапов шифрования' },
  { label: 'Меньше подсказок', text: 'Меньше подсказок' },
  { label: 'Другой сценарий', text: 'Другой сценарий, но та же механика' },
];

/**
 * Task Variant Generator Dialog
 *
 * Flow:
 * 1. User enters wishes
 * 2. Show random game (Tic-Tac-Toe or Snake) while generating
 * 3. Show result or error
 */
export default function TaskVariantGenerator({ isOpen, onClose, parentTask, onGenerationComplete }) {
  const [userRequest, setUserRequest] = useState('');
  const [showGame, setShowGame] = useState(false);
  const [selectedGame, setSelectedGame] = useState(null); // 'tictactoe' or 'snake'

  const {
    isGenerating,
    status,
    error,
    generatedVariant,
    startGeneration,
    reset,
  } = useVariantGeneration(parentTask?.id);

  /**
   * Handle submit
   */
  const handleSubmit = useCallback(async () => {
    if (!userRequest.trim() || !parentTask?.id) return;

    // Randomly select game (50/50)
    const game = Math.random() < 0.5 ? 'tictactoe' : 'snake';
    setSelectedGame(game);
    setShowGame(true);
    await startGeneration(userRequest.trim());
  }, [userRequest, parentTask?.id, startGeneration]);

  /**
   * Handle close
   */
  const handleClose = useCallback(() => {
    reset();
    setUserRequest('');
    setShowGame(false);
    setSelectedGame(null);
    onClose();
  }, [reset, onClose]);

  /**
   * Handle game end (generation complete)
   */
  const handleGameEnd = useCallback((result) => {
    // Game ended, but we wait for generation status
    // This is just for UX - user keeps playing
  }, []);

  if (!isOpen) return null;

  const isStep1 = !showGame && !generatedVariant;
  const isStep2 = showGame && isGenerating;
  const isStep3 = generatedVariant || (status === 'failed' && error);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Dialog */}
      <div className="relative z-10 w-full max-w-[640px] mx-4 rounded-[20px] border border-white/[0.06] bg-[#111118] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
          <div>
            <h2 className="text-xl font-bold text-white">
              {isStep1 && 'Создать похожее задание'}
              {isStep2 && 'Генерация варианта...'}
              {isStep3 && error && 'Ошибка генерации'}
              {isStep3 && !error && 'Вариант создан!'}
            </h2>
            {parentTask && (
              <p className="text-sm text-white/40 mt-1">
                На основе: {parentTask.title}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="p-2 text-white/40 hover:text-white transition-colors"
          >
            <AppIcon name="close" className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 min-h-[400px]">
          {/* Step 1: Enter wishes */}
          {isStep1 && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-white/60 mb-2">
                  Опишите, что изменить
                </label>
                <textarea
                  value={userRequest}
                  onChange={(e) => setUserRequest(e.target.value)}
                  placeholder="Например: 'Немного полегче, но больше этапов шифрования'..."
                  className="w-full h-32 px-4 py-3 bg-white/[0.03] border border-white/[0.06] rounded-[12px] text-white placeholder:text-white/30 focus:outline-none focus:border-[#9B6BFF]/50 focus:ring-1 focus:ring-[#9B6BFF]/50 resize-none"
                  maxLength={200}
                />
                <p className="text-xs text-white/30 mt-2 text-right">
                  {userRequest.length}/200
                </p>
              </div>

              {/* Suggested wishes */}
              <div>
                <p className="text-sm text-white/40 mb-3">Или выберите готовый вариант:</p>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTED_WISHES.map((suggestion) => (
                    <button
                      key={suggestion.label}
                      type="button"
                      onClick={() => setUserRequest(suggestion.text)}
                      className={`
                        px-4 py-2 rounded-[10px] text-sm transition-all
                        ${userRequest === suggestion.text
                          ? 'bg-[#9B6BFF] text-white'
                          : 'bg-white/[0.03] text-white/60 hover:bg-white/[0.06] hover:text-white'}
                      `}
                    >
                      {suggestion.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Info box */}
              <div className="mt-6 p-4 rounded-[12px] bg-[#9B6BFF]/10 border border-[#9B6BFF]/20">
                <div className="flex items-start gap-3">
                  <AppIcon name="info" className="h-5 w-5 text-[#9B6BFF] mt-0.5" />
                  <div className="text-sm text-white/70">
                    <p className="font-medium text-white mb-1">Как это работает:</p>
                    <p>
                      ИИ создаст уникальный вариант задания на основе вашего запроса.
                      Генерация займёт около 1 минуты. Пока идёт генерация, вы можете
                      сыграть в крестики-нолики с ботом.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Game while generating */}
          {isStep2 && (
            <div className="flex flex-col items-center justify-center h-full">
              {selectedGame === 'tictactoe' && (
                <TicTacToe mode="endless" onGameEnd={handleGameEnd} />
              )}
              {selectedGame === 'snake' && (
                <Snake mode="endless" onGameEnd={handleGameEnd} />
              )}

              {/* Smooth progress bar */}
              <div className="mt-6 w-full max-w-[300px]">
                <div className="flex items-center justify-between text-xs text-white/40 mb-2">
                  <span>Генерация варианта...</span>
                  <span>ИИ думает</span>
                </div>
                <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full w-full bg-gradient-to-r from-[#9B6BFF] via-[#A97CFF] to-[#9B6BFF] 
                                  bg-[length:200%_100%] animate-progress-indeterminate rounded-full" />
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Result or Error */}
          {isStep3 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              {error ? (
                <>
                  <div className="w-16 h-16 rounded-full bg-[#FF5A6E]/10 flex items-center justify-center mb-4">
                    <AppIcon name="close" className="h-8 w-8 text-[#FF5A6E]" />
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">Ошибка генерации</h3>
                  <p className="text-white/60 text-sm max-w-[400px]">{error}</p>
                </>
              ) : (
                <>
                  <div className="w-16 h-16 rounded-full bg-[#3FD18A]/10 flex items-center justify-center mb-4">
                    <AppIcon name="check-circle" className="h-8 w-8 text-[#3FD18A]" />
                  </div>
                  <h3 className="text-lg font-bold text-white mb-2">Вариант создан!</h3>
                  <p className="text-white/60 text-sm max-w-[400px] mb-6">
                    Новый вариант задания сгенерирован и добавлен в пул UGC-заданий.
                    Задание будет доступно после проверки модератором.
                  </p>
                </>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/[0.06]">
          {isStep1 && (
            <>
              <button
                type="button"
                onClick={handleClose}
                className="px-5 py-2.5 text-sm text-white/60 hover:text-white transition-colors"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={!userRequest.trim() || userRequest.trim().length < 3}
                className="px-5 py-2.5 bg-[#9B6BFF] hover:bg-[#A97CFF] disabled:bg-white/10 disabled:text-white/30 
                         disabled:cursor-not-allowed rounded-[10px] text-sm font-medium text-white transition-all"
              >
                Создать вариант
              </button>
            </>
          )}

          {isStep2 && (
            <p className="text-xs text-white/40">
              Играйте! Генерация займёт около 1 минуты...
            </p>
          )}

          {isStep3 && (
            <>
              <button
                type="button"
                onClick={handleClose}
                className="px-5 py-2.5 text-sm text-white/60 hover:text-white transition-colors"
              >
                Закрыть
              </button>
              {!error && (
                <button
                  type="button"
                  onClick={handleClose}
                  className="px-5 py-2.5 bg-[#9B6BFF] hover:bg-[#A97CFF] rounded-[10px] 
                           text-sm font-medium text-white transition-all"
                >
                  Готово
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
