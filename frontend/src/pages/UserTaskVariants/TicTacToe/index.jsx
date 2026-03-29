import React, { useState, useEffect, useCallback } from 'react';
import Board from './Board';
import {
  createEmptyBoard,
  makeMove,
  findBestMove,
  checkWinner,
  getGameStatus,
} from './GameEngine';

/**
 * Main Tic-Tac-Toe game component
 *
 * Features:
 * - Endless mode (auto-restart after game ends)
 * - Unbeatable AI (minimax)
 * - Player alternates between 'X' and 'O' each game
 * - Visual feedback for game state
 */
export default function TicTacToe({ mode = 'endless', onGameEnd }) {
  const [board, setBoard] = useState(createEmptyBoard());
  const [isPlayerTurn, setIsPlayerTurn] = useState(true);
  const [gameResult, setGameResult] = useState(null);
  const [winningLine, setWinningLine] = useState(null);
  const [gameCount, setGameCount] = useState(0);
  const [stats, setStats] = useState({ wins: 0, losses: 0, draws: 0 });
  
  // Player alternates: even games = X (goes first), odd games = O (goes second)
  const playerSymbol = gameCount % 2 === 0 ? 'X' : 'O';
  const botSymbol = playerSymbol === 'X' ? 'O' : 'X';

  /**
   * Find the winning line after game ends
   */
  const findWinningLine = useCallback((board, winner) => {
    if (!winner || winner === 'draw') return null;
    
    // Check rows
    for (let i = 0; i < 3; i++) {
      if (board[i][0] === winner && board[i][1] === winner && board[i][2] === winner) {
        return { type: 'row', index: i };
      }
    }
    
    // Check columns
    for (let i = 0; i < 3; i++) {
      if (board[0][i] === winner && board[1][i] === winner && board[2][i] === winner) {
        return { type: 'col', index: i };
      }
    }
    
    // Check diagonals
    if (board[0][0] === winner && board[1][1] === winner && board[2][2] === winner) {
      return { type: 'diag-main' };
    }
    if (board[0][2] === winner && board[1][1] === winner && board[2][0] === winner) {
      return { type: 'diag-anti' };
    }
    
    return null;
  }, []);

  /**
   * Handle game end
   */
  const handleGameEnd = useCallback((result) => {
    setGameResult(result);

    if (result === 'draw') {
      setStats(prev => ({ ...prev, draws: prev.draws + 1 }));
    } else if (result === playerSymbol) {
      setStats(prev => ({ ...prev, wins: prev.wins + 1 }));
    } else {
      setStats(prev => ({ ...prev, losses: prev.losses + 1 }));
    }

    setGameCount(prev => prev + 1);

    if (onGameEnd) {
      onGameEnd(result);
    }
  }, [onGameEnd, playerSymbol]);

  /**
   * Bot move effect
   */
  useEffect(() => {
    if (!isPlayerTurn && !gameResult) {
      const timer = setTimeout(() => {
        const newBoard = board.map(row => [...row]);
        const bestMove = findBestMove(newBoard, botSymbol);

        if (bestMove) {
          makeMove(newBoard, bestMove.row, bestMove.col, botSymbol);
          setBoard(newBoard);

          const result = checkWinner(newBoard);
          if (result) {
            if (result !== 'draw') {
              setWinningLine(findWinningLine(newBoard, result));
            }
            handleGameEnd(result);
          } else {
            setIsPlayerTurn(true);
          }
        }
      }, 500); // Delay for natural feel

      return () => clearTimeout(timer);
    }
  }, [isPlayerTurn, gameResult, board, botSymbol, findWinningLine, handleGameEnd]);

  /**
   * Handle player click
   */
  const handleCellClick = (row, col) => {
    if (!isPlayerTurn || gameResult || board[row][col] !== null) {
      return;
    }

    const newBoard = board.map(row => [...row]);
    makeMove(newBoard, row, col, playerSymbol);
    setBoard(newBoard);

    const result = checkWinner(newBoard);
    if (result) {
      if (result !== 'draw') {
        setWinningLine(findWinningLine(newBoard, result));
      }
      handleGameEnd(result);
    } else {
      setIsPlayerTurn(false);
    }
  };

  /**
   * Start new game (endless mode)
   */
  const startNewGame = useCallback(() => {
    setBoard(createEmptyBoard());
    // Player goes first if X, bot goes first if O
    setIsPlayerTurn(playerSymbol === 'X');
    setGameResult(null);
    setWinningLine(null);
  }, [playerSymbol]);

  const status = gameResult ? getGameStatus(board) : 
                 isPlayerTurn ? `Ваш ход (${playerSymbol})` : 
                 `Бот думает (${botSymbol})`;
  const statusColor = gameResult === 'draw' ? 'text-[#F2C94C]' :
                      gameResult === playerSymbol ? 'text-[#3FD18A]' :
                      gameResult ? 'text-[#FF5A6E]' :
                      isPlayerTurn ? 'text-white' : 'text-white/60';

  return (
    <div className="flex flex-col items-center gap-4 p-6">
      {/* Status */}
      <div className={`text-lg font-medium ${statusColor} transition-colors duration-300`}>
        {status}
      </div>
      
      {/* Stats */}
      <div className="flex gap-6 text-sm text-white/40">
        <span>Игр: {gameCount}</span>
        <span className="text-[#3FD18A]">Побед: {stats.wins}</span>
        <span className="text-[#F2C94C]">Ничьих: {stats.draws}</span>
        <span className="text-[#FF5A6E]">Поражений: {stats.losses}</span>
      </div>
      
      {/* Board */}
      <Board
        board={board}
        onCellClick={handleCellClick}
        disabled={!!gameResult || !isPlayerTurn}
        winningLine={winningLine}
        playerSymbol={playerSymbol}
        botSymbol={botSymbol}
      />
      
      {/* Manual restart button */}
      {gameResult && mode === 'endless' && (
        <button
          type="button"
          onClick={startNewGame}
          className="mt-2 px-4 py-2 text-sm text-[#9B6BFF] hover:text-white transition-colors"
        >
          Начать заново
        </button>
      )}
      
      {/* Hint text */}
      <p className="text-xs text-white/30 text-center max-w-[280px]">
        Совет: бот играет идеально. Лучший результат — ничья!
      </p>
    </div>
  );
}
