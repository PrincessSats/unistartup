import React, { useState, useEffect } from 'react';
import ContestPlannerDrawer from '../pages/Admin/Drawers/ContestPlannerDrawer';

export default function ContestCreateModal({ isOpen, contestId, onClose, onSuccess }) {
  const [showDrawer, setShowDrawer] = useState(isOpen);

  useEffect(() => {
    setShowDrawer(isOpen);
  }, [isOpen]);

  if (!showDrawer) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-40 flex items-center justify-center">
      {/* Modal backdrop closes on click */}
      <div
        className="absolute inset-0"
        onClick={() => {
          setShowDrawer(false);
          onClose();
        }}
      />

      {/* Modal content */}
      <div className="relative z-50 bg-slate-900 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Close button */}
        <button
          onClick={() => {
            setShowDrawer(false);
            onClose();
          }}
          className="absolute top-4 right-4 text-slate-400 hover:text-white transition"
        >
          ✕
        </button>

        {/* Use existing ContestPlannerDrawer component */}
        <div className="p-6">
          <ContestPlannerDrawer
            contestId={contestId}
            onSuccess={() => {
              setShowDrawer(false);
              onClose();
              onSuccess?.();
            }}
            onClose={() => {
              setShowDrawer(false);
              onClose();
            }}
          />
        </div>
      </div>
    </div>
  );
}
