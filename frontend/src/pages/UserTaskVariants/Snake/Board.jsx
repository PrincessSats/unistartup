import React from 'react';

/**
 * Snake game board component
 * Renders the grid with snake and food
 */
export default function Board({ snake, food, gameOver, isPaused }) {
  // Create grid cells
  const cells = [];
  const snakeSet = new Set(snake.map(segment => `${segment.x},${segment.y}`));
  const head = snake[0];
  
  for (let y = 0; y < 20; y++) {
    for (let x = 0; x < 20; x++) {
      const isHead = head.x === x && head.y === y;
      const isBody = snakeSet.has(`${x},${y}`) && !isHead;
      const isFood = food.x === x && food.y === y;
      
      let cellClass = 'bg-white/[0.03] border border-white/[0.04]';
      
      if (isHead) {
        cellClass = 'bg-[#9B6BFF] border border-[#9B6BFF]/50 shadow-[0_0_10px_rgba(155,107,255,0.5)]';
      } else if (isBody) {
        cellClass = 'bg-[#9B6BFF]/70 border border-[#9B6BFF]/30';
      } else if (isFood) {
        cellClass = 'bg-[#3FD18A] border border-[#3FD18A]/50 shadow-[0_0_10px_rgba(63,209,138,0.5)] rounded-full';
      }
      
      if (gameOver && (isHead || isBody)) {
        cellClass = 'bg-[#FF5A6E]/50 border border-[#FF5A6E]/30';
      }
      
      cells.push(
        <div
          key={`${x}-${y}`}
          className={`
            aspect-square w-full rounded-[2px]
            transition-colors duration-100
            ${cellClass}
          `}
        />
      );
    }
  }
  
  return (
    <div className="gap-[1px] w-full max-w-[400px] mx-auto p-2 rounded-[12px] bg-white/[0.02] border border-white/[0.06]" style={{ display: 'grid', gridTemplateColumns: 'repeat(20, 1fr)' }}>
      {cells}
    </div>
  );
}
