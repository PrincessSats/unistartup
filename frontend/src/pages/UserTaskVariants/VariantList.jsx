import React, { useState, useEffect, useCallback } from 'react';
import { userVariantsAPI } from '../../services/api';
import AppIcon from '../../components/AppIcon';
import VariantCard from './VariantCard';

/**
 * Variant List component
 * Displays all user-generated variants for a task with voting
 */
export default function VariantList({ taskId, onVote, parentTaskId, parentTaskTitle }) {
  const [variants, setVariants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /**
   * Load variants
   */
  const loadVariants = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await userVariantsAPI.getTaskVariants(taskId);
      setVariants(response.variants || []);
    } catch (err) {
      console.error('Load variants error:', err);
      setError('Не удалось загрузить варианты');
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    if (taskId) {
      loadVariants();
    }
  }, [taskId, loadVariants]);

  /**
   * Handle vote
   */
  const handleVote = async (variantId, voteType) => {
    try {
      await userVariantsAPI.voteVariant(variantId, { vote_type: voteType });

      // Update local state
      setVariants(prevVariants => {
        return prevVariants.map(variant => {
          if (variant.variant_id === variantId) {
            const isSameVote = variant.user_vote === voteType;

            return {
              ...variant,
              user_vote: isSameVote ? null : voteType,
              upvotes: isSameVote && voteType === 'upvote'
                ? variant.upvotes - 1
                : voteType === 'upvote'
                  ? variant.upvotes + 1
                  : variant.upvotes,
              downvotes: isSameVote && voteType === 'downvote'
                ? variant.downvotes - 1
                : voteType === 'downvote'
                  ? variant.downvotes + 1
                  : variant.downvotes,
              net_rating: isSameVote
                ? 0
                : voteType === 'upvote'
                  ? variant.net_rating + 1
                  : variant.net_rating - 1,
            };
          }
          return variant;
        });
      });

      if (onVote) {
        onVote(variantId, voteType);
      }
    } catch (err) {
      console.error('Vote error:', err);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="p-4 rounded-[12px] border border-white/[0.06] bg-white/[0.02] animate-pulse"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 space-y-3">
                <div className="h-5 bg-white/10 rounded w-3/4" />
                <div className="h-4 bg-white/10 rounded w-full" />
                <div className="h-4 bg-white/10 rounded w-2/3" />
              </div>
              <div className="flex flex-col gap-2">
                <div className="w-8 h-8 bg-white/10 rounded-[8px]" />
                <div className="w-8 h-8 bg-white/10 rounded-[8px]" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8 text-center">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-[#FF5A6E]/10 mb-3">
          <AppIcon name="x" className="w-6 h-6 text-[#FF5A6E]" />
        </div>
        <p className="text-[#FF5A6E] text-sm">{error}</p>
      </div>
    );
  }

  if (variants.length === 0) {
    return (
      <div className="py-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-white/[0.03] mb-4">
          <AppIcon name="variants" className="w-8 h-8 text-white/30" />
        </div>
        {parentTaskTitle ? (
          <>
            <p className="text-white/40 text-sm mb-1">
              Для задачи "{parentTaskTitle}" пока нет вариантов
            </p>
            <p className="text-white/30 text-xs">
              Будьте первым — создайте свой вариант!
            </p>
          </>
        ) : (
          <>
            <p className="text-white/40 text-sm mb-1">
              Пока нет вариантов от пользователей
            </p>
            <p className="text-white/30 text-xs">
              Будьте первым — создайте свой вариант!
            </p>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {variants.map((variant) => (
        <VariantCard
          key={variant.variant_id}
          variant={variant}
          onVote={handleVote}
          userVote={variant.user_vote}
        />
      ))}
    </div>
  );
}
