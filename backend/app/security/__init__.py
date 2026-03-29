"""Security utilities."""

from app.security.input_sanitization import (
    sanitize_html,
    strip_html_tags,
    escape_html,
    detect_xss_attempt,
    sanitize_username,
    sanitize_email,
    sanitize_comment,
    sanitize_feedback_message,
    sanitize_topic,
    validate_sql_sort_order,
)

from app.security.security_headers import security_headers_middleware

from app.security.audit_logger import (
    log_audit_event,
    log_auth_event,
    log_admin_action,
    log_security_event,
    get_audit_logs_for_user,
    get_audit_logs_by_action,
    AuditAction,
)

__all__ = [
    # Input sanitization
    "sanitize_html",
    "strip_html_tags",
    "escape_html",
    "detect_xss_attempt",
    "sanitize_username",
    "sanitize_email",
    "sanitize_comment",
    "sanitize_feedback_message",
    "sanitize_topic",
    "validate_sql_sort_order",
    
    # Security headers
    "security_headers_middleware",
    
    # Audit logging
    "log_audit_event",
    "log_auth_event",
    "log_admin_action",
    "log_security_event",
    "get_audit_logs_for_user",
    "get_audit_logs_by_action",
    "AuditAction",
]

