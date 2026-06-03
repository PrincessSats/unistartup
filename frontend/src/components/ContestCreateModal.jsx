import React from 'react';
import ContestPlannerDrawer from '../pages/Admin/Drawers/ContestPlannerDrawer';

export default function ContestCreateModal({ isOpen, contestId, onClose, onSuccess }) {
  return (
    <ContestPlannerDrawer
      open={isOpen}
      contestId={contestId}
      onClose={onClose}
      onCreated={() => { onClose(); onSuccess?.(); }}
      onUpdated={() => { onClose(); onSuccess?.(); }}
    />
  );
}
