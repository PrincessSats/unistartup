/**
 * Движок игры крестиков-ноликов с ИИ Minimax
 *
 * Возможности:
 * - Непобедимый ИИ (minimax с альфа-бета отсечением)
 * - Бесконечный режим (автоперезагрузка после окончания)
 * - Игрок всегда использует 'X', бот использует 'O'
 * - Лучший результат для игрока — ничья (бот никогда не проигрывает)
 */

/**
 * Проверить, есть ли победитель на доске
 * @param {Array<Array<string|null>>} board - доска размером 3x3
 * @returns {string|null} - 'X', 'O', 'draw', или null (игра продолжается)
 */
export function checkWinner(board) {
  // Проверка строк
  for (let i = 0; i < 3; i++) {
    if (board[i][0] && board[i][0] === board[i][1] && board[i][0] === board[i][2]) {
      return board[i][0];
    }
  }

  // Проверка столбцов
  for (let i = 0; i < 3; i++) {
    if (board[0][i] && board[0][i] === board[1][i] && board[0][i] === board[2][i]) {
      return board[0][i];
    }
  }

  // Проверка диагоналей
  if (board[0][0] && board[0][0] === board[1][1] && board[0][0] === board[2][2]) {
    return board[0][0];
  }
  if (board[0][2] && board[0][2] === board[1][1] && board[0][2] === board[2][0]) {
    return board[0][2];
  }

  // Проверка на ничью (доска заполнена)
  const isFull = board.every(row => row.every(cell => cell !== null));
  if (isFull) {
    return 'draw';
  }

  // Игра продолжается
  return null;
}

/**
 * Получить доступные ходы на доске
 * @param {Array<Array<string|null>>} board - доска размером 3x3
 * @returns {Array<{row: number, col: number}>} - Массив доступных ходов
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
 * Алгоритм Minimax с альфа-бета отсечением
 * Находит оптимальный ход для текущего игрока
 *
 * @param {Array<Array<string|null>>} board - доска размером 3x3
 * @param {number} depth - текущая глубина поиска
 * @param {boolean} isMaximizing - true если максимизирующий игрок (бот 'O')
 * @param {number} alpha - значение альфа для отсечения
 * @param {number} beta - значение бета для отсечения
 * @returns {number} - оценка позиции
 */
function minimax(board, depth, isMaximizing, alpha, beta) {
  const result = checkWinner(board);

  // Терминальные состояния
  if (result === 'O') return 10 - depth;  // Бот побеждает (предпочитать более быстрые победы)
  if (result === 'X') return depth - 10;  // Игрок побеждает (предпочитать более медленные поражения)
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
      if (beta <= alpha) break;  // Отсечение бета
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
      if (beta <= alpha) break;  // Отсечение альфа
    }

    return bestScore;
  }
}

/**
 * Найти лучший ход для бота с помощью minimax
 *
 * @param {Array<Array<string|null>>} board - доска размером 3x3
 * @param {string} player - 'O' для бота (по умолчанию)
 * @returns {{row: number, col: number, score: number}} - лучший ход с оценкой
 */
export function findBestMove(board, player = 'O') {
  let bestScore = -Infinity;
  let bestMove = { row: 0, col: 0, score: 0 };
  const moves = getAvailableMoves(board);

  // Если первый ход, предпочитать центр, потом углы
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
 * Создать новую пустую доску для игры
 * @returns {Array<Array<string|null>>} - пустая доска размером 3x3
 */
export function createEmptyBoard() {
  return [
    [null, null, null],
    [null, null, null],
    [null, null, null],
  ];
}

/**
 * Сделать ход на доске
 *
 * @param {Array<Array<string|null>>} board - доска размером 3x3
 * @param {number} row - индекс строки (0-2)
 * @param {number} col - индекс столбца (0-2)
 * @param {string} player - 'X' или 'O'
 * @returns {boolean} - true если ход успешен, false если ячейка занята
 */
export function makeMove(board, row, col, player) {
  if (board[row][col] !== null) {
    return false;
  }
  board[row][col] = player;
  return true;
}

/**
 * Проверить, окончена ли игра
 * @param {Array<Array<string|null>>} board - доска размером 3x3
 * @returns {{isOver: boolean, result: string|null}} - статус окончания игры
 */
export function isGameOver(board) {
  const result = checkWinner(board);
  return {
    isOver: result !== null,
    result: result,
  };
}

/**
 * Получить статус игры в удобочитаемом виде
 * @param {Array<Array<string|null>>} board - доска размером 3x3
 * @returns {string} - статус игры
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
