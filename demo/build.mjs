// Post-production: normalize raw clips, render brand title cards, crossfade
// everything together, mix optional music, encode a 1080p H.264 MP4.
//
//   node build.mjs
//
// Output: output/hacknet-demo.mp4
// Requires ffmpeg + ffprobe on PATH.

import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, rmSync, readdirSync } from 'node:fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const RAW_DIR = join(__dirname, 'raw');
const CARDS_DIR = join(__dirname, 'cards');
const TMP_DIR = join(__dirname, 'cards', '_tmp');
const OUT_DIR = join(__dirname, 'output');
const MUSIC = join(__dirname, 'assets', 'music.mp3');
const FINAL = join(OUT_DIR, 'hacknet-demo.mp4');

const W = 1920;
const H = 1080;
const FPS = 30;
const XFADE = 0.5; // crossfade seconds
const INTRO_SEC = 3.0;
const OUTRO_SEC = 3.2;

function which(bin) {
  try {
    execFileSync(bin, ['-version'], { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

function ff(args) {
  execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', ...args], {
    stdio: 'inherit',
  });
}

function probeDuration(file) {
  const out = execFileSync('ffprobe', [
    '-v', 'error',
    '-show_entries', 'format=duration',
    '-of', 'default=noprint_wrappers=1:nokey=1',
    file,
  ]);
  return parseFloat(out.toString().trim()) || 0;
}

// ---- Brand title cards (rendered via headless Chromium) -------------------

function cardHtml(title, sub) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>
    html,body{margin:0;width:${W}px;height:${H}px;overflow:hidden}
    body{display:flex;align-items:center;justify-content:center;
      font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
      background:radial-gradient(1200px 800px at 50% 35%, #2a1d52 0%, #14102a 55%, #0c0a1a 100%);}
    .wrap{text-align:center;color:#fff;transform:translateY(-20px)}
    .badge{display:inline-block;padding:10px 22px;border-radius:999px;
      border:1px solid rgba(155,107,255,.5);color:#cbb6ff;font-size:22px;letter-spacing:3px;
      text-transform:uppercase;margin-bottom:34px;background:rgba(131,89,221,.12)}
    h1{font-size:96px;margin:0;font-weight:800;letter-spacing:1px;
      background:linear-gradient(90deg,#ffffff,#b89bff);-webkit-background-clip:text;
      background-clip:text;color:transparent}
    .bar{width:120px;height:6px;border-radius:999px;margin:34px auto 0;
      background:linear-gradient(90deg,#8359DD,#9B6BFF)}
    p{font-size:30px;margin:30px 0 0;color:rgba(255,255,255,.72);font-weight:400}
  </style></head><body><div class="wrap">
    <div class="badge">HackNet</div>
    <h1>${title}</h1>
    <div class="bar"></div>
    <p>${sub}</p>
  </div></body></html>`;
}

async function renderCards() {
  if (existsSync(CARDS_DIR)) rmSync(CARDS_DIR, { recursive: true, force: true });
  mkdirSync(TMP_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });

  const cards = [
    { id: 'intro', title: 'Learn Cybersecurity', sub: 'Hands-on CTF challenges, contests & a live CVE knowledge base' },
    { id: 'outro', title: 'hacknet.tech', sub: 'Start hacking — the right way' },
  ];
  for (const c of cards) {
    await page.setContent(cardHtml(c.title, c.sub), { waitUntil: 'networkidle' });
    await page.screenshot({ path: join(CARDS_DIR, `${c.id}.png`) });
  }
  await browser.close();
}

// ---- Segment normalization -------------------------------------------------

// A still PNG -> short video segment.
function cardToSegment(pngId, seconds, outFile) {
  ff([
    '-loop', '1', '-t', String(seconds), '-i', join(CARDS_DIR, `${pngId}.png`),
    '-vf', `fps=${FPS},scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,fade=t=in:st=0:d=0.4,fade=t=out:st=${(seconds - 0.4).toFixed(2)}:d=0.4`,
    '-r', String(FPS),
    outFile,
  ]);
}

// A raw webm clip -> normalized 1080p mp4 segment.
function clipToSegment(webm, outFile) {
  ff([
    '-i', webm,
    '-vf', `fps=${FPS},scale=${W}:${H}:force_original_aspect_ratio=decrease,pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p`,
    '-an', '-r', String(FPS),
    outFile,
  ]);
}

// ---- xfade chain -----------------------------------------------------------

function xfadeAll(segments, outFile) {
  const durs = segments.map(probeDuration);
  const inputs = segments.flatMap((s) => ['-i', s]);

  if (segments.length === 1) {
    ff([...inputs, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', outFile]);
    return durs[0];
  }

  const filters = [];
  let prev = '0:v';
  let cumOffset = 0; // running length of composite minus this transition
  for (let i = 1; i < segments.length; i++) {
    // offset = sum(d_0..d_{i-1}) - i*XFADE
    cumOffset += durs[i - 1];
    const offset = (cumOffset - i * XFADE).toFixed(3);
    const out = i === segments.length - 1 ? 'vout' : `v${i}`;
    filters.push(
      `[${prev}][${i}:v]xfade=transition=fade:duration=${XFADE}:offset=${offset}[${out}]`
    );
    prev = out;
  }
  const totalDur = durs.reduce((a, b) => a + b, 0) - (segments.length - 1) * XFADE;

  ff([
    ...inputs,
    '-filter_complex', filters.join(';'),
    '-map', '[vout]',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
    outFile,
  ]);
  return totalDur;
}

// ---- Audio mux -------------------------------------------------------------

function muxAudio(videoFile, totalDur, outFile) {
  const hasMusic = existsSync(MUSIC);
  if (hasMusic) {
    const fadeStart = Math.max(0, totalDur - 2.5).toFixed(2);
    ff([
      '-i', videoFile,
      '-stream_loop', '-1', '-i', MUSIC,
      '-filter_complex',
      `[1:a]volume=0.55,afade=t=in:st=0:d=2,afade=t=out:st=${fadeStart}:d=2.5[a]`,
      '-map', '0:v', '-map', '[a]',
      '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
      '-t', totalDur.toFixed(2),
      '-movflags', '+faststart',
      outFile,
    ]);
  } else {
    // Silent stereo track so the MP4 has a valid audio stream everywhere.
    ff([
      '-i', videoFile,
      '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
      '-map', '0:v', '-map', '1:a',
      '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k',
      '-shortest',
      '-movflags', '+faststart',
      outFile,
    ]);
  }
}

// ---- Main ------------------------------------------------------------------

async function main() {
  if (!which('ffmpeg') || !which('ffprobe')) {
    console.error('ERROR: ffmpeg/ffprobe not found on PATH. Install: brew install ffmpeg');
    process.exit(1);
  }
  if (!existsSync(RAW_DIR)) {
    console.error('ERROR: raw/ not found. Run `npm run capture` first.');
    process.exit(1);
  }
  const clips = readdirSync(RAW_DIR)
    .filter((f) => f.endsWith('.webm') && /^\d\d-/.test(f)) // scene clips only, skip strays
    .sort(); // scene ids are zero-padded → lexical sort = scene order
  if (!clips.length) {
    console.error('ERROR: no .webm clips in raw/. Capture produced nothing.');
    process.exit(1);
  }
  console.log(`Found ${clips.length} clips:`, clips.join(', '));

  console.log('Rendering brand cards...');
  await renderCards();

  if (existsSync(OUT_DIR)) rmSync(OUT_DIR, { recursive: true, force: true });
  mkdirSync(OUT_DIR, { recursive: true });

  // Build ordered, normalized segment list: intro card, clips..., outro card.
  console.log('Normalizing segments...');
  const segments = [];
  const introSeg = join(TMP_DIR, 'seg_intro.mp4');
  cardToSegment('intro', INTRO_SEC, introSeg);
  segments.push(introSeg);

  clips.forEach((clip, i) => {
    const seg = join(TMP_DIR, `seg_${String(i).padStart(2, '0')}.mp4`);
    clipToSegment(join(RAW_DIR, clip), seg);
    segments.push(seg);
  });

  const outroSeg = join(TMP_DIR, 'seg_outro.mp4');
  cardToSegment('outro', OUTRO_SEC, outroSeg);
  segments.push(outroSeg);

  console.log('Crossfading timeline...');
  const silent = join(OUT_DIR, '_video_only.mp4');
  const totalDur = xfadeAll(segments, silent);

  console.log(`Muxing audio (${existsSync(MUSIC) ? 'music.mp3' : 'silent'})...`);
  muxAudio(silent, totalDur, FINAL);
  rmSync(silent, { force: true });

  console.log(`\nDone → ${FINAL}`);
  console.log(`Duration ~${totalDur.toFixed(1)}s, ${W}x${H}, H.264.`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
