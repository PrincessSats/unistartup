"""
Сервис аудит-логирования для отслеживания событий безопасности.

Логирует важные действия:
- События аутентификации (вход, выход, неудачные попытки)
- Действия администратора (управление пользователями, изменение контента)
- События безопасности (смена пароля, удаление аккаунта)
- Доступ к данным (экспорт чувствительных данных)

Все записи аудита неизменны и хранятся для соответствия требованиям.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Стандартизированные типы действий для аудита."""

    # Аутентификация
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILED = "auth.login.failed"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REFRESH_TOKEN = "auth.refresh_token"
    AUTH_PASSWORD_CHANGED = "auth.password_changed"
    AUTH_EMAIL_CHANGED = "auth.email_changed"
    
    # Управление аккаунтом
    ACCOUNT_CREATED = "account.created"
    ACCOUNT_DELETED = "account.deleted"
    ACCOUNT_UPDATED = "account.updated"
    PROFILE_UPDATED = "profile.updated"
    
    # Действия администратора
    ADMIN_USER_CREATED = "admin.user.created"
    ADMIN_USER_DELETED = "admin.user.deleted"
    ADMIN_USER_BANNED = "admin.user.banned"
    ADMIN_TASK_CREATED = "admin.task.created"
    ADMIN_TASK_UPDATED = "admin.task.updated"
    ADMIN_TASK_DELETED = "admin.task.deleted"
    ADMIN_CONTEST_CREATED = "admin.contest.created"
    ADMIN_CONTEST_UPDATED = "admin.contest.updated"
    ADMIN_CONTEST_DELETED = "admin.contest.deleted"
    ADMIN_KB_ENTRY_CREATED = "admin.kb_entry.created"
    ADMIN_KB_ENTRY_UPDATED = "admin.kb_entry.updated"
    ADMIN_KB_ENTRY_DELETED = "admin.kb_entry.deleted"
    ADMIN_PROMPT_UPDATED = "admin.prompt.updated"
    
    # События безопасности
    SECURITY_RATE_LIMIT_EXCEEDED = "security.rate_limit_exceeded"
    SECURITY_XSS_ATTEMPT = "security.xss_attempt"
    SECURITY_SQL_INJECTION_ATTEMPT = "security.sql_injection_attempt"
    SECURITY_PROMPT_INJECTION_ATTEMPT = "security.prompt_injection_attempt"
    
    # Доступ к данным
    DATA_EXPORT_REQUESTED = "data.export_requested"
    DATA_ACCESS_SENSITIVE = "data.access_sensitive"


async def log_audit_event(
    db: AsyncSession,
    action: AuditAction,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    Записывает событие аудита в базу данных.

    Args:
        db: Сессия базы данных
        action: Тип логируемого действия
        user_id: ID пользователя, выполнившего действие
        resource_type: Тип затронутого ресурса (например, 'user', 'task')
        resource_id: ID затронутого ресурса
        details: Дополнительные JSON-сериализуемые детали
        ip_address: IP-адрес запроса
        user_agent: User-agent строка запроса
    """
    try:
        # Импортируем здесь, чтобы избежать циклических импортов
        from app.models.audit_log import AuditLog
        
        audit_entry = AuditLog(
            user_id=user_id,
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent[:1024] if user_agent else None,  # Обрезаем слишком длинный user-agent
        )
        
        db.add(audit_entry)
        # Не коммитим здесь - пусть коммитит вызывающий код
        # Это позволяет логированию аудита быть частью большей транзакции

    except Exception as e:
        # Никогда не позволяйте сбоям логирования аудита нарушить основной поток
        logger.error("Failed to log audit event: action=%s, error=%s", action.value, e)
        # Не откатываем здесь - пусть решает вызывающий код


async def log_auth_event(
    db: AsyncSession,
    action: AuditAction,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Вспомогательная функция для логирования событий аутентификации."""
    await log_audit_event(
        db=db,
        action=action,
        user_id=user_id,
        resource_type="auth",
        resource_id=None,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def log_admin_action(
    db: AsyncSession,
    action: AuditAction,
    user_id: int,
    resource_type: str,
    resource_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Вспомогательная функция для логирования действий администратора."""
    await log_audit_event(
        db=db,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def log_security_event(
    db: AsyncSession,
    action: AuditAction,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Вспомогательная функция для логирования событий безопасности."""
    await log_audit_event(
        db=db,
        action=action,
        user_id=user_id,
        resource_type="security",
        resource_id=None,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def get_audit_logs_for_user(
    db: AsyncSession,
    user_id: int,
    limit: int = 100,
    offset: int = 0,
) -> list:
    """
    Получает записи аудита для конкретного пользователя.

    Args:
        db: Сессия базы данных
        user_id: ID пользователя
        limit: Максимальное количество записей
        offset: Сколько записей пропустить

    Returns:
        Список записей аудита
    """
    try:
        from app.models.audit_log import AuditLog
        
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        return result.scalars().all()
    
    except Exception as e:
        logger.error("Failed to fetch audit logs: user_id=%s, error=%s", user_id, e)
        return []


async def get_audit_logs_by_action(
    db: AsyncSession,
    action: AuditAction,
    limit: int = 100,
) -> list:
    """
    Получает записи аудита для конкретного типа действия.

    Полезно для мониторинга безопасности и реагирования на инциденты.

    Args:
        db: Сессия базы данных
        action: Тип действия для фильтрации
        limit: Максимальное количество записей

    Returns:
        Список записей аудита
    """
    try:
        from app.models.audit_log import AuditLog
        
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.action == action.value)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        
        return result.scalars().all()
    
    except Exception as e:
        logger.error("Failed to fetch audit logs by action: action=%s, error=%s", action.value, e)
        return []
