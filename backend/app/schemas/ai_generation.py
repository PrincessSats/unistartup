from typing import Literal, Optional

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    task_type: Literal["forensics_image_metadata", "crypto_text_web", "web_static_xss", "chat_llm"]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    num_variants: int = Field(default=5, ge=3, le=7)
    cve_id: Optional[str] = None
    topic: Optional[str] = None


class GenerateResponse(BaseModel):
    batch_id: str
    status: str  # "generating"
    rag_context_used: int = 0


class RewardCheckSchema(BaseModel):
    type: str
    score: float
    weight: float
    detail: str
    error: Optional[str] = None


class VariantSchema(BaseModel):
    id: str
    variant_number: int
    reward_total: Optional[float] = None
    reward_binary: Optional[float] = None
    advantage: Optional[float] = None
    rank_in_group: Optional[int] = None
    passed_all_binary: bool = False
    quality_score: Optional[float] = None
    failure_reason: Optional[str] = None
    reward_checks: Optional[list[RewardCheckSchema]] = None
    # generated_spec intentionally excluded — contains flag


class BatchStatusResponse(BaseModel):
    batch_id: str
    status: str
    task_type: str
    difficulty: str
    attempt: int
    group_mean_reward: Optional[float] = None
    group_std_reward: Optional[float] = None
    pass_rate: Optional[float] = None
    variants: list[VariantSchema] = Field(default_factory=list)
    selected_variant_id: Optional[str] = None
    rag_context_ids: Optional[list[int]] = None
    rag_query_text: Optional[str] = None


class AnalyticsResponse(BaseModel):
    task_type: str
    difficulty: str
    total_variants: int
    passed_variants: int
    pass_rate: float
    avg_quality_score: Optional[float] = None
    common_failures: list[dict] = Field(default_factory=list)
    best_temperature: Optional[float] = None
