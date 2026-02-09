from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class KBCommentCreate(BaseModel):
    body: str
    parent_id: Optional[int] = None


class KBComment(BaseModel):
    id: int
    kb_entry_id: int
    user_id: int
    parent_id: Optional[int] = None
    body: str
    status: str
    created_at: datetime
    username: Optional[str] = None
    avatar_url: Optional[str] = None
