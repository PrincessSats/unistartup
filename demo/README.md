# HackNet Investor Demo — Cinematic Capture Pipeline

Records a polished walkthrough of **hacknet.tech** with Playwright, then stitches it
into a 1080p MP4 with brand title cards, animated cursor, captions, crossfades, and
optional music.

## Prerequisites
- Node 18+
- `ffmpeg` + `ffprobe` on PATH → `brew install ffmpeg`

## Setup
```bash
cd demo
npm install
npm run setup            # installs the Chromium build Playwright uses
cp .env.example .env     # then fill in DEMO_EMAIL / DEMO_PASSWORD
```

`.env`:
```
BASE_URL=https://hacknet.tech   # or http://localhost:3000 to test locally
DEMO_EMAIL=you@example.com
DEMO_PASSWORD=••••••••
CAPTION_LANG=en                 # en (investors) or ru
```

## Run
```bash
npm run capture          # records raw/<scene>.webm against prod
npm run build            # renders cards + stitches → output/hacknet-demo.mp4
# or both at once:
npm run demo
```

Open the result:
```bash
open output/hacknet-demo.mp4
```

## Scenes (in order)
Intro card → Login → Home → Education (list) → Education (task solver) →
Championship → Knowledge base → Outro card.

Captions and selectors live in `scenes.mjs` — the one place to tweak copy, pacing,
or fix a selector if the prod UI shifts.

## Music (optional)
Drop a track at `assets/music.mp3`. The pipeline loops/trims it to length with a
fade-out. No file → silent audio track (video still valid). Use a track you have
rights to.

## Layout
| File | Role |
|------|------|
| `capture.mjs` | Records one webm per scene; handles login + auth reuse |
| `scenes.mjs` | Scene list: routes, captions, on-page actions, selectors |
| `build.mjs` | ffmpeg post-production → final MP4 |
| `lib/cursor.js` | Injected fake animated cursor + click ripple |
| `lib/captions.js` | Injected lower-third caption overlay |
| `lib/human.js` | Cinematic pacing: eased moves, slow scroll, human typing |

## Troubleshooting
- **Stuck on /login** → check `.env` creds; `raw/_failures/*.png` shows the failure frame.
- **A scene looks empty** → prod selector changed; adjust in `scenes.mjs`, re-run capture.
- **Different pacing** → tune `dwell()` / `smoothScroll()` calls in `scenes.mjs`.
- **No audio** → add `assets/music.mp3`.
