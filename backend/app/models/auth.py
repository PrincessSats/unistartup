from sqlalchemy import Column, BigInteger, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class PasswordResetToken(Base):
    """
    Токены для сброса пароля.
    Хранит хеш токена и время истечения.
    """
    __tablename__ = "auth_password_reset_tokens"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(Text, nullable=False, unique=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    used_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationship to User
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("idx_password_reset_tokens_user_id", user_id),
        Index("idx_password_reset_tokens_expires_at", expires_at),
    )
