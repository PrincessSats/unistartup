"""
Система вознаграждения GRPO для автоматически генерируемых CTF-вызовов.

RewardType     — перечисление 5 категорий проверок
RewardCheck    — результат одной проверки одного варианта
VariantReward  — совокупное вознаграждение для одного варианта
REWARD_WEIGHTS — конфигурация веса для каждого типа задачи
compute_group_advantages — баллы группоабсолютного преимущества GRPO
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
    CVE_RELEVANCE = "CVE_RELEVANCE"


@dataclass
class RewardCheck:
    type: RewardType
    score: float          # 0.0 or 1.0 for binary checks; 0.0-1.0 for QUALITY
    weight: float
    detail: str = ""
    error: Optional[str] = None

    def is_binary(self) -> bool:
        return self.type not in (RewardType.QUALITY, RewardType.RAG_GROUNDING, RewardType.CVE_RELEVANCE)


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


# Веса для каждого типа вознаграждения на каждый тип задачи.
# Двоичные проверки (FORMAT, FUNCTIONAL, SOLVABILITY, NON_TRIVIALITY) выступают как ворота.
# QUALITY — это баллы LLM-as-judge, применяемые наверху для ранжирования.
REWARD_WEIGHTS: dict[str, dict[RewardType, float]] = {
    "crypto_text_web": {
        RewardType.FORMAT: 1.0,
        RewardType.FUNCTIONAL: 1.5,
        RewardType.SOLVABILITY: 2.0,
        RewardType.NON_TRIVIALITY: 1.5,
        RewardType.QUALITY: 2.0,
        RewardType.RAG_GROUNDING: 1.5,
        RewardType.CVE_RELEVANCE: 1.0,
    },
    "forensics_image_metadata": {
        RewardType.FORMAT: 1.0,
        RewardType.FUNCTIONAL: 2.0,
        RewardType.SOLVABILITY: 2.0,
        RewardType.NON_TRIVIALITY: 1.0,
        RewardType.QUALITY: 2.0,
        RewardType.RAG_GROUNDING: 1.5,
        RewardType.CVE_RELEVANCE: 1.0,
    },
    "web_static_xss": {
        RewardType.FORMAT: 1.0,
        RewardType.FUNCTIONAL: 1.5,
        RewardType.SOLVABILITY: 2.0,
        RewardType.NON_TRIVIALITY: 1.5,
        RewardType.QUALITY: 2.0,
        RewardType.RAG_GROUNDING: 1.5,
        RewardType.CVE_RELEVANCE: 1.0,
    },
    "chat_llm": {
        RewardType.FORMAT: 1.0,
        RewardType.FUNCTIONAL: 1.5,
        RewardType.SOLVABILITY: 2.0,
        RewardType.NON_TRIVIALITY: 2.0,
        RewardType.QUALITY: 2.0,
        RewardType.RAG_GROUNDING: 1.5,
        RewardType.CVE_RELEVANCE: 1.0,
    },
}


def compute_group_advantages(rewards: list[VariantReward]) -> list[VariantReward]:
    """
    Вычислить баллы группоабсолютного преимущества GRPO на месте.

    advantage_i = (reward_i - mean) / std

    Откатывается на преимущество 0.0 для всех, если std равен 0 (все одинаковые вознаграждения).
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
