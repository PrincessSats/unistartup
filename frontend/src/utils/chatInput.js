export function clampChatInput(value, maxChars) {
  const normalizedMax = Number.isFinite(Number(maxChars)) ? Number(maxChars) : 0;
  if (normalizedMax <= 0) return '';
  return String(value || '').slice(0, normalizedMax);
}

export function getChatRemaining(value, maxChars) {
  const normalizedMax = Number.isFinite(Number(maxChars)) ? Number(maxChars) : 0;
  if (normalizedMax <= 0) return 0;
  return Math.max(0, normalizedMax - String(value || '').length);
}
