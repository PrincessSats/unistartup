"""
Сервис логирования активности контестов.

Утилиты для записи действий админов, сабмитов и событий участников.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityLog, EventType, EventSource

logger = logging.getLogger(__name__)


async def log_activity(
    db: AsyncSession,
    event_type: EventType,
    action: str,
    admin_id: Optional[int] = None,
    contest_id: Optional[int] = None,
    source: EventSource = EventSource.ADMIN_ACTION,
    details: Optional[Dict[str, Any]] = None,
) -> ActivityLog:
    """
    Записывает событие в таблицу activity_log.

    Args:
        db: Сессия базы данных
        event_type: Тип события (из enum EventType)
        action: Читаемое описание (например, "Created contest 'HackNet Summer'")
        admin_id: ID админа, выполнившего действие (опционально)
        contest_id: ID связанного контеста (опционально)
        source: Источник события (по умолчанию: ADMIN_ACTION)
        details: Дополнительные данные в JSON (опционально)

    Returns:
        Созданный экземпляр ActivityLog
    """
    try:
        log_entry = ActivityLog(
            admin_id=admin_id,
            contest_id=contest_id,
            event_type=event_type,
            source=source,
            action=action,
            details=details or {},
            created_at=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        await db.flush()  # Flush для получения ID, без коммита
        logger.debug(f"Logged activity: {event_type.value} - {action}")
        return log_entry
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")
        # Не пробрасываем исключение — логирование не должно ломать основной флоу
        return None


async def log_contest_created(
    db: AsyncSession,
    admin_id: int,
    contest_id: int,
    contest_title: str,
    details: Optional[Dict[str, Any]] = None,
) -> ActivityLog:
    """Логирует создание контеста."""
    action = f"Created contest '{contest_title}'"
    return await log_activity(
        db=db,
        event_type=EventType.CONTEST_CREATED,
        action=action,
        admin_id=admin_id,
        contest_id=contest_id,
        details=details,
    )


async def log_contest_updated(
    db: AsyncSession,
    admin_id: int,
    contest_id: int,
    contest_title: str,
    details: Optional[Dict[str, Any]] = None,
) -> ActivityLog:
    """Логирует обновление контеста."""
    action = f"Updated contest '{contest_title}'"
    return await log_activity(
        db=db,
        event_type=EventType.CONTEST_UPDATED,
        action=action,
        admin_id=admin_id,
        contest_id=contest_id,
        details=details,
    )


async def log_contest_deleted(
    db: AsyncSession,
    admin_id: int,
    contest_id: int,
    contest_title: str,
) -> ActivityLog:
    """Логирует удаление контеста."""
    action = f"Deleted contest '{contest_title}'"
    return await log_activity(
        db=db,
        event_type=EventType.CONTEST_DELETED,
        action=action,
        admin_id=admin_id,
        contest_id=contest_id,
    )


async def log_contest_ended(
    db: AsyncSession,
    admin_id: int,
    contest_id: int,
    contest_title: str,
) -> ActivityLog:
    """Логирует завершение контеста."""
    action = f"Ended contest '{contest_title}'"
    return await log_activity(
        db=db,
        event_type=EventType.CONTEST_ENDED,
        action=action,
        admin_id=admin_id,
        contest_id=contest_id,
    )


async def log_task_added(
    db: AsyncSession,
    admin_id: int,
    contest_id: int,
    task_id: int,
    task_title: str,
    details: Optional[Dict[str, Any]] = None,
) -> ActivityLog:
    """Логирует добавление задачи в контест."""
    action = f"Added task '{task_title}' to contest"
    return await log_activity(
        db=db,
        event_type=EventType.TASK_ADDED,
        action=action,
        admin_id=admin_id,
        contest_id=contest_id,
        details=details,
    )


async def log_task_removed(
    db: AsyncSession,
    admin_id: int,
    contest_id: int,
    task_id: int,
    task_title: str,
) -> ActivityLog:
    """Логирует удаление задачи из контеста."""
    action = f"Removed task '{task_title}' from contest"
    return await log_activity(
        db=db,
        event_type=EventType.TASK_REMOVED,
        action=action,
        admin_id=admin_id,
        contest_id=contest_id,
    )


async def log_submission(
    db: AsyncSession,
    contest_id: int,
    task_id: int,
    user_id: int,
    username: str,
    is_correct: bool,
    details: Optional[Dict[str, Any]] = None,
) -> ActivityLog:
    """Логирует попытку отправки флага."""
    event_type = EventType.SUBMISSION_CORRECT if is_correct else EventType.SUBMISSION_RECEIVED
    action = f"Flag submission by {username} - {'Correct' if is_correct else 'Received'}"
    return await log_activity(
        db=db,
        event_type=event_type,
        action=action,
        contest_id=contest_id,
        source=EventSource.PARTICIPANT_ACTION,
        details=details,
    )


async def log_participant_joined(
    db: AsyncSession,
    contest_id: int,
    user_id: int,
    username: str,
) -> ActivityLog:
    """Логирует вступление участника в контест."""
    action = f"Participant {username} joined contest"
    return await log_activity(
        db=db,
        event_type=EventType.PARTICIPANT_JOINED,
        action=action,
        contest_id=contest_id,
        source=EventSource.PARTICIPANT_ACTION,
        details={"user_id": user_id, "username": username},
    )
