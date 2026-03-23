from typing import Literal, Optional

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    # task_type is optional: if omitted and cve_id is provided, the pipeline
    # infers the best task type from CVE CWE data via cwe_mapping.infer_task_type().
    task_type: Optional[Literal["forensics_image_metadata", "crypto_text_web", "web_static_xss", "chat_llm"]] = None
    difficulty: Literal["beginner", "intermediate", "advanced"]
    num_variants: int = Field(default=5, ge=3, le=7)
    cve_id: Optional[str] = None
    topic: Optional[str] = None


class GenerateResponse(BaseModel):
    batch_id: str
    status: str  # "generating"
    task_type: Optional[str] = None  # resolved task type (useful when inferred from CVE)
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
    temperature: Optional[float] = None
    model_used: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    generation_time_ms: Optional[int] = None
    quality_details: Optional[dict] = None
    spec_title: Optional[str] = None
    spec_description: Optional[str] = None
    artifact_content: Optional[str] = None


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
    current_stage: Optional[str] = None
    stage_started_at: Optional[str] = None
    stage_meta: Optional[dict] = None
    created_at: Optional[str] = None
    num_variants: int = 5


class VariantReviewSchema(BaseModel):
    """Full variant detail for admin review — includes flag and verification_data."""
    id: str
    variant_number: int
    # Spec — full, including flag (admin only)
    spec_title: Optional[str] = None
    spec_description: Optional[str] = None
    spec_story: Optional[str] = None
    spec_flag: Optional[str] = None
    spec_hint: Optional[str] = None
    spec_category: Optional[str] = None
    spec_raw: Optional[dict] = None
    # Artifact
    artifact_content: Optional[str] = None
    artifact_file_url: Optional[str] = None
    artifact_verification: Optional[dict] = None
    artifact_error: Optional[str] = None
    # Generation stats
    temperature: Optional[float] = None
    model_used: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    generation_time_ms: Optional[int] = None
    # Rewards
    reward_total: Optional[float] = None
    reward_binary: Optional[float] = None
    quality_score: Optional[float] = None
    quality_details: Optional[dict] = None
    advantage: Optional[float] = None
    rank_in_group: Optional[int] = None
    passed_all_binary: bool = False
    failure_reason: Optional[str] = None
    reward_checks: Optional[list[RewardCheckSchema]] = None
    is_selected: bool = False
    published_task_id: Optional[int] = None


class AnalyticsResponse(BaseModel):
    task_type: str
    difficulty: str
    total_variants: int
    passed_variants: int
    pass_rate: float
    avg_quality_score: Optional[float] = None
    common_failures: list[dict] = Field(default_factory=list)
    best_temperature: Optional[float] = None
