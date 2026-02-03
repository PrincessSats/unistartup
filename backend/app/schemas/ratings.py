from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    user_id: int
    username: str
    avatar_url: Optional[str] = None
    rating: int
    solved: int
    first_blood: int
    rank: int
    is_current_user: bool = False


class LeaderboardResponse(BaseModel):
    kind: str
    generated_at: datetime
    entries: List[LeaderboardEntry]
