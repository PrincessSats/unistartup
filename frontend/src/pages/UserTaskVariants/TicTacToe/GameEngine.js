/**
 * Tic-Tac-Toe Game Engine with Minimax AI
 * 
 * Features:
 * - Unbeatable AI (minimax with alpha-beta pruning)
 * - Endless mode (auto-restart after game ends)
 * - Player always uses 'X', bot uses 'O'
 * - Best outcome for player is a draw (bot never loses)
 */

/**
 * Check if there's a winner on the board
 * @param {Array<Array<string|null>>} board - 3x3 game board
 * @returns {string|null} - 'X', 'O', 'draw', or null (game in progress)
 */
export function checkWinner(board) {
  // Check rows
  for (let i = 0; i < 3; i++) {
    if (board[i][0] && board[i][0] === board[i][1] && board[i][0] === board[i][2]) {
      return board[i][0];
    }
  }
  
  // Check columns
  for (let i = 0; i < 3; i++) {
    if (board[0][i] && board[0][i] === board[1][i] && board[0][i] === board[2][i]) {
      return board[0][i];
    }
  }
  
  // Check diagonals
  if (board[0][0] && board[0][0] === board[1][1] && board[0][0] === board[2][2]) {
    return board[0][0];
  }
  if (board[0][2] && board[0][2] === board[1][1] && board[0][2] === board[2][0]) {
    return board[0][2];
  }
  
  // Check for draw (board full)
  const isFull = board.every(row => row.every(cell => cell !== null));
  if (isFull) {
    return 'draw';
  }
  
  // Game still in progress
  return null;
}

/**
 * Get available moves on the board
 * @param {Array<Array<string|null>>} board - 3x3 game board
 * @returns {Array<{row: number, col: number}>} - Array of available moves
 */
export function getAvailableMoves(board) {
  const moves = [];
  for (let row = 0; row < 3; row++) {
    for (let col = 0; col < 3; col++) {
      if (board[row][col] === null) {
        moves.push({ row, col });
      }
    }
  }
  return moves;
}

/**
 * Minimax algorithm with alpha-beta pruning
 * Finds the optimal move for the current player
 * 
 * @param {Array<Array<string|null>>} board - 3x3 game board
 * @param {number} depth - Current search depth
 * @param {boolean} isMaximizing - True if maximizing player (bot 'O')
 * @param {number} alpha - Alpha value for pruning
 * @param {number} beta - Beta value for pruning
 * @returns {number} - Score of the position
 */
function minimax(board, depth, isMaximizing, alpha, beta) {
  const result = checkWinner(board);
  
  // Terminal states
  if (result === 'O') return 10 - depth;  // Bot wins (prefer faster wins)
  if (result === 'X') return depth - 10;  // Player wins (prefer slower losses)
  if (result === 'draw') return 0;
  
  if (isMaximizing) {
    let bestScore = -Infinity;
    const moves = getAvailableMoves(board);
    
    for (const { row, col } of moves) {
      board[row][col] = 'O';
      const score = minimax(board, depth + 1, false, alpha, beta);
      board[row][col] = null;
      bestScore = Math.max(bestScore, score);
      alpha = Math.max(alpha, score);
      if (beta <= alpha) break;  // Beta cutoff
    }
    
    return bestScore;
  } else {
    let bestScore = Infinity;
    const moves = getAvailableMoves(board);
    
    for (const { row, col } of moves) {
      board[row][col] = 'X';
      const score = minimax(board, depth + 1, true, alpha, beta);
      board[row][col] = null;
      bestScore = Math.min(bestScore, score);
      beta = Math.min(beta, score);
      if (beta <= alpha) break;  // Alpha cutoff
    }
    
    return bestScore;
  }
}

/**
 * Find the best move for the bot using minimax
 * 
 * @param {Array<Array<string|null>>} board - 3x3 game board
 * @param {string} player - 'O' for bot (default)
 * @returns {{row: number, col: number, score: number}} - Best move with score
 */
export function findBestMove(board, player = 'O') {
  let bestScore = -Infinity;
  let bestMove = { row: 0, col: 0, score: 0 };
  const moves = getAvailableMoves(board);
  
  // If first move, prefer center, then corners
  if (moves.length === 9) {
    return { row: 1, col: 1, score: 0 };
  }
  if (moves.length === 8 && board[1][1] === null) {
    return { row: 1, col: 1, score: 0 };
  }
  
  for (const { row, col } of moves) {
    board[row][col] = player;
    const score = minimax(board, 0, false, -Infinity, Infinity);
    board[row][col] = null;
    
    if (score > bestScore) {
      bestScore = score;
      bestMove = { row, col, score };
    }
  }
  
  return bestMove;
}

/**
 * Create a new empty game board
 * @returns {Array<Array<string|null>>} - 3x3 empty board
 */
export function createEmptyBoard() {
  return [
    [null, null, null],
    [null, null, null],
    [null, null, null],
  ];
}

/**
 * Make a move on the board
 * 
 * @param {Array<Array<string|null>>} board - 3x3 game board
 * @param {number} row - Row index (0-2)
 * @param {number} col - Column index (0-2)
 * @param {string} player - 'X' or 'O'
 * @returns {boolean} - True if move was successful, false if cell occupied
 */
export function makeMove(board, row, col, player) {
  if (board[row][col] !== null) {
    return false;
  }
  board[row][col] = player;
  return true;
}

/**
 * Check if the game is over
 * @param {Array<Array<string|null>>} board - 3x3 game board
 * @returns {{isOver: boolean, result: string|null}} - Game over status
 */
export function isGameOver(board) {
  const result = checkWinner(board);
  return {
    isOver: result !== null,
    result: result,
  };
}

/**
 * Get the game status as a human-readable string
 * @param {Array<Array<string|null>>} board - 3x3 game board
 * @returns {string} - Game status
 */
export function getGameStatus(board) {
  const result = checkWinner(board);
  
  if (result === 'X') {
    return 'Вы победили! (Невозможно — бот играет идеально)';
  }
  if (result === 'O') {
    return 'Бот победил!';
  }
  if (result === 'draw') {
    return 'Ничья! Бот сыграл идеально.';
  }
  
  return 'Ход игрока';
}
