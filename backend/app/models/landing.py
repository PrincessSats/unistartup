from sqlalchemy import Column, BigInteger, Integer, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.database import Base


class LandingHuntSession(Base):
    __tablename__ = "landing_hunt_sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_token = Column(Text, nullable=False, unique=True, index=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    items = relationship(
        "LandingHuntSessionItem",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    promo_code = relationship("PromoCode", back_populates="hunt_session", uselist=False)


class LandingHuntSessionItem(Base):
    __tablename__ = "landing_hunt_session_items"

    session_id = Column(
        BigInteger,
        ForeignKey("landing_hunt_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    bug_key = Column(Text, primary_key=True)
    found_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    session = relationship("LandingHuntSession", back_populates="items")


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(Text, nullable=False, unique=True, index=True)
    source = Column(Text, nullable=False)
    reward_points = Column(Integer, nullable=False, default=0)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    issued_hunt_session_id = Column(
        BigInteger,
        ForeignKey("landing_hunt_sessions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    redeemed_by_user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    redeemed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    hunt_session = relationship("LandingHuntSession", back_populates="promo_code")

