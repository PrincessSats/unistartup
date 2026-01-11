from pydantic import BaseModel, EmailStr, Field
from typing import Optional
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