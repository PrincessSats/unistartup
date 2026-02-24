import { clampChatInput, getChatRemaining } from './chatInput';

describe('chatInput utils', () => {
  test('clampChatInput keeps value within max length', () => {
    expect(clampChatInput('abcdef', 3)).toBe('abc');
    expect(clampChatInput('abc', 10)).toBe('abc');
  });

  test('getChatRemaining returns max on empty input', () => {
    expect(getChatRemaining('', 150)).toBe(150);
  });

  test('getChatRemaining never goes below zero', () => {
    expect(getChatRemaining('abcdef', 3)).toBe(0);
  });
});
