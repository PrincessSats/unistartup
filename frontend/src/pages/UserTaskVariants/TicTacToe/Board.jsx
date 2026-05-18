import React from 'react';
import Cell from './Cell';

/**
 * Компонент доски для крестиков-ноликов (сетка 3x3)
 */
export default function Board({ board, onCellClick, disabled, winningLine, playerSymbol, botSymbol }) {
  /**
   * Проверка, является ли ячейка частью выигрышной линии
   */
  const isWinningCell = (row, col) => {
    if (!winningLine) return false;

    // Проверка строк
    if (winningLine.type === 'row' && winningLine.index === row) return true;
    // Проверка столбцов
    if (winningLine.type === 'col' && winningLine.index === col) return true;
    // Проверка диагоналей
    if (winningLine.type === 'diag-main' && row === col) return true;
    if (winningLine.type === 'diag-anti' && row + col === 2) return true;

    return false;
  };
  
  return (
    <div className="grid grid-cols-3 gap-3 w-full max-w-[280px] mx-auto">
      {board.map((row, rowIndex) =>
        row.map((cell, colIndex) => (
          <Cell
            key={`${rowIndex}-${colIndex}`}
            value={cell}
            onClick={() => onCellClick(rowIndex, colIndex)}
            disabled={disabled || cell !== null}
            isWinning={isWinningCell(rowIndex, colIndex)}
            playerSymbol={playerSymbol}
            botSymbol={botSymbol}
          />
        ))
      )}
    </div>
  );
}
