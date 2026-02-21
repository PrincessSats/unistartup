import defaultVisual from '../assets/education/default.svg';
import cryptoVisual from '../assets/education/crypto.svg';
import forensicsVisual from '../assets/education/forensics.svg';
import osintVisual from '../assets/education/osint.svg';
import pwnVisual from '../assets/education/pwn.svg';
import reverseVisual from '../assets/education/reverse.svg';
import stegoVisual from '../assets/education/stego.svg';
import webVisual from '../assets/education/web.svg';

const visualMap = new Map([
  ['web', webVisual],
  ['веб', webVisual],
  ['crypto', cryptoVisual],
  ['криптография', cryptoVisual],
  ['osint', osintVisual],
  ['forensics', forensicsVisual],
  ['форензика', forensicsVisual],
  ['pwn', pwnVisual],
  ['pentest machine', pwnVisual],
  ['reverse', reverseVisual],
  ['re', reverseVisual],
  ['реверс', reverseVisual],
  ['реверс-инжиниринг', reverseVisual],
  ['stego', stegoVisual],
  ['стеганография', stegoVisual],
]);

function normalize(value) {
  return String(value || '').trim().toLowerCase();
}

export function getEducationCardVisual(task) {
  const candidates = [
    normalize(task?.category),
    ...(Array.isArray(task?.tags) ? task.tags.map((tag) => normalize(tag)) : []),
  ];

  for (const candidate of candidates) {
    if (visualMap.has(candidate)) {
      return visualMap.get(candidate);
    }
  }

  return defaultVisual;
}
