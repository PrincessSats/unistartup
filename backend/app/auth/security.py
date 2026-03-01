import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from typing import Optional
from app.config import settings

def hash_password(password: str) -> str:
    """
    Хеширует пароль.
    Мы НИКОГДА не храним пароли в открытом виде!
    """
    return bcrypt.hashpw(
        password.encode('utf-8'), 
        bcrypt.gensalt()
    ).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет, совпадает ли введенный пароль с хешем в БД.
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def build_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> tuple[str, datetime]:
    """
    Создает JWT токен.
    
    data - это обычно {"sub": "user_email"}
    sub (subject) - для кого токен
    """
    to_encode = data.copy()
    
    # Короткоживущий access token, долгоживущая сессия строится через refresh token.
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    
    # Шифруем данные секретным ключом
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt, expire


def create_access_token(data: dict) -> str:
    token, _ = build_access_token(data=data)
    return token


def generate_refresh_token() -> str:
    """
    Генерирует криптографически стойкий opaque refresh token.
    """
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """
    Для хранения refresh token в БД сохраняем только SHA-256 hash.
    """
    value = str(token or "").strip()
    return sha256(value.encode("utf-8")).hexdigest()

def decode_access_token(token: str) -> dict:
    """
    Расшифровывает JWT токен.
    Возвращает данные или None если токен невалидный.
    """
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None
