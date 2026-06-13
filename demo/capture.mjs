// Capture orchestrator. Records one webm per scene against production, with a
// fake animated cursor and cinematic captions injected into every page.
//
//   node capture.mjs
//
// Output: raw/<scene-id>.webm  (+ storageState.json for authed scenes)

import dotenv from 'dotenv';
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { readFileSync, existsSync, mkdirSync, rmSync, renameSync, readdirSync } from 'node:fs';
import { buildScenes } from './scenes.mjs';
import * as h from './lib/human.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
// Load .env from THIS folder, not the caller's cwd.
dotenv.config({ path: join(__dirname, '.env') });
const RAW_DIR = join(__dirname, 'raw');
const STATE_FILE = join(__dirname, 'storageState.json');
const FAIL_DIR = join(__dirname, 'raw', '_failures');

const BASE_URL = (process.env.BASE_URL || 'https://hacknet.tech').replace(/\/$/, '');
const EMAIL = process.env.DEMO_EMAIL || '';
const PASSWORD = process.env.DEMO_PASSWORD || '';
const LANG = (process.env.CAPTION_LANG || 'en').toLowerCase();

const VIEWPORT = { width: 1920, height: 1080 };
const SETTLE_MS = Number(process.env.SETTLE_MS || 4000); // wait for lazy list data

// Init scripts injected before any page script runs (survive navigation).
const cursorJs = readFileSync(join(__dirname, 'lib', 'cursor.js'), 'utf8');
const captionsJs = readFileSync(join(__dirname, 'lib', 'captions.js'), 'utf8');

function freshDirs() {
  if (existsSync(RAW_DIR)) rmSync(RAW_DIR, { recursive: true, force: true });
  mkdirSync(RAW_DIR, { recursive: true });
  mkdirSync(FAIL_DIR, { recursive: true });
}

async function newContext(browser, { authed }) {
  const ctx = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 2,
    locale: 'ru-RU',
    ignoreHTTPSErrors: true, // prod cert CN may not match — don't block capture
    recordVideo: { dir: RAW_DIR, size: VIEWPORT },
    ...(authed && existsSync(STATE_FILE) ? { storageState: STATE_FILE } : {}),
  });
  await ctx.addInitScript(cursorJs);
  await ctx.addInitScript(captionsJs);
  return ctx;
}

// Move the recorded webm to a stable, scene-named path.
async function finalizeVideo(page, sceneId) {
  const video = page.video();
  await page.context().close(); // flush video to disk
  if (!video) return;
  const tmpPath = await video.path().catch(() => null);
  const target = join(RAW_DIR, `${sceneId}.webm`);
  if (tmpPath && existsSync(tmpPath)) {
    renameSync(tmpPath, target);
    console.log(`  saved raw/${sceneId}.webm`);
  } else {
    // Fallback: grab the newest stray webm.
    const strays = readdirSync(RAW_DIR).filter((f) => f.endsWith('.webm') && f !== `${sceneId}.webm`);
    if (strays.length) {
      renameSync(join(RAW_DIR, strays[strays.length - 1]), target);
      console.log(`  saved raw/${sceneId}.webm (fallback)`);
    }
  }
}

async function doLogin(page) {
  console.log('  logging in...');
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('networkidle').catch(() => {});
  await h.dismissOverlays(page);

  const email = page
    .locator('input[type="email"], input[name="email"], input[autocomplete="username"]')
    .first();
  const pass = page.locator('input[type="password"]').first();

  await email.waitFor({ state: 'visible', timeout: 15000 });
  await h.typeHuman(page, email, EMAIL);
  await h.typeHuman(page, pass, PASSWORD);

  const submit = page
    .locator('button[type="submit"], button:has-text("Войти"), button:has-text("Sign in"), button:has-text("Login")')
    .first();
  await h.clickEl(page, submit);

  // Wait for redirect away from /login (to /home).
  await page
    .waitForURL((u) => !/\/login(\b|$)/.test(u.pathname || ''), { timeout: 20000 })
    .catch(() => console.log('  WARN: did not leave /login — check credentials'));
  await page.waitForLoadState('networkidle').catch(() => {});
  await h.dismissOverlays(page);

  // Persist auth for subsequent scenes.
  await page.context().storageState({ path: STATE_FILE });
  console.log('  auth saved to storageState.json');
}

async function runScene(browser, scene) {
  console.log(`\n[scene ${scene.id}]`);
  const ctx = await newContext(browser, { authed: scene.requiresAuth });
  const page = await ctx.newPage();
  page.setDefaultTimeout(15000);

  try {
    if (scene.doLogin) {
      if (!EMAIL || !PASSWORD) {
        throw new Error('DEMO_EMAIL / DEMO_PASSWORD missing in .env — cannot log in.');
      }
      await doLogin(page);
      // Return to /login visually for a clean login-scene clip framing.
      await page.goto(`${BASE_URL}${scene.route}`, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle').catch(() => {});
    } else {
      await page.goto(`${BASE_URL}${scene.route}`, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle').catch(() => {});
    }
    await h.placeCursor(page, VIEWPORT.width * 0.5, VIEWPORT.height * 0.55);
    // Settle: localhost React lazy-loads list data ~several seconds after
    // networkidle. Wait so scenes film loaded content, not skeletons.
    await h.dwell(scene.doLogin ? 600 : SETTLE_MS);

    await scene.actions(page, h, { lang: LANG });

    await h.dwell(500);
    await finalizeVideo(page, scene.id);
  } catch (err) {
    console.log(`  ERROR in ${scene.id}: ${err.message}`);
    await page
      .screenshot({ path: join(FAIL_DIR, `${scene.id}.png`), fullPage: false })
      .catch(() => {});
    // Discard this scene's video so failed clips never reach the build.
    const video = page.video();
    const stray = video ? await video.path().catch(() => null) : null;
    await ctx.close().catch(() => {});
    if (stray && existsSync(stray)) rmSync(stray, { force: true });
  }
}

async function main() {
  console.log(`Capturing demo against: ${BASE_URL}`);
  console.log(`Captions: ${LANG.toUpperCase()}`);
  if (!EMAIL || !PASSWORD) {
    console.log('NOTE: no creds in .env — authed scenes will likely redirect to /login.');
  }
  freshDirs();

  const browser = await chromium.launch({
    headless: true,
    args: [
      '--force-color-profile=srgb',
      '--disable-features=IsolateOrigins,site-per-process',
      '--disable-http2', // prod TLS/ALPN quirk → ERR_HTTP2_PROTOCOL_ERROR; force HTTP/1.1
    ],
  });

  const scenes = buildScenes({ lang: LANG, base: BASE_URL });
  for (const scene of scenes) {
    await runScene(browser, scene);
  }

  await browser.close();
  console.log('\nCapture complete. Raw clips in raw/. Next: npm run build');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
