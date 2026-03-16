"""
GRPO reward system for AI-generated CTF challenges.

RewardType     — enum of the 5 check categories
RewardCheck    — result of a single check on one variant
VariantReward  — aggregated reward for one variant
REWARD_WEIGHTS — per-task-type weight config
compute_group_advantages — GRPO group-relative advantage scores
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RewardType(str, Enum):
    FORMAT = "FORMAT"
    FUNCTIONAL = "FUNCTIONAL"
    SOLVABILITY = "SOLVABILITY"
    NON_TRIVIALITY = "NON_TRIVIALITY"
    QUALITY = "QUALITY"
    RAG_GROUNDING = "RAG_GROUNDING"


@dataclass
class RewardCheck:
    type: RewardType
    score: float          # 0.0 or 1.0 for binary checks; 0.0-1.0 for QUALITY
    weight: float
    detail: str = ""
    error: Optional[str] = None

    def is_binary(self) -> bool:
        return self.type not in (RewardType.QUALITY, RewardType.RAG_GROUNDING)


@dataclass
class VariantReward:
    variant_number: int
    checks: list[RewardCheck] = field(default_factory=list)
    # Populated by compute()
    total_reward: float = 0.0
    binary_reward: float = 0.0
    passed_all_binary: bool = False
    # Populated by compute_group_advantages()
    advantage: float = 0.0

    def compute(self) -> None:
        """Compute total_reward, binary_reward, and passed_all_binary from checks."""
        if not self.checks:
            return

        total_weight = sum(c.weight for c in self.checks)
        if total_weight == 0:
            return

        self.total_reward = sum(c.score * c.weight for c in self.checks) / total_weight

        binary_checks = [c for c in self.checks if c.is_binary()]
        if binary_checks:
            binary_weight = sum(c.weight for c in binary_checks)
            self.binary_reward = sum(c.score * c.weight for c in binary_checks) / binary_weight
            self.passed_all_binary = all(c.score >= 1.0 for c in binary_checks)


# Per-task-type weights for each reward type.
# Binary checks (FORMAT, FUNCTIONAL, SOLVABILITY, NON_TRIVIALITY) act as gates.
# QUALITY is the LLM-as-judge score applied on top for ranking.
REWARD_WEIGHTS: dict[str, dict[RewardType, float]] = {
    "crypto_text_web": {
        RewardType.FORMAT: 1.0,
        RewardType.FUNCTIONAL: 1.5,
        RewardType.SOLVABILITY: 2.0,
        RewardType.NON_TRIVIALITY: 1.5,
        RewardType.QUALITY: 2.0,
        RewardType.RAG_GROUNDING: 1.5,
    },
    "forensics_image_metadata": {
        RewardType.FORMAT: 1.0,
        RewardType.FUNCTIONAL: 2.0,
        RewardType.SOLVABILITY: 2.0,
        RewardType.NON_TRIVIALITY: 1.0,
        RewardType.QUALITY: 2.0,
        RewardType.RAG_GROUNDING: 1.5,
    },
    "web_static_xss": {
        RewardType.FORMAT: 1.0,
        RewardType.FUNCTIONAL: 1.5,
        RewardType.SOLVABILITY: 2.0,
        RewardType.NON_TRIVIALITY: 1.5,
        RewardType.QUALITY: 2.0,
        RewardType.RAG_GROUNDING: 1.5,
    },
    "chat_llm": {
        RewardType.FORMAT: 1.0,
        RewardType.FUNCTIONAL: 1.5,
        RewardType.SOLVABILITY: 2.0,
        RewardType.NON_TRIVIALITY: 2.0,
        RewardType.QUALITY: 2.0,
        RewardType.RAG_GROUNDING: 1.5,
    },
}


def compute_group_advantages(rewards: list[VariantReward]) -> list[VariantReward]:
    """
    Compute GRPO group-relative advantage scores in-place.

    advantage_i = (reward_i - mean) / std

    Falls back to 0.0 advantage for all if std is 0 (all same reward).
    """
    if not rewards:
        return rewards

    scores = [r.total_reward for r in rewards]
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std = math.sqrt(variance)

    for r in rewards:
        if std > 1e-9:
            r.advantage = (r.total_reward - mean) / std
        else:
            r.advantage = 0.0

    return rewards
