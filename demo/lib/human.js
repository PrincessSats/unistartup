// Node-side cinematic pacing helpers. Operate on a Playwright `page`.
// All movement is deliberate and eased so the recorded video feels human, not robotic.

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Show / hide the injected lower-third caption.
export async function caption(page, title, sub = '') {
  await page.evaluate(
    ([t, s]) => window.__demo?.showCaption?.(t, s),
    [title, sub]
  );
}
export async function hideCaption(page) {
  await page.evaluate(() => window.__demo?.hideCaption?.());
}

// Center the fake cursor immediately (no animation) — used at scene start.
export async function placeCursor(page, x, y) {
  await page.evaluate(([px, py]) => window.__demo?.setCursor?.(px, py), [x, y]);
}

// Move fake cursor + real mouse together to absolute viewport coords, eased.
export async function moveTo(page, x, y, duration = 850) {
  await page.evaluate(
    ([px, py, d]) => window.__demo?.moveCursor?.(px, py, d),
    [x, y, duration]
  );
  await page.mouse.move(x, y); // keep real mouse in sync for hover states
  await sleep(duration + 60);
}

// Move to an element's center, optionally hover-dwell, then return its box.
export async function moveToEl(page, locator, { duration = 850, dwell = 350 } = {}) {
  await locator.scrollIntoViewIfNeeded().catch(() => {});
  const box = await locator.boundingBox();
  if (!box) return null;
  const x = Math.round(box.x + box.width / 2);
  const y = Math.round(box.y + box.height / 2);
  await moveTo(page, x, y, duration);
  await page.mouse.move(x, y);
  if (dwell) await sleep(dwell);
  return box;
}

// Cinematic click: move cursor to element, ripple, then click.
export async function clickEl(page, locator, opts = {}) {
  await moveToEl(page, locator, opts);
  await page.evaluate(() => window.__demo?.clickRipple?.());
  await sleep(180);
  await locator.click({ timeout: 8000 }).catch(async () => {
    // Fallback: force click if normal click is intercepted by overlays.
    await locator.click({ force: true, timeout: 8000 }).catch(() => {});
  });
  await sleep(250);
}

// Type text into a focused field, char-by-char, human cadence.
export async function typeHuman(page, locator, text, perChar = 90) {
  await clickEl(page, locator, { dwell: 150 });
  await locator.fill('');
  await locator.type(text, { delay: perChar });
  await sleep(300);
}

// Smooth, slow scroll by `totalPx` over `steps`, easing in/out. Negative scrolls up.
export async function smoothScroll(page, totalPx, { steps = 60, stepDelay = 16 } = {}) {
  await page.evaluate(
    async ([total, n, delay]) => {
      const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
      let prev = 0;
      for (let i = 1; i <= n; i++) {
        const e = ease(i / n);
        const target = total * e;
        window.scrollBy(0, target - prev);
        prev = target;
        await new Promise((r) => setTimeout(r, delay));
      }
    },
    [totalPx, steps, stepDelay]
  );
}

// Hold on the current frame for a beat (cinematic dwell).
export async function dwell(ms = 1200) {
  await sleep(ms);
}

// --- Zoom (Ken Burns) -------------------------------------------------------

// Smoothly zoom toward a viewport point.
export async function zoomToPoint(page, x, y, scale = 1.4, duration = 1200) {
  await page.evaluate(
    ([px, py, s, d]) => window.__demo?.zoomTo?.(px, py, s, d),
    [x, y, scale, duration]
  );
  await sleep(duration + 80);
}

// Zoom toward an element's center (scrolls it into view first).
export async function zoomToEl(page, locator, { scale = 1.45, duration = 1200, dwell = 900 } = {}) {
  await locator.scrollIntoViewIfNeeded().catch(() => {});
  await sleep(250);
  const box = await locator.boundingBox().catch(() => null);
  const x = box ? Math.round(box.x + box.width / 2) : 960;
  const y = box ? Math.round(box.y + Math.min(box.height / 2, 220)) : 400;
  // Drift the cursor to the focus point as we zoom — feels intentional.
  await page.evaluate(([px, py]) => window.__demo?.moveCursor?.(px, py, 700), [x, y]);
  await zoomToPoint(page, x, y, scale, duration);
  if (dwell) await sleep(dwell);
}

// Зум "по размеру элемента": масштаб подбирается так, чтобы панель влезла в кадр
// целиком (с отступом). Большие панели → масштаб ≈1.0 (показ полностью, без обрезки),
// мелкие цели → приближение, но не больше maxScale.
export async function zoomToFit(
  page,
  locator,
  { margin = 80, maxScale = 1.3, duration = 1200, dwell = 1500 } = {}
) {
  await locator.scrollIntoViewIfNeeded().catch(() => {});
  await sleep(300);
  const box = await locator.boundingBox().catch(() => null);
  if (!box) {
    // запасной вариант: лёгкий зум по центру
    await zoomToPoint(page, 960, 400, 1.15, duration);
    if (dwell) await sleep(dwell);
    return;
  }
  const vw = 1920;
  const vh = 1080;
  const fit = Math.min(vw / (box.width + 2 * margin), vh / (box.height + 2 * margin));
  const scale = Math.max(1.0, Math.min(fit, maxScale));
  const x = Math.round(box.x + box.width / 2);
  const y = Math.round(box.y + box.height / 2);
  await page.evaluate(([px, py]) => window.__demo?.moveCursor?.(px, py, 700), [x, y]);
  await zoomToPoint(page, x, y, scale, duration);
  if (dwell) await sleep(dwell);
}

export async function zoomReset(page, duration = 1000) {
  await page.evaluate(([d]) => window.__demo?.zoomReset?.(d), [duration]);
  await sleep(duration + 80);
}

// Navigate by visibly clicking a sidebar item (with a zoom flourish), falling
// back to a direct goto if the click target can't be found. `base` = BASE_URL.
export async function gotoViaSidebar(page, { base, label, route, settleMs = 4000 }) {
  const link = page
    .locator(`a:has-text("${label}"), nav a:has-text("${label}")`)
    .first();
  const visible = await link.isVisible().catch(() => false);
  if (visible) {
    // zoom to the sidebar, then click the item.
    await zoomToEl(page, link, { scale: 1.5, duration: 1000, dwell: 500 });
    await clickEl(page, link);
    await zoomReset(page, 800);
    await page.waitForLoadState('networkidle').catch(() => {});
  } else {
    await page.goto(`${base}${route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle').catch(() => {});
  }
  await sleep(settleMs);
}

// Закрыть открытое модальное окно (например форму создания UGC): сначала Escape,
// затем поиск кнопки закрытия. Курсор анимируется к крестику, если он найден.
export async function closeModal(page) {
  await page.keyboard.press('Escape').catch(() => {});
  await sleep(500);
  const closers = [
    'button:has-text("Закрыть")',
    'button:has-text("Отмена")',
    'button:has-text("Отменить")',
    '[aria-label*="close" i]',
    '[aria-label*="закрыть" i]',
    'button:has-text("✕")',
    'button:has-text("×")',
  ];
  for (const sel of closers) {
    const loc = page.locator(sel).first();
    if (await loc.isVisible().catch(() => false)) {
      await clickEl(page, loc, { dwell: 150 });
      await sleep(400);
      return;
    }
  }
}

// Best-effort dismissal of cookie banners / onboarding overlays on prod.
export async function dismissOverlays(page) {
  const candidates = [
    'button:has-text("Принять")',
    'button:has-text("Accept")',
    'button:has-text("Согласен")',
    'button:has-text("Понятно")',
    'button:has-text("Пропустить")',
    'button:has-text("Skip")',
    'button:has-text("Закрыть")',
    'button:has-text("Начать")',
    '[aria-label="close"]',
    '[aria-label="Close"]',
  ];
  for (const sel of candidates) {
    const loc = page.locator(sel).first();
    if (await loc.isVisible().catch(() => false)) {
      await loc.click({ timeout: 2000 }).catch(() => {});
      await sleep(400);
    }
  }
}
