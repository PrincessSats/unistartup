import uuid

from sqlalchemy import Column, BigInteger, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UserTaskVariantRequest(Base):
    """User request for task variant generation."""
    __tablename__ = "user_task_variant_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user_request = Column(Text, nullable=False)
    sanitized_request = Column(Text)  # After injection filtering
    status = Column(Text, nullable=False, default="pending")  # pending, generating, completed, failed
    generated_variant_id = Column(UUID(as_uuid=True), ForeignKey("ai_generation_variants.id"))
    failure_reason = Column(Text)
    rejection_reason = Column(Text)  # For injection detection failures
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(TIMESTAMP(timezone=True))

    parent_task = relationship("Task", back_populates="user_variant_requests")
    generated_variant = relationship("AIGenerationVariant", back_populates="user_variant_request")


class UserTaskVariantVote(Base):
    """Community votes on user-generated task variants."""
    __tablename__ = "user_task_variant_votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("ai_generation_variants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    vote_type = Column(Text, nullable=False)  # upvote, downvote
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("variant_id", "user_id", name="uq_variant_user_vote"),
    )

    variant = relationship("AIGenerationVariant", back_populates="user_votes")


# Add back-populates to existing models (imported where needed)
# Task.user_variant_requests
# AIGenerationVariant.user_variant_request
# AIGenerationVariant.user_votes
