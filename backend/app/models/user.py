from sqlalchemy import Column, BigInteger, Integer, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMP, ARRAY, JSONB
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
    auth_identities = relationship("UserAuthIdentity", back_populates="user", cascade="all, delete-orphan")
    registration_data = relationship("UserRegistrationData", back_populates="user", uselist=False, cascade="all, delete-orphan")

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
    onboarding_status = Column(Text, nullable=True)  # NULL | pending | dismissed | completed
    
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


class UserAuthIdentity(Base):
    """
    Привязки внешних OAuth-провайдеров к локальному пользователю.
    """
    __tablename__ = "user_auth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_user_auth_identities_provider_subject"),
        UniqueConstraint("user_id", "provider", name="uq_user_auth_identities_user_provider"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(Text, nullable=False)
    provider_user_id = Column(Text, nullable=False)
    provider_email = Column(Text, nullable=True)
    provider_login = Column(Text, nullable=True)
    provider_avatar_url = Column(Text, nullable=True)
    raw_profile_json = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)

    user = relationship("User", back_populates="auth_identities")


class AuthRegistrationFlow(Base):
    """
    Черновики регистрации для email magic-link и OAuth continuation.
    """
    __tablename__ = "auth_registration_flows"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    intent = Column(Text, nullable=False, default="register")
    source = Column(Text, nullable=False)
    email = Column(Text, nullable=True, index=True)
    email_verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    terms_accepted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    marketing_opt_in = Column(Boolean, nullable=False, default=False)
    marketing_opt_in_at = Column(TIMESTAMP(timezone=True), nullable=True)
    provider = Column(Text, nullable=True)
    provider_user_id = Column(Text, nullable=True)
    provider_email = Column(Text, nullable=True)
    provider_login = Column(Text, nullable=True)
    provider_avatar_url = Column(Text, nullable=True)
    provider_raw_profile_json = Column(JSONB, nullable=True)
    oauth_state_hash = Column(Text, nullable=True, unique=True, index=True)
    oauth_code_verifier = Column(Text, nullable=True)
    magic_link_token_hash = Column(Text, nullable=True, unique=True, index=True)
    magic_link_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    magic_link_sent_count = Column(Integer, nullable=False, default=0)
    last_magic_link_sent_at = Column(TIMESTAMP(timezone=True), nullable=True)
    magic_link_consumed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    completed_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    consumed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class UserRegistrationData(Base):
    """
    Ответы анкеты и источник регистрации.
    """
    __tablename__ = "user_registration_data"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    registration_source = Column(Text, nullable=False)
    terms_accepted_at = Column(TIMESTAMP(timezone=True), nullable=False)
    marketing_opt_in = Column(Boolean, nullable=False, default=False)
    marketing_opt_in_at = Column(TIMESTAMP(timezone=True), nullable=True)
    profession_tags = Column(ARRAY(Text), nullable=False, default=list)
    grade = Column(Text, nullable=True)
    interest_tags = Column(ARRAY(Text), nullable=False, default=list)
    questionnaire_completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="registration_data")
