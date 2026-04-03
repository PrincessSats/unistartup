from pydantic import BaseModel, EmailStr, Field
from typing import Literal, Optional
from datetime import datetime

class UserRegister(BaseModel):
    """
    Данные для регистрации.
    Что пользователь отправляет в форме регистрации.
    """
    email: EmailStr  # Автоматически проверит, что это валидный email
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)  # Минимум 8 символов

class UserLogin(BaseModel):
    """
    Данные для входа.
    """
    email: EmailStr
    password: str

class Token(BaseModel):
    """
    JWT токен, который мы отдаем после входа.
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    session_expires_at: datetime


class AuthMessage(BaseModel):
    message: str

class UserResponse(BaseModel):
    """
    Данные пользователя, которые мы отдаем клиенту.
    (без пароля!)
    """
    id: int
    email: str
    username: str
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True  # Позволяет создавать из SQLAlchemy моделей


class EmailRegistrationStartRequest(BaseModel):
    email: EmailStr
    terms_accepted: bool
    marketing_opt_in: bool = False


class EmailRegistrationActionResponse(BaseModel):
    message: str
    flow_token: str
    email: str


class EmailRegistrationResendRequest(BaseModel):
    flow_token: str


class FlowEmailAttachRequest(BaseModel):
    flow_token: str
    email: EmailStr
    terms_accepted: bool
    marketing_opt_in: bool = False


class RegistrationFlowResponse(BaseModel):
    flow_token: str
    source: Literal["email_magic_link", "yandex", "github", "telegram"]
    intent: str
    email: Optional[str] = None
    email_verified: bool
    step: Literal["email", "email_sent", "details"]
    provider: Optional[str] = None
    username_suggestion: Optional[str] = None
    terms_accepted: bool
    marketing_opt_in: bool = False


class RegistrationCompleteRequest(BaseModel):
    flow_token: str
    username: str = Field(..., min_length=3, max_length=50)
    password: Optional[str] = Field(default=None, min_length=8)
    profession_tags: list[str] = Field(default_factory=list)
    grade: str
    interest_tags: list[str] = Field(default_factory=list)


class OAuthLoginFinalizeRequest(BaseModel):
    flow_token: str


class ForgotPasswordRequest(BaseModel):
    """
    Request for password reset link.
    """
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """
    Request to reset password using a reset token.
    """
    token: str
    new_password: str


class MessageResponse(BaseModel):
    """
    Generic message response.
    """
    message: str
