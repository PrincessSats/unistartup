"""
Activity log model for tracking contest-related events.

Stores events like contest CRUD, task assignments, submissions, and participant actions.
Used for audit trail and admin activity feed.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    BIGINT,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    event,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class EventType(str, enum.Enum):
    """Types of events that can be logged."""
    # Contest CRUD
    CONTEST_CREATED = "contest_created"
    CONTEST_UPDATED = "contest_updated"
    CONTEST_DELETED = "contest_deleted"
    CONTEST_ENDED = "contest_ended"

    # Task assignments
    TASK_ADDED = "task_added"
    TASK_REMOVED = "task_removed"

    # Submissions
    SUBMISSION_RECEIVED = "submission_received"
    SUBMISSION_CORRECT = "submission_correct"
    SUBMISSION_INCORRECT = "submission_incorrect"

    # Participants
    PARTICIPANT_JOINED = "participant_joined"
    PARTICIPANT_LEFT = "participant_left"

    # Chat
    CHAT_MESSAGE = "chat_message"


class EventSource(str, enum.Enum):
    """Source of the event."""
    ADMIN_ACTION = "admin_action"
    SYSTEM_EVENT = "system_event"
    PARTICIPANT_ACTION = "participant_action"


class ActivityLog(Base):
    """
    Activity log entry for contest-related events.

    Stores an immutable record of actions in the contest management system
    for auditing, admin visibility, and debugging.
    """

    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Admin who performed the action (NULL for system/participant events)
    admin_id = Column(BIGINT, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Contest this event is related to (nullable for some events)
    contest_id = Column(BIGINT, ForeignKey("contests.id", ondelete="SET NULL"), nullable=True, index=True)

    # Event type (e.g., "contest_created", "submission_correct")
    event_type = Column(SQLEnum(EventType, native_enum=False), nullable=False, index=True)

    # Source of the event (admin_action, system_event, participant_action)
    source = Column(SQLEnum(EventSource, native_enum=False), nullable=False, default=EventSource.ADMIN_ACTION)

    # Human-readable action description (e.g., "Created contest 'HackNet Summer'")
    action = Column(String(255), nullable=False)

    # Additional details in JSON format (before/after values, user info, etc.)
    details = Column(JSONB, nullable=True, default=dict)

    # Timestamp (automatically set)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_activity_log_admin_id", "admin_id"),
        Index("idx_activity_log_contest_id", "contest_id"),
        Index("idx_activity_log_event_type", "event_type"),
        Index("idx_activity_log_source", "source"),
        Index("idx_activity_log_created_at", "created_at"),
        Index("idx_activity_log_contest_created", "contest_id", "created_at"),
        Index("idx_activity_log_event_created", "event_type", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ActivityLog(id={self.id}, event_type={self.event_type}, "
            f"contest_id={self.contest_id}, created_at={self.created_at})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "admin_id": self.admin_id,
            "contest_id": self.contest_id,
            "event_type": self.event_type.value if isinstance(self.event_type, EventType) else self.event_type,
            "source": self.source.value if isinstance(self.source, EventSource) else self.source,
            "action": self.action,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
