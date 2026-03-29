import React, { useState, useCallback, useEffect } from 'react';
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

function formatElapsed(secs) {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

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
  const [elapsed, setElapsed] = useState(0);

  const {
    isGenerating,
    status,
    error,
    generatedVariant,
    startGeneration,
    reset,
  } = useVariantGeneration(parentTask?.id);

  // Elapsed timer — runs only while generation is in progress
  useEffect(() => {
    if (!isGenerating) return;
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [isGenerating]);

  /**
   * Handle submit
   */
  const handleSubmit = useCallback(async () => {
    if (!userRequest.trim() || !parentTask?.id) return;

    // Randomly select game (50/50)
    const game = Math.random() < 0.5 ? 'tictactoe' : 'snake';
    setSelectedGame(game);
    setElapsed(0);
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
    setElapsed(0);
    onClose();
  }, [reset, onClose]);

  /**
   * Handle game end (generation complete)
   */
  const handleGameEnd = useCallback((_result) => {
    // Game ended, but we wait for generation status
  }, []);

  if (!isOpen) return null;

  const isStep1 = !showGame && !generatedVariant;
  const isStep2 = showGame && isGenerating;
  const isStep3 = generatedVariant || (status === 'failed' && error);

  // Exponential fill: reaches ~49% at 1 min, ~74% at 2 min, ~87% at 3 min, ~93% at 4 min
  const progressPercent = generatedVariant
    ? 100
    : Math.min(95, Math.round((1 - Math.exp(-elapsed / 90)) * 100));

  // Step states: driven by API status, with time-based fallback
  const stepStates = [
    'done', // "Запрос принят" — always done after submit
    (status === 'generating' || status === 'completed') ? 'done' : 'active',
    status === 'completed'
      ? 'done'
      : (status === 'generating' || progressPercent >= 40) ? 'active' : 'waiting',
    status === 'completed' ? 'done' : progressPercent >= 82 ? 'active' : 'waiting',
  ];

  const STEPS = [
    { label: 'Запрос принят',        desc: 'Задание передано ИИ' },
    { label: 'Анализ оригинала',     desc: 'ИИ изучает структуру задания' },
    { label: 'Генерация варианта',   desc: 'Создание уникального контента' },
    { label: 'Финализация',          desc: 'Проверка и сохранение' },
  ];

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
                      Генерация занимает 3–4 минуты. Пока идёт генерация, вы можете
                      сыграть в крестики-нолики или Змейку с ботом.
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

              {/* Generation progress */}
              <div className="mt-5 w-full max-w-[340px]">
                {/* Timer header */}
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-medium text-white/40 uppercase tracking-wider">
                    Прогресс генерации
                  </span>
                  <span className="text-sm font-mono text-[#9B6BFF] tabular-nums">
                    {formatElapsed(elapsed)}
                  </span>
                </div>

                {/* Steps */}
                <div className="space-y-2 mb-4">
                  {STEPS.map((step, i) => {
                    const state = stepStates[i];
                    return (
                      <div
                        key={step.label}
                        className={`flex items-center gap-3 transition-opacity duration-500 ${state === 'waiting' ? 'opacity-35' : 'opacity-100'}`}
                      >
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${
                          state === 'done'   ? 'bg-[#3FD18A]/15' :
                          state === 'active' ? 'bg-[#9B6BFF]/15' :
                          'bg-white/[0.04]'
                        }`}>
                          {state === 'done' && (
                            <svg className="w-3 h-3 text-[#3FD18A]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                          {state === 'active' && (
                            <div className="w-3 h-3 rounded-full border-2 border-[#9B6BFF] border-t-transparent animate-spin" />
                          )}
                          {state === 'waiting' && (
                            <div className="w-1.5 h-1.5 rounded-full bg-white/20" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm leading-tight ${
                            state === 'done'   ? 'text-[#3FD18A]' :
                            state === 'active' ? 'text-white font-medium' :
                            'text-white/40'
                          }`}>
                            {step.label}
                          </p>
                          <p className="text-[11px] text-white/25 mt-0.5">{step.desc}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Estimated progress bar */}
                <div className="w-full h-1 bg-white/[0.06] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[#9B6BFF] to-[#C084FC] rounded-full transition-all duration-[2000ms] ease-out"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                <div className="flex items-center justify-between mt-1.5">
                  <span className="text-[11px] text-white/25">~3–4 мин</span>
                  <span className="text-[11px] text-white/35 tabular-nums">{progressPercent}%</span>
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
              Играйте! Генерация занимает 3–4 минуты...
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
