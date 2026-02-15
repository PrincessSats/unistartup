const kbImage = (index) => `/kb/kb-img-${index}.png`;

const imageStyles = {
  1: 'scale-[1.18] translate-x-[8%]',
  2: 'scale-[1.22] translate-x-[9%]',
  3: 'scale-[1.2] translate-x-[10%]',
  4: 'scale-[1.18] translate-x-[8%]',
  5: 'scale-[1.2] translate-x-[10%]',
  6: 'scale-[1.16] translate-x-[8%]',
  7: 'scale-[1.2] translate-x-[6%] -translate-y-[2%]',
  8: 'scale-[1.2] translate-x-[8%]',
};

const fallbackCycle = [7, 1, 5, 3, 8, 2, 4, 6];

const cardTagMap = {
  'web': 7,
  'веб': 7,
  'osint': 1,
  'криптография': 5,
  'crypto': 5,
  'форензика': 3,
  'forensics': 3,
  'reverse': 4,
  'реверс': 4,
  'pentest': 2,
  'pentest machine': 2,
  'blue team': 8,
  'blueteam': 8,
  'network': 6,
  'сети': 6,
};

const heroTagMap = {
  'web': 7,
  'веб': 7,
  'криптография': 7,
  'crypto': 7,
  'osint': 1,
  'форензика': 3,
  'forensics': 3,
  'reverse': 4,
  'реверс': 4,
  'pentest': 2,
  'pentest machine': 2,
  'blue team': 8,
  'blueteam': 8,
  'network': 5,
  'сети': 5,
};

function normalizeTag(tag) {
  return String(tag || '').trim().toLowerCase();
}

function getFallbackIndex(seed = 0) {
  const safeSeed = Number.isFinite(seed) ? Math.abs(Math.trunc(seed)) : 0;
  return fallbackCycle[safeSeed % fallbackCycle.length];
}

function getVisual(index) {
  return {
    src: kbImage(index),
    imageClassName: imageStyles[index] || '',
  };
}

export function getKnowledgeCardVisual(tags = [], seed = 0) {
  const match = tags.find((tag) => cardTagMap[normalizeTag(tag)]);
  const index = match ? cardTagMap[normalizeTag(match)] : getFallbackIndex(seed);
  return getVisual(index);
}

export function getKnowledgeHeroVisual(tags = [], seed = 0) {
  const match = tags.find((tag) => heroTagMap[normalizeTag(tag)]);
  const index = match ? heroTagMap[normalizeTag(match)] : getFallbackIndex(seed);
  return getVisual(index);
}
