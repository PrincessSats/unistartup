from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.database import get_db
from app.models.user import User, UserProfile, UserRating
from app.schemas.user import UserRegister, UserLogin, Token, UserResponse
from app.auth.security import hash_password, verify_password, create_access_token
from app.security.rate_limit import RateLimit, enforce_rate_limit

router = APIRouter(prefix="/auth", tags=["Авторизация"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация нового пользователя.
    
    Что делаем:
    1. Проверяем, не занят ли email
    2. Проверяем, не занят ли username
    3. Хешируем пароль
    4. Создаем User и UserProfile
    5. Сохраняем в БД
    """
    
    # Проверяем email
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email уже зарегистрирован"
        )
    
    # Проверяем username
    result = await db.execute(select(UserProfile).where(UserProfile.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username уже занят"
        )
    
    # Создаем пользователя
    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        is_active=True
    )
    db.add(new_user)
    await db.flush()  # Получаем ID пользователя
    
    # Создаем профиль
    new_profile = UserProfile(
        user_id=new_user.id,
        username=user_data.username,
        role="participant"  # По умолчанию обычный участник
    )
    db.add(new_profile)

    # Создаем стартовые рейтинги
    new_rating = UserRating(
        user_id=new_user.id
    )
    db.add(new_rating)
    await db.commit()
    await db.refresh(new_user)
    
    # Формируем ответ
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        username=new_profile.username,
        role=new_profile.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at
    )

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Вход в систему.
    
    Что делаем:
    1. Ищем пользователя по email
    2. Проверяем пароль
    3. Создаем JWT токен
    4. Отдаем токен клиенту
    """
    
    enforce_rate_limit(
        request,
        scope="auth_login_ip",
        subject="any",
        rule=RateLimit(max_requests=20, window_seconds=60),
    )
    enforce_rate_limit(
        request,
        scope="auth_login_account",
        subject=user_data.email.lower(),
        rule=RateLimit(max_requests=8, window_seconds=300),
    )

    # Ищем пользователя
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    user = result.scalar_one_or_none()
    
    # Проверяем существование и пароль
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )
    
    # Проверяем, активен ли аккаунт
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован"
        )
    
    # Создаем токен
    access_token = create_access_token(data={"sub": user.email})

    # Обновляем время последнего входа (используем лёгкое обновление без загрузки профиля)
    await db.execute(
        update(UserProfile)
        .where(UserProfile.user_id == user.id)
        .values(last_login=func.now())
    )
    await db.commit()
    
    return Token(access_token=access_token, token_type="bearer")
