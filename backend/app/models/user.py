from sqlalchemy import Column, BigInteger, Integer, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    """
    Таблица пользователей (авторизация).
    Хранит email и хеш пароля.
    """
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    email_verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Связь с профилем (один к одному)
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    rating = relationship("UserRating", back_populates="user", uselist=False, cascade="all, delete-orphan")
    refresh_tokens = relationship("AuthRefreshToken", back_populates="user")

class UserProfile(Base):
    """
    Профиль пользователя.
    Хранит username, роль (admin/participant), аватар и т.д.
    """
    __tablename__ = "user_profiles"
    
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    username = Column(Text, nullable=False, unique=True, index=True)
    role = Column(Text, nullable=False, default="participant")  # 'admin', 'author', 'participant'
    bio = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)
    locale = Column(Text, default="ru-RU")
    timezone = Column(Text, default="Europe/Moscow")
    last_login = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Связь с пользователем
    user = relationship("User", back_populates="profile")

class UserRating(Base):
    """
    Рейтинги пользователя (чемпионат и практика).
    """
    __tablename__ = "user_ratings"
    
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    contest_rating = Column(Integer, nullable=False, default=0)
    practice_rating = Column(Integer, nullable=False, default=0)
    first_blood = Column(Integer, nullable=False, default=0)
    last_updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    user = relationship("User", back_populates="rating")


class AuthRefreshToken(Base):
    """
    Ротационные refresh-токены (храним только хеш токена).
    """
    __tablename__ = "auth_refresh_tokens"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(Text, nullable=False, unique=True, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    revoked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    rotated_to_id = Column(
        BigInteger,
        ForeignKey("auth_refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(Text, nullable=True)

    user = relationship("User", back_populates="refresh_tokens")
    rotated_to = relationship("AuthRefreshToken", remote_side=[id], uselist=False)
