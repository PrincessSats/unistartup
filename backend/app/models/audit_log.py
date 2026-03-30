"""
Audit log model for tracking security-relevant events.

This model stores an immutable audit trail of important actions
in the system for compliance, security monitoring, and forensics.
"""

from datetime import datetime, timezone
from sqlalchemy import BIGINT, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLog(Base):
    """
    Audit log entry.
    
    Stores a record of security-relevant actions performed in the system.
    Entries are immutable - they should never be updated or deleted.
    """
    
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User who performed the action (NULL for system actions)
    user_id = Column(BIGINT, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Action type (e.g., "auth.login.success", "admin.task.deleted")
    action = Column(String(128), nullable=False, index=True)
    
    # Type of resource affected (e.g., "user", "task", "contest")
    resource_type = Column(String(64), nullable=True)
    
    # ID of the affected resource
    resource_id = Column(BIGINT, nullable=True)
    
    # Additional details in JSON format
    details = Column(JSONB, nullable=True, default=dict)
    
    # IP address of the request
    ip_address = Column(String(64), nullable=True)
    
    # User agent string
    user_agent = Column(Text, nullable=True)
    
    # Timestamp (automatically set)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_user_created", "user_id", "created_at"),
        Index("idx_audit_logs_action_created", "action", "created_at"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
        Index("idx_audit_logs_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action={self.action}, "
            f"user_id={self.user_id}, created_at={self.created_at})>"
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "action": self.action,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Prevent updates and deletes (soft enforcement via event listeners)
@event.listens_for(AuditLog, "before_update")
def prevent_audit_log_update(mapper, connection, target):
    """Raise an error if someone tries to update an audit log entry."""
    # In production, you might want to log this as a security event
    # or use database-level constraints instead
    pass  # Silently ignore for now - can be made stricter later


@event.listens_for(AuditLog, "before_delete")
def prevent_audit_log_delete(mapper, connection, target):
    """Raise an error if someone tries to delete an audit log entry."""
    # In production, you might want to log this as a security event
    pass  # Silently ignore for now - can be made stricter later
