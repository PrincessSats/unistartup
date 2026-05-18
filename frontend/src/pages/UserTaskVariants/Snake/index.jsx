import React, { useState, useEffect, useCallback, useRef } from 'react';
import Board from './Board';
import StatusBar from './StatusBar';
import {
  createInitialState,
  gameTick,
  handleKeyPress,
  GAME_SPEED,
} from './GameEngine';

/**
 * Основной компонент игры Змейка
 *
 * Возможности:
 * - Бесконечный режим (автоперезагрузка после окончания)
 * - Управление стрелками или WASD
 * - Отслеживание счёта с рекордом
 * - Функция паузы (пробел)
 */
export default function Snake({ mode = 'endless', onGameEnd }) {
  const [gameState, setGameState] = useState(createInitialState);
  const [highScore, setHighScore] = useState(0);
  const [gamesPlayed, setGamesPlayed] = useState(0);
  const gameLoopRef = useRef(null);

  // Загрузка рекорда из localStorage
  useEffect(() => {
    const saved = localStorage.getItem('snakeHighScore');
    if (saved) {
      setHighScore(parseInt(saved, 10));
    }
  }, []);

  /**
   * Обработка окончания игры
   */
  const handleGameEnd = useCallback((finalScore) => {
    setGamesPlayed(prev => prev + 1);
    
    if (finalScore > highScore) {
      setHighScore(finalScore);
      localStorage.setItem('snakeHighScore', finalScore.toString());
    }
    
    if (onGameEnd) {
      onGameEnd({ score: finalScore });
    }
  }, [highScore, onGameEnd]);

  /**
   * Игровой цикл
   */
  useEffect(() => {
    if (!gameState.gameOver && !gameState.isPaused) {
      gameLoopRef.current = setInterval(() => {
        setGameState(prev => {
          const newState = gameTick(prev);
          if (!prev.gameOver && newState.gameOver) {
            // Игра только что окончена
            setTimeout(() => handleGameEnd(newState.score), 100);
          }
          return newState;
        });
      }, GAME_SPEED);
    }

    return () => {
      if (gameLoopRef.current) {
        clearInterval(gameLoopRef.current);
      }
    };
  }, [gameState.gameOver, gameState.isPaused, handleGameEnd]);

  /**
   * Управление с клавиатуры
   */
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Предотвращение стандартного поведения для стрелок (скролл)
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {
        e.preventDefault();
      }

      setGameState(prev => handleKeyPress(prev, e.key));
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  /**
   * Ручной перезапуск
   */
  const handleRestart = useCallback(() => {
    setGameState(createInitialState());
  }, []);
  
  return (
    <div className="flex flex-col items-center gap-6 p-6">
      {/* Статус */}
      <StatusBar
        score={gameState.score}
        highScore={highScore}
        gamesPlayed={gamesPlayed}
        gameOver={gameState.gameOver}
        isPaused={gameState.isPaused}
      />

      {/* Доска */}
      <Board
        snake={gameState.snake}
        food={gameState.food}
        gameOver={gameState.gameOver}
        isPaused={gameState.isPaused}
      />

      {/* Кнопка ручного перезапуска */}
      {gameState.gameOver && mode === 'endless' && (
        <button
          type="button"
          onClick={handleRestart}
          className="mt-2 px-4 py-2 text-sm text-[#9B6BFF] hover:text-white transition-colors"
        >
          Начать заново
        </button>
      )}

      {/* Подсказка по мобильному управлению */}
      <p className="text-xs text-white/30 text-center max-w-[400px]">
        Совет: используйте стрелки или WASD для управления. Пробел — пауза.
      </p>
    </div>
  );
}
