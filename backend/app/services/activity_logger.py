"""
Service for logging contest-related activities.

Provides utilities for recording admin actions, submissions, and participant events.
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
    Log an activity to the activity_log table.

    Args:
        db: Database session
        event_type: Type of event (from EventType enum)
        action: Human-readable description (e.g., "Created contest 'HackNet Summer'")
        admin_id: ID of admin who performed the action (optional)
        contest_id: ID of related contest (optional)
        source: Source of the event (default: ADMIN_ACTION)
        details: Additional JSON details (optional)

    Returns:
        The created ActivityLog instance
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
        await db.flush()  # Flush to get the ID, but don't commit yet
        logger.debug(f"Logged activity: {event_type.value} - {action}")
        return log_entry
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")
        # Don't raise - activity logging should not break the main action
        raise


async def log_contest_created(
    db: AsyncSession,
    admin_id: int,
    contest_id: int,
    contest_title: str,
    details: Optional[Dict[str, Any]] = None,
) -> ActivityLog:
    """Log contest creation."""
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
    """Log contest update."""
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
    """Log contest deletion."""
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
    """Log contest being ended."""
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
    """Log task being added to contest."""
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
    """Log task being removed from contest."""
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
    """Log a flag submission."""
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
    """Log participant joining contest."""
    action = f"Participant {username} joined contest"
    return await log_activity(
        db=db,
        event_type=EventType.PARTICIPANT_JOINED,
        action=action,
        contest_id=contest_id,
        source=EventSource.PARTICIPANT_ACTION,
        details={"user_id": user_id, "username": username},
    )
