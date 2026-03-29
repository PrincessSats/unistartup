import React from 'react';
import AppIcon from '../../components/AppIcon';
import { useNavigate } from 'react-router-dom';

/**
 * Variant Card component
 * Displays a single user-generated variant with vote controls
 */
export default function VariantCard({ variant, onVote, userVote }) {
  const navigate = useNavigate();

  const {
    variant_id,
    spec_title,
    spec_description,
    upvotes,
    downvotes,
    net_rating,
    created_at,
  } = variant;

  const formattedDate = created_at
    ? new Date(created_at).toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      })
    : '';

  const handleClick = () => {
    // Navigate to the published task if it exists
    if (variant.published_task_id) {
      navigate(`/education/${variant.published_task_id}`);
    }
  };

  return (
    <div
      className="p-4 rounded-[12px] border border-white/[0.06] bg-white/[0.02] hover:border-white/[0.09] transition-colors cursor-pointer"
      onClick={handleClick}
    >
      <div className="flex items-start justify-between gap-4">
        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-bold text-white truncate hover:text-[#9B6BFF] transition-colors">
            {spec_title || 'Без названия'}
          </h3>
          {spec_description && (
            <p className="mt-1 text-sm text-white/60 line-clamp-2">
              {spec_description}
            </p>
          )}
          
          <div className="mt-3 flex items-center gap-4 text-xs text-white/40">
            {formattedDate && (
              <span>{formattedDate}</span>
            )}
            <div className="flex items-center gap-1">
              <AppIcon name="thumbs-up" className="h-3.5 w-3.5 text-[#3FD18A]" />
              <span className="text-[#3FD18A]">{upvotes}</span>
            </div>
            <div className="flex items-center gap-1">
              <AppIcon name="thumbs-down" className="h-3.5 w-3.5 text-[#FF5A6E]" />
              <span className="text-[#FF5A6E]">{downvotes}</span>
            </div>
            <span className={`
              px-2 py-0.5 rounded-full text-xs font-medium
              ${net_rating > 0 ? 'bg-[#3FD18A]/10 text-[#3FD18A]' :
                net_rating < 0 ? 'bg-[#FF5A6E]/10 text-[#FF5A6E]' :
                'bg-white/10 text-white/60'}
            `}>
              {net_rating > 0 ? '+' : ''}{net_rating}
            </span>
          </div>
        </div>

        {/* Vote controls */}
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onVote(variant_id, 'upvote');
            }}
            className={`
              p-2 rounded-[8px] transition-all
              ${userVote === 'upvote'
                ? 'bg-[#3FD18A]/20 text-[#3FD18A]'
                : 'bg-white/[0.03] text-white/40 hover:text-[#3FD18A] hover:bg-[#3FD18A]/10'}
            `}
            aria-label="Upvote"
          >
            <AppIcon name="thumbs-up" className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onVote(variant_id, 'downvote');
            }}
            className={`
              p-2 rounded-[8px] transition-all
              ${userVote === 'downvote'
                ? 'bg-[#FF5A6E]/20 text-[#FF5A6E]'
                : 'bg-white/[0.03] text-white/40 hover:text-[#FF5A6E] hover:bg-[#FF5A6E]/10'}
            `}
            aria-label="Downvote"
          >
            <AppIcon name="thumbs-down" className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
