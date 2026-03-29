import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, Float, Text, Boolean, ForeignKey, Date
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB, UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AIGenerationBatch(Base):
    """Один запрос на генерацию = один батч из N вариантов."""
    __tablename__ = "ai_generation_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requested_by = Column(Integer, ForeignKey("users.id"))
    task_type = Column(Text, nullable=False)
    difficulty = Column(Text, nullable=False)
    num_variants = Column(Integer, nullable=False, default=5)
    attempt = Column(Integer, nullable=False, default=1)
    status = Column(Text, nullable=False, default="pending")
    current_stage = Column(Text, default="pending")
    stage_started_at = Column(TIMESTAMP(timezone=True))
    stage_meta = Column(JSONB)
    # GRPO group stats
    group_mean_reward = Column(Float)
    group_std_reward = Column(Float)
    pass_rate = Column(Float)
    # Result
    selected_variant_id = Column(UUID(as_uuid=True))
    failure_reasons_summary = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(TIMESTAMP(timezone=True))
    # RAG context
    rag_context_ids = Column(ARRAY(Integer))
    rag_context_summary = Column(Text)
    rag_query_text = Column(Text)

    variants = relationship("AIGenerationVariant", back_populates="batch", cascade="all, delete-orphan")


class AIGenerationVariant(Base):
    """Один вариант внутри батча. Хранятся все варианты, включая проигравшие."""
    __tablename__ = "ai_generation_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("ai_generation_batches.id", ondelete="CASCADE"), nullable=False)
    variant_number = Column(Integer, nullable=False)
    # Generation params
    model_used = Column(Text)
    temperature = Column(Float)
    tokens_input = Column(Integer)
    tokens_output = Column(Integer)
    generation_time_ms = Column(Integer)
    # LLM output
    generated_spec = Column(JSONB)
    # Artifact result
    artifact_result = Column(JSONB)
    # Reward scoring (GRPO core)
    reward_checks = Column(JSONB)
    reward_total = Column(Float)
    reward_binary = Column(Float)
    passed_all_binary = Column(Boolean, default=False)
    # LLM quality assessment (only if passed binary)
    quality_score = Column(Float)
    quality_details = Column(JSONB)
    # GRPO group-relative
    advantage = Column(Float)
    rank_in_group = Column(Integer)
    # Selection
    is_selected = Column(Boolean, default=False)
    published_task_id = Column(Integer, ForeignKey("tasks.id"))
    # Failure tracking
    failure_reason = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    # Embedding of generated spec (title + description) for feedback similarity search
    embedding = Column(Vector(256), nullable=True)

    batch = relationship("AIGenerationBatch", back_populates="variants")
    user_variant_request = relationship("UserTaskVariantRequest", back_populates="generated_variant", uselist=False)
    user_votes = relationship("UserTaskVariantVote", back_populates="variant", cascade="all, delete-orphan")


class AIGenerationAnalytics(Base):
    """Агрегированная аналитика для feedback loop."""
    __tablename__ = "ai_generation_analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(Text, nullable=False)
    difficulty = Column(Text, nullable=False)
    period_date = Column(Date, nullable=False)
    total_variants = Column(Integer, default=0)
    passed_variants = Column(Integer, default=0)
    avg_reward = Column(Float)
    avg_quality_score = Column(Float)
    common_failures = Column(JSONB)
    best_temperature = Column(Float)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class AIBaseImage(Base):
    """Пул базовых изображений для forensics задач."""
    __tablename__ = "ai_base_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(Text, nullable=False)
    s3_key = Column(Text, nullable=False)
    format = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)


class AIXSSTemplate(Base):
    """Параметризованные шаблоны HTML-страниц для XSS задач."""
    __tablename__ = "ai_xss_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    difficulty = Column(Text, nullable=False)
    xss_type = Column(Text, nullable=False)
    html_template = Column(Text, nullable=False)
    payload_example = Column(Text)
    is_active = Column(Boolean, default=True)
