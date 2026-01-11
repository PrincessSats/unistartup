import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
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

def create_access_token(data: dict) -> str:
    """
    Создает JWT токен.
    
    data - это обычно {"sub": "user_email"}
    sub (subject) - для кого токен
    """
    to_encode = data.copy()
    
    # Токен будет действителен 30 минут
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    # Шифруем данные секретным ключом
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

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