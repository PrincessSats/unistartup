import React from 'react';

/**
 * Individual cell component for Tic-Tac-Toe board
 */
export default function Cell({ value, onClick, disabled, isWinning, playerSymbol, botSymbol }) {
  // Determine colors based on which symbol is player/bot
  const playerColor = '#9B6BFF';
  const botColor = '#FF5A6E';
  
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`
        aspect-square w-full rounded-[12px] text-4xl font-bold
        transition-all duration-200
        flex items-center justify-center
        ${value === null && !disabled
          ? 'bg-white/[0.05] hover:bg-[#9B6BFF]/20 cursor-pointer hover:scale-105'
          : 'bg-white/[0.03] cursor-default'}
        ${isWinning ? 'bg-[#3FD18A]/20 border-2 border-[#3FD18A]' : 'border border-white/[0.06]'}
        ${value === playerSymbol ? `text-[${playerColor}]` : ''}
        ${value === botSymbol ? `text-[${botColor}]` : ''}
        disabled:opacity-50
      `}
      aria-label={value ? `Cell contains ${value}` : 'Empty cell'}
    >
      {value === playerSymbol && (
        <svg className="w-12 h-12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" style={{ color: playerColor }}>
          <line x1="4" y1="4" x2="20" y2="20" strokeLinecap="round" />
          <line x1="20" y1="4" x2="4" y2="20" strokeLinecap="round" />
        </svg>
      )}
      {value === botSymbol && (
        <svg className="w-12 h-12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" style={{ color: botColor }}>
          <circle cx="12" cy="12" r="8" />
        </svg>
      )}
    </button>
  );
}
