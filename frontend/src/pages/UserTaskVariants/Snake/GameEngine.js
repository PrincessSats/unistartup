/**
 * Движок игры Змейка
 *
 * Возможности:
 * - Классическая игра "Змейка"
 * - Управление стрелками
 * - Отслеживание счёта
 * - Бесконечный режим (автоперезагрузка после смерти)
 */

// Константы игры
export const GRID_SIZE = 20;
export const INITIAL_SNAKE = [
  { x: 10, y: 10 },
  { x: 10, y: 11 },
  { x: 10, y: 12 },
];
export const INITIAL_DIRECTION = { x: 0, y: -1 }; // Движение вверх
export const GAME_SPEED = 150; // мс за тик

/**
 * Векторы направления
 */
export const DIRECTIONS = {
  UP: { x: 0, y: -1 },
  DOWN: { x: 0, y: 1 },
  LEFT: { x: -1, y: 0 },
  RIGHT: { x: 1, y: 0 },
};

/**
 * Проверка, является ли направление противоположным (нельзя развернуться)
 */
export function isOppositeDirection(dir1, dir2) {
  return dir1.x === -dir2.x && dir1.y === -dir2.y;
}

/**
 * Создание начального состояния игры
 */
export function createInitialState() {
  return {
    snake: [...INITIAL_SNAKE],
    direction: INITIAL_DIRECTION,
    nextDirection: INITIAL_DIRECTION,
    food: spawnFood(INITIAL_SNAKE),
    score: 0,
    gameOver: false,
    isPaused: false,
  };
}

/**
 * Спавнить еду в случайной позиции (не на змейке)
 */
export function spawnFood(snake) {
  const snakeSet = new Set(snake.map(segment => `${segment.x},${segment.y}`));

  let food;
  do {
    food = {
      x: Math.floor(Math.random() * GRID_SIZE),
      y: Math.floor(Math.random() * GRID_SIZE),
    };
  } while (snakeSet.has(`${food.x},${food.y}`));

  return food;
}

/**
 * Обработка тика игры (движение змейки, проверка коллизий, поедание еды)
 */
export function gameTick(state) {
  if (state.gameOver || state.isPaused) {
    return state;
  }
  
  const { snake, direction, nextDirection, food, score } = state;

  // Обновление направления (предотвращение поворотов на 180°)
  const newDirection = isOppositeDirection(direction, nextDirection)
    ? direction
    : nextDirection;

  // Вычисление новой позиции головы
  const head = snake[0];
  const newHead = {
    x: head.x + newDirection.x,
    y: head.y + newDirection.y,
  };

  // Проверка коллизии со стеной
  if (newHead.x < 0 || newHead.x >= GRID_SIZE || newHead.y < 0 || newHead.y >= GRID_SIZE) {
    return { ...state, gameOver: true };
  }

  // Проверка коллизии с собой
  const snakeSet = new Set(snake.map(segment => `${segment.x},${segment.y}`));
  if (snakeSet.has(`${newHead.x},${newHead.y}`)) {
    return { ...state, gameOver: true };
  }

  // Создание новой змейки
  const newSnake = [newHead, ...snake];

  // Проверка коллизии с едой
  let newFood = food;
  let newScore = score;

  if (newHead.x === food.x && newHead.y === food.y) {
    // Съедена еда - не удалять хвост, спавнить новую еду
    newScore += 10;
    newFood = spawnFood(newSnake);
  } else {
    // Не съедена - удалить хвост
    newSnake.pop();
  }
  
  return {
    ...state,
    snake: newSnake,
    direction: newDirection,
    food: newFood,
    score: newScore,
  };
}

/**
 * Обработка ввода клавиатуры
 */
export function handleKeyPress(state, key) {
  if (state.gameOver) {
    return state;
  }

  let newDirection = state.nextDirection;

  switch (key) {
    case 'ArrowUp':
    case 'w':
    case 'W':
      if (state.direction.y !== 1) {
        newDirection = DIRECTIONS.UP;
      }
      break;
    case 'ArrowDown':
    case 's':
    case 'S':
      if (state.direction.y !== -1) {
        newDirection = DIRECTIONS.DOWN;
      }
      break;
    case 'ArrowLeft':
    case 'a':
    case 'A':
      if (state.direction.x !== 1) {
        newDirection = DIRECTIONS.LEFT;
      }
      break;
    case 'ArrowRight':
    case 'd':
    case 'D':
      if (state.direction.x !== -1) {
        newDirection = DIRECTIONS.RIGHT;
      }
      break;
    case ' ':
      // Пробел для паузы
      return { ...state, isPaused: !state.isPaused };
    default:
      break;
  }

  return { ...state, nextDirection: newDirection };
}

/**
 * Получить сообщение о статусе игры
 */
export function getGameStatus(state) {
  if (state.gameOver) {
    return `Игра окончена! Счёт: ${state.score}`;
  }
  if (state.isPaused) {
    return 'Пауза';
  }
  return `Счёт: ${state.score}`;
}

/**
 * Проверка, должна ли игра перезагрузиться (для бесконечного режима)
 */
export function shouldRestart(state) {
  return state.gameOver;
}
