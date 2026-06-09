"""
Pydantic-схемы для API журнала активности.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class ActivityLogResponse(BaseModel):
    """Модель ответа для одной записи журнала активности."""
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
    """Модель ответа для постраничного списка журнала активности."""
    items: List[ActivityLogResponse]
    total: int
    page: int
    page_size: int
    has_more: bool

    class Config:
        from_attributes = True
