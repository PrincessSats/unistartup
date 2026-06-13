// Injected via addInitScript. Renders a cinematic lower-third caption overlay.
// Exposes window.__demo.showCaption(text, sub) / hideCaption().

(() => {
  if (window.__demoCaptionsInstalled) return;
  window.__demoCaptionsInstalled = true;

  window.__demo = window.__demo || {};

  const build = () => {
    let box = document.getElementById('__demo_caption');
    if (box) return box;
    box = document.createElement('div');
    box.id = '__demo_caption';
    Object.assign(box.style, {
      position: 'fixed',
      left: '64px',
      bottom: '64px',
      maxWidth: '720px',
      padding: '18px 26px',
      borderRadius: '16px',
      background: 'linear-gradient(135deg, rgba(27,21,48,0.92), rgba(40,28,74,0.92))',
      border: '1px solid rgba(155,107,255,0.45)',
      boxShadow: '0 10px 40px rgba(0,0,0,0.45)',
      backdropFilter: 'blur(6px)',
      color: '#ffffff',
      fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
      zIndex: '2147483647',
      pointerEvents: 'none',
      opacity: '0',
      transform: 'translateY(16px)',
      transition: 'opacity 450ms ease, transform 450ms ease',
    });

    const accent = document.createElement('div');
    Object.assign(accent.style, {
      width: '40px',
      height: '4px',
      borderRadius: '999px',
      background: 'linear-gradient(90deg, #8359DD, #9B6BFF)',
      marginBottom: '12px',
    });

    const title = document.createElement('div');
    title.id = '__demo_caption_title';
    Object.assign(title.style, {
      fontSize: '26px',
      fontWeight: '700',
      lineHeight: '1.25',
      letterSpacing: '0.2px',
    });

    const sub = document.createElement('div');
    sub.id = '__demo_caption_sub';
    Object.assign(sub.style, {
      fontSize: '16px',
      fontWeight: '400',
      marginTop: '8px',
      color: 'rgba(255,255,255,0.72)',
      lineHeight: '1.4',
    });

    box.appendChild(accent);
    box.appendChild(title);
    box.appendChild(sub);
    // Parent to <html> so the page-body zoom transform never scales the caption.
    document.documentElement.appendChild(box);
    return box;
  };

  window.__demo.showCaption = (text, subText = '') => {
    const box = build();
    box.querySelector('#__demo_caption_title').textContent = text || '';
    const sub = box.querySelector('#__demo_caption_sub');
    sub.textContent = subText || '';
    sub.style.display = subText ? 'block' : 'none';
    requestAnimationFrame(() => {
      box.style.opacity = '1';
      box.style.transform = 'translateY(0)';
    });
  };

  window.__demo.hideCaption = () => {
    const box = document.getElementById('__demo_caption');
    if (!box) return;
    box.style.opacity = '0';
    box.style.transform = 'translateY(16px)';
  };
})();
