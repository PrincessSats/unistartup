import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import AppIcon from './AppIcon';

const VIEWPORT_MARGIN = 12;
const TOOLTIP_GAP = 12;
const OVERLAY_COLOR = 'rgba(5, 4, 12, 0.84)';

const ONBOARDING_STEPS = [
  {
    key: 'achievements',
    title: 'Достижения',
    description: 'Сюда будем выводить твои достижения\nв турнирах и обучении',
    cta: 'Далее',
    isFinal: false,
    target: 'home-hero',
    placement: 'bottom',
    tooltipWidth: 340,
    tooltipMinHeight: 152,
    highlightPadding: 8,
  },
  {
    key: 'education',
    title: 'Обучение',
    description: 'Тут собрали несколько заданий\nдля старта на основе твоих ответов\n— хотим, чтобы тебе было интересно',
    cta: 'Далее',
    isFinal: false,
    target: 'home-training',
    placement: 'top',
    tooltipWidth: 340,
    tooltipMinHeight: 172,
    highlightPadding: 8,
  },
  {
    key: 'faq',
    title: 'Вопросы',
    description: 'Если возникнут вопросы по\nиспользованию платформы - собрали\nответы на них на странице «FAQ»',
    cta: 'Далее',
    isFinal: false,
    target: 'sidebar-faq',
    placement: 'right',
    tooltipWidth: 340,
    tooltipMinHeight: 166,
    highlightPadding: 8,
  },
  {
    key: 'first-task',
    title: 'Первое задание',
    description: 'Теперь ты готов пользоваться\nплатформой! Может сразу пройдешь\nзадание?:)',
    cta: 'К платформе',
    isFinal: true,
    target: 'home-first-task',
    placement: 'left',
    tooltipWidth: 340,
    tooltipMinHeight: 166,
    highlightPadding: 8,
  },
];

function tailClassByPlacement(placement) {
  if (placement === 'bottom') {
    return '-top-1.5 left-1/2 -translate-x-1/2';
  }
  if (placement === 'right') {
    return '-left-1.5 top-1/2 -translate-y-1/2';
  }
  if (placement === 'left') {
    return '-right-1.5 top-1/2 -translate-y-1/2';
  }
  return '-bottom-1.5 left-1/2 -translate-x-1/2';
}

function clamp(value, min, max) {
  const lower = Math.min(min, max);
  const upper = Math.max(min, max);
  return Math.min(Math.max(value, lower), upper);
}

function resolveVisibleTarget(targetName) {
  const candidates = Array.from(document.querySelectorAll(`[data-onboarding-target="${targetName}"]`));
  if (candidates.length === 0) return null;

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const visible = candidates.find((element) => {
    const rect = element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    return rect.bottom > 0 && rect.right > 0 && rect.left < vw && rect.top < vh;
  });

  return visible || null;
}

function buildCutoutRect(step, rect) {
  const padding = step.highlightPadding ?? 8;
  const left = clamp(rect.left - padding, VIEWPORT_MARGIN, window.innerWidth - VIEWPORT_MARGIN);
  const top = clamp(rect.top - padding, VIEWPORT_MARGIN, window.innerHeight - VIEWPORT_MARGIN);
  const right = clamp(rect.right + padding, VIEWPORT_MARGIN, window.innerWidth - VIEWPORT_MARGIN);
  const bottom = clamp(rect.bottom + padding, VIEWPORT_MARGIN, window.innerHeight - VIEWPORT_MARGIN);
  return {
    left,
    top,
    right,
    bottom,
    width: Math.max(12, right - left),
    height: Math.max(12, bottom - top),
    radius: Math.min(14, Math.max(8, Math.min(rect.width, rect.height) * 0.08)),
  };
}

function computeTooltipRect(step, cutout, placement) {
  const width = Math.min(step.tooltipWidth || 340, window.innerWidth - VIEWPORT_MARGIN * 2);
  const minHeight = Math.min(step.tooltipMinHeight || 152, window.innerHeight - VIEWPORT_MARGIN * 2);
  let left = 0;
  let top = 0;

  if (placement === 'bottom') {
    left = cutout.left + cutout.width / 2 - width / 2;
    top = cutout.bottom + TOOLTIP_GAP;
  } else if (placement === 'top') {
    left = cutout.left + cutout.width / 2 - width / 2;
    top = cutout.top - minHeight - TOOLTIP_GAP;
  } else if (placement === 'right') {
    left = cutout.right + TOOLTIP_GAP;
    top = cutout.top + cutout.height / 2 - minHeight / 2;
  } else {
    left = cutout.left - width - TOOLTIP_GAP;
    top = cutout.top + cutout.height / 2 - minHeight / 2;
  }

  return {
    left: clamp(left, VIEWPORT_MARGIN, window.innerWidth - width - VIEWPORT_MARGIN),
    top: clamp(top, VIEWPORT_MARGIN, window.innerHeight - minHeight - VIEWPORT_MARGIN),
    width,
    minHeight,
  };
}

function choosePlacement(step, cutout) {
  const preferred = step.placement || 'bottom';
  const available = {
    top: cutout.top,
    bottom: window.innerHeight - cutout.bottom,
    left: cutout.left,
    right: window.innerWidth - cutout.right,
  };

  if (preferred === 'top' && available.top > 190) return 'top';
  if (preferred === 'bottom' && available.bottom > 190) return 'bottom';
  if (preferred === 'left' && available.left > 360) return 'left';
  if (preferred === 'right' && available.right > 360) return 'right';

  const fallbackOrder = ['bottom', 'top', 'right', 'left'];
  return fallbackOrder.sort((a, b) => available[b] - available[a])[0];
}

function HomeOnboardingOverlay({ stepIndex = 0, onClose, onNext, onFinish }) {
  const step = ONBOARDING_STEPS[stepIndex] || ONBOARDING_STEPS[0];
  const rafRef = useRef(null);
  const [layout, setLayout] = useState(null);

  const fallbackTooltip = useMemo(
    () => ({
      left: Math.max(VIEWPORT_MARGIN, (window.innerWidth - (step.tooltipWidth || 340)) / 2),
      top: Math.max(
        VIEWPORT_MARGIN,
        (window.innerHeight - Math.min(step.tooltipMinHeight || 152, window.innerHeight - VIEWPORT_MARGIN * 2)) / 2
      ),
      width: Math.min(step.tooltipWidth || 340, window.innerWidth - VIEWPORT_MARGIN * 2),
      minHeight: Math.min(step.tooltipMinHeight || 152, window.innerHeight - VIEWPORT_MARGIN * 2),
    }),
    [step.tooltipMinHeight, step.tooltipWidth]
  );

  const syncLayout = useCallback(() => {
    const target = resolveVisibleTarget(step.target);
    if (!target) {
      setLayout(null);
      return;
    }

    const targetRect = target.getBoundingClientRect();
    const cutout = buildCutoutRect(step, targetRect);
    const placement = choosePlacement(step, cutout);
    const tooltip = computeTooltipRect(step, cutout, placement);
    setLayout({ cutout, tooltip, placement });
  }, [step]);

  useEffect(() => {
    const target = resolveVisibleTarget(step.target);
    if (target) {
      target.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }, [step.target]);

  useEffect(() => {
    const schedule = () => {
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
      }
      rafRef.current = requestAnimationFrame(syncLayout);
    };

    schedule();
    window.addEventListener('resize', schedule);
    window.addEventListener('scroll', schedule, true);

    const target = resolveVisibleTarget(step.target);
    let observer = null;
    if (target && typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(schedule);
      observer.observe(target);
    }

    return () => {
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
      }
      window.removeEventListener('resize', schedule);
      window.removeEventListener('scroll', schedule, true);
      observer?.disconnect();
    };
  }, [step.target, syncLayout]);

  const handlePrimaryClick = () => {
    if (step.isFinal) {
      onFinish?.();
      return;
    }
    onNext?.();
  };

  return (
    <div className="fixed inset-0 z-[70] font-sans-figma">
      {layout?.cutout ? (
        <>
          <div className="absolute inset-x-0 top-0" style={{ height: layout.cutout.top, background: OVERLAY_COLOR }} />
          <div className="absolute inset-x-0 bottom-0" style={{ top: layout.cutout.bottom, background: OVERLAY_COLOR }} />
          <div
            className="absolute left-0"
            style={{
              top: layout.cutout.top,
              width: layout.cutout.left,
              height: layout.cutout.height,
              background: OVERLAY_COLOR,
            }}
          />
          <div
            className="absolute right-0"
            style={{
              top: layout.cutout.top,
              left: layout.cutout.right,
              height: layout.cutout.height,
              background: OVERLAY_COLOR,
            }}
          />
          <div
            className="pointer-events-none absolute border border-white/[0.18]"
            style={{
              left: layout.cutout.left,
              top: layout.cutout.top,
              width: layout.cutout.width,
              height: layout.cutout.height,
              borderRadius: `${layout.cutout.radius}px`,
            }}
          />
        </>
      ) : (
        <div className="absolute inset-0" style={{ background: OVERLAY_COLOR }} />
      )}

      <div
        className="pointer-events-auto absolute rounded-[12px] border border-white/[0.08] bg-[rgba(155,107,255,0.14)] p-4 backdrop-blur-[32px]"
        style={{
          left: layout?.tooltip.left ?? fallbackTooltip.left,
          top: layout?.tooltip.top ?? fallbackTooltip.top,
          width: layout?.tooltip.width ?? fallbackTooltip.width,
          minHeight: layout?.tooltip.minHeight ?? fallbackTooltip.minHeight,
        }}
      >
        <span
          className={`absolute h-3 w-3 rotate-45 bg-[rgba(155,107,255,0.14)] ${tailClassByPlacement(layout?.placement || 'bottom')}`}
          aria-hidden
        />

        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="text-[16px] font-medium leading-[20px] tracking-[0.04em] text-white">
              {step.title}
            </h3>
            <p className="mt-2 whitespace-pre-line text-[14px] leading-[20px] tracking-[0.04em] text-white/95">
              {step.description}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="mt-0.5 shrink-0 text-white/60 transition-colors hover:text-white"
            aria-label="Закрыть онбординг"
          >
            <AppIcon name="close" className="h-[14px] w-[14px]" />
          </button>
        </div>

        <button
          type="button"
          onClick={handlePrimaryClick}
          className="mt-3 inline-flex h-11 items-center justify-center rounded-lg border border-white/[0.14] bg-[linear-gradient(88deg,#563BA6_1.28%,#57389E_15.3%,#593C9E_35.4%,#8359DD_62.97%,#9F63FF_98.48%)] px-4 text-[16px] leading-[20px] tracking-[0.04em] text-white transition-opacity hover:opacity-90"
        >
          {step.cta}
        </button>
      </div>
    </div>
  );
}

export default HomeOnboardingOverlay;
