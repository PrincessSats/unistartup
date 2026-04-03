"""
Pydantic schemas for activity log API.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class ActivityLogResponse(BaseModel):
    """Response model for a single activity log entry."""
    id: int
    admin_id: Optional[int] = None
    contest_id: Optional[int] = None
    event_type: str  # e.g., "contest_created", "submission_correct"
    source: str  # "admin_action", "system_event", "participant_action"
    action: str  # Human-readable description
    details: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityLogListResponse(BaseModel):
    """Response model for paginated activity log list."""
    items: List[ActivityLogResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

    class Config:
        from_attributes = True
