"""
Audit logging service for tracking security-relevant events.

Logs important actions like:
- Authentication events (login, logout, failed attempts)
- Admin actions (user management, content changes)
- Security events (password changes, account deletion)
- Data access (sensitive data exports)

All audit logs are immutable and retained for compliance.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Standardized audit action types."""
    
    # Authentication
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILED = "auth.login.failed"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REFRESH_TOKEN = "auth.refresh_token"
    AUTH_PASSWORD_CHANGED = "auth.password_changed"
    AUTH_EMAIL_CHANGED = "auth.email_changed"
    
    # Account management
    ACCOUNT_CREATED = "account.created"
    ACCOUNT_DELETED = "account.deleted"
    ACCOUNT_UPDATED = "account.updated"
    PROFILE_UPDATED = "profile.updated"
    
    # Admin actions
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
    
    # Security events
    SECURITY_RATE_LIMIT_EXCEEDED = "security.rate_limit_exceeded"
    SECURITY_XSS_ATTEMPT = "security.xss_attempt"
    SECURITY_SQL_INJECTION_ATTEMPT = "security.sql_injection_attempt"
    SECURITY_PROMPT_INJECTION_ATTEMPT = "security.prompt_injection_attempt"
    
    # Data access
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
    Log an audit event to the database.
    
    Args:
        db: Database session
        action: Type of action being logged
        user_id: ID of the user who performed the action
        resource_type: Type of resource affected (e.g., 'user', 'task')
        resource_id: ID of the resource affected
        details: Additional JSON-serializable details
        ip_address: IP address of the request
        user_agent: User agent string of the request
    """
    try:
        # Import here to avoid circular imports
        from app.models.audit_log import AuditLog
        
        audit_entry = AuditLog(
            user_id=user_id,
            action=action.value,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent[:1024] if user_agent else None,  # Truncate long user agents
        )
        
        db.add(audit_entry)
        # Don't commit here - let the caller commit
        # This allows audit logging to be part of a larger transaction
        
    except Exception as e:
        # Never let audit logging failures break the main flow
        logger.error("Failed to log audit event: action=%s, error=%s", action.value, e)
        # Don't rollback here - let the caller decide


async def log_auth_event(
    db: AsyncSession,
    action: AuditAction,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Helper to log authentication-related events."""
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
    """Helper to log admin actions."""
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
    """Helper to log security events."""
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
    Retrieve audit logs for a specific user.
    
    Args:
        db: Database session
        user_id: User ID to fetch logs for
        limit: Maximum number of logs to return
        offset: Number of logs to skip
    
    Returns:
        List of audit log entries
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
    Retrieve audit logs for a specific action type.
    
    Useful for security monitoring and incident response.
    
    Args:
        db: Database session
        action: Action type to filter by
        limit: Maximum number of logs to return
    
    Returns:
        List of audit log entries
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
