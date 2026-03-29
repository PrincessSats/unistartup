/**
 * Snake Game Engine
 *
 * Features:
 * - Classic snake gameplay
 * - Arrow key controls
 * - Score tracking
 * - Endless mode (auto-restart on death)
 */

// Game constants
export const GRID_SIZE = 20;
export const INITIAL_SNAKE = [
  { x: 10, y: 10 },
  { x: 10, y: 11 },
  { x: 10, y: 12 },
];
export const INITIAL_DIRECTION = { x: 0, y: -1 }; // Moving up
export const GAME_SPEED = 150; // ms per tick

/**
 * Direction vectors
 */
export const DIRECTIONS = {
  UP: { x: 0, y: -1 },
  DOWN: { x: 0, y: 1 },
  LEFT: { x: -1, y: 0 },
  RIGHT: { x: 1, y: 0 },
};

/**
 * Check if direction is opposite (can't reverse)
 */
export function isOppositeDirection(dir1, dir2) {
  return dir1.x === -dir2.x && dir1.y === -dir2.y;
}

/**
 * Create initial game state
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
 * Spawn food at random position (not on snake)
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
 * Process game tick (move snake, check collisions, eat food)
 */
export function gameTick(state) {
  if (state.gameOver || state.isPaused) {
    return state;
  }
  
  const { snake, direction, nextDirection, food, score } = state;
  
  // Update direction (prevent 180° turns)
  const newDirection = isOppositeDirection(direction, nextDirection)
    ? direction
    : nextDirection;
  
  // Calculate new head position
  const head = snake[0];
  const newHead = {
    x: head.x + newDirection.x,
    y: head.y + newDirection.y,
  };
  
  // Check wall collision
  if (newHead.x < 0 || newHead.x >= GRID_SIZE || newHead.y < 0 || newHead.y >= GRID_SIZE) {
    return { ...state, gameOver: true };
  }
  
  // Check self collision
  const snakeSet = new Set(snake.map(segment => `${segment.x},${segment.y}`));
  if (snakeSet.has(`${newHead.x},${newHead.y}`)) {
    return { ...state, gameOver: true };
  }
  
  // Create new snake
  const newSnake = [newHead, ...snake];
  
  // Check food collision
  let newFood = food;
  let newScore = score;
  
  if (newHead.x === food.x && newHead.y === food.y) {
    // Ate food - don't remove tail, spawn new food
    newScore += 10;
    newFood = spawnFood(newSnake);
  } else {
    // Didn't eat - remove tail
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
 * Handle keyboard input
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
      // Space to pause
      return { ...state, isPaused: !state.isPaused };
    default:
      break;
  }
  
  return { ...state, nextDirection: newDirection };
}

/**
 * Get game status message
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
 * Check if game should restart (for endless mode)
 */
export function shouldRestart(state) {
  return state.gameOver;
}
