import React from 'react';
import Cell from './Cell';

/**
 * Tic-Tac-Toe board component (3x3 grid)
 */
export default function Board({ board, onCellClick, disabled, winningLine, playerSymbol, botSymbol }) {
  /**
   * Check if a cell is part of the winning line
   */
  const isWinningCell = (row, col) => {
    if (!winningLine) return false;
    
    // Check rows
    if (winningLine.type === 'row' && winningLine.index === row) return true;
    // Check columns
    if (winningLine.type === 'col' && winningLine.index === col) return true;
    // Check diagonals
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
