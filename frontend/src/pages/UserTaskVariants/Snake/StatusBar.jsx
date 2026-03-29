import React from 'react';
import AppIcon from '../../../components/AppIcon';

/**
 * Snake game status bar
 * Shows score, high score, and game state
 */
export default function StatusBar({ score, highScore, gameOver, isPaused, gamesPlayed }) {
  return (
    <div className="flex flex-col items-center gap-4 w-full max-w-[400px]">
      {/* Score display */}
      <div className="flex items-center gap-6">
        <div className="text-center">
          <div className="text-xs text-white/40 mb-1">Счёт</div>
          <div className="text-2xl font-bold text-white">{score}</div>
        </div>
        
        <div className="w-[1px] h-8 bg-white/10" />
        
        <div className="text-center">
          <div className="text-xs text-white/40 mb-1">Рекорд</div>
          <div className="text-2xl font-bold text-[#3FD18A]">{highScore}</div>
        </div>
        
        <div className="w-[1px] h-8 bg-white/10" />
        
        <div className="text-center">
          <div className="text-xs text-white/40 mb-1">Игр</div>
          <div className="text-2xl font-bold text-[#9B6BFF]">{gamesPlayed}</div>
        </div>
      </div>
      
      {/* Game state indicator */}
      <div className={`
        text-sm font-medium transition-colors duration-300
        ${gameOver ? 'text-[#FF5A6E]' : isPaused ? 'text-[#F2C94C]' : 'text-white/60'}
      `}>
        {gameOver && (
          <span className="flex items-center gap-2">
            <AppIcon name="x" className="h-4 w-4" />
            Игра окончена
          </span>
        )}
        {isPaused && !gameOver && (
          <span className="flex items-center gap-2">
            <AppIcon name="pause" className="h-4 w-4" />
            Пауза (пробел)
          </span>
        )}
        {!gameOver && !isPaused && (
          <span className="flex items-center gap-2">
            <AppIcon name="info" className="h-4 w-4" />
            Управление: стрелки или WASD
          </span>
        )}
      </div>
    </div>
  );
}
