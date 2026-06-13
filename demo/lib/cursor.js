// Injected into every page via addInitScript.
// Real OS mouse pointer is NOT captured in Playwright video, so we draw a fake
// cursor element and expose window.__demo helpers to animate it smoothly.
// Also provides the caption overlay (kept here so a single init script owns the UI layer).

(() => {
  if (window.__demoInstalled) return;
  window.__demoInstalled = true;

  const ensureLayer = () => {
    let layer = document.getElementById('__demo_layer');
    if (layer) return layer;
    layer = document.createElement('div');
    layer.id = '__demo_layer';
    Object.assign(layer.style, {
      position: 'fixed',
      inset: '0',
      zIndex: '2147483647',
      pointerEvents: 'none',
      overflow: 'hidden',
    });
    // Parent to <html>, NOT <body>: body gets the zoom transform, and we want
    // the cursor + captions to stay unscaled on top.
    document.documentElement.appendChild(layer);
    return layer;
  };

  const buildCursor = (layer) => {
    let c = document.getElementById('__demo_cursor');
    if (c) return c;
    c = document.createElement('div');
    c.id = '__demo_cursor';
    Object.assign(c.style, {
      position: 'fixed',
      left: '0px',
      top: '0px',
      width: '28px',
      height: '28px',
      transform: 'translate(-2px, -2px)',
      zIndex: '2147483647',
      pointerEvents: 'none',
      transition: 'opacity 250ms ease',
      filter: 'drop-shadow(0 2px 6px rgba(0,0,0,0.55))',
    });
    // Crisp arrow pointer (SVG), tinted toward brand purple highlight.
    c.innerHTML = `
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M5 3l14 7-6 1.5L9.5 18 5 3z" fill="#ffffff" stroke="#1b1530" stroke-width="1.2" stroke-linejoin="round"/>
      </svg>`;
    layer.appendChild(c);
    return c;
  };

  // Click ripple in brand purple.
  const ripple = (x, y) => {
    const layer = ensureLayer();
    const r = document.createElement('div');
    Object.assign(r.style, {
      position: 'fixed',
      left: x + 'px',
      top: y + 'px',
      width: '10px',
      height: '10px',
      marginLeft: '-5px',
      marginTop: '-5px',
      borderRadius: '999px',
      border: '2px solid #9B6BFF',
      background: 'rgba(131,89,221,0.35)',
      zIndex: '2147483646',
      pointerEvents: 'none',
      transition: 'transform 450ms ease-out, opacity 450ms ease-out',
      opacity: '1',
    });
    layer.appendChild(r);
    requestAnimationFrame(() => {
      r.style.transform = 'scale(5)';
      r.style.opacity = '0';
    });
    setTimeout(() => r.remove(), 500);
  };

  const state = { x: window.innerWidth / 2, y: window.innerHeight * 0.5 };

  const place = () => {
    const layer = ensureLayer();
    const cur = buildCursor(layer);
    cur.style.left = state.x + 'px';
    cur.style.top = state.y + 'px';
  };

  const easeInOut = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

  window.__demo = window.__demo || {};

  // Smoothly move the fake cursor from current pos to (x,y) over `duration` ms.
  window.__demo.moveCursor = (x, y, duration = 800) =>
    new Promise((resolve) => {
      const sx = state.x;
      const sy = state.y;
      const start = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - start) / duration);
        const e = easeInOut(t);
        state.x = sx + (x - sx) * e;
        state.y = sy + (y - sy) * e;
        place();
        if (t < 1) requestAnimationFrame(step);
        else resolve();
      };
      requestAnimationFrame(step);
    });

  // --- Cinematic zoom (Ken Burns) on the page body --------------------------
  // We scale <body> toward a viewport point so that point stays put while the
  // surrounding UI grows. Overlay layer lives on <html>, so it never scales.
  const ensureZoomStyle = () => {
    const b = document.body;
    if (!b.style.willChange) b.style.willChange = 'transform';
  };
  window.__demo.zoomTo = (x, y, scale = 1.4, duration = 1200) => {
    ensureZoomStyle();
    const b = document.body;
    const ox = x + window.scrollX;
    const oy = y + window.scrollY;
    b.style.transformOrigin = `${ox}px ${oy}px`;
    b.style.transition = `transform ${duration}ms cubic-bezier(.34,.02,.2,1)`;
    // force reflow so origin+transition apply before transform changes
    void b.offsetWidth;
    b.style.transform = `scale(${scale})`;
    return new Promise((r) => setTimeout(r, duration + 60));
  };
  window.__demo.zoomReset = (duration = 1000) => {
    const b = document.body;
    b.style.transition = `transform ${duration}ms cubic-bezier(.34,.02,.2,1)`;
    b.style.transform = 'scale(1)';
    return new Promise((r) => setTimeout(r, duration + 60));
  };

  window.__demo.clickRipple = () => ripple(state.x, state.y);
  window.__demo.setCursor = (x, y) => {
    state.x = x;
    state.y = y;
    place();
  };
  window.__demo.cursorPos = () => ({ x: state.x, y: state.y });

  const boot = () => {
    place();
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
  // Re-assert on resize so cursor stays valid.
  window.addEventListener('resize', place);
})();
