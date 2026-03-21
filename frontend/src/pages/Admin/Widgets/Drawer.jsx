import React, { useEffect, useCallback } from 'react';

const overlayBase = 'fixed inset-0 bg-black/70 backdrop-blur-sm z-50';
const drawerBase = 'fixed top-0 right-0 h-full bg-[#0B0A10] border-l border-white/[0.09] z-50 overflow-hidden flex flex-col';

function Drawer({ open, onClose, title, subtitle, width = '640px', children, footer }) {
  const handleOverlayClick = useCallback((event) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  }, [onClose]);

  const handleEscKey = useCallback((event) => {
    if (event.key === 'Escape' && open) {
      onClose();
    }
  }, [open, onClose]);

  useEffect(() => {
    if (open) {
      document.addEventListener('keydown', handleEscKey);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEscKey);
      document.body.style.overflow = 'unset';
    };
  }, [open, handleEscKey]);

  if (!open) return null;

  return (
    <div className={overlayBase} onClick={handleOverlayClick}>
      <div
        className={drawerBase}
        style={{ width }}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 p-8 border-b border-white/[0.09]">
          <div className="flex-1">
            <h3 className="text-white text-[24px] leading-[32px] font-medium">
              {title}
            </h3>
            {subtitle && (
              <p className="text-white/60 text-[14px] mt-2">
                {subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-white/60 hover:text-white transition-colors text-[14px]"
          >
            Закрыть
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-8">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="border-t border-white/[0.09] p-8 pt-6">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export default Drawer;
