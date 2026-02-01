from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class FeaturedTask(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    points: int = 0


class ContestSummary(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    start_at: datetime
    end_at: datetime
    is_public: bool
    leaderboard_visible: bool
    tasks_total: int
    tasks_solved: int
    reward_points: int
    participants_count: int
    first_blood_username: Optional[str] = None
    knowledge_areas: List[str] = Field(default_factory=list)
    days_left: int
    prev_contest_id: Optional[int] = None
    next_contest_id: Optional[int] = None
    featured_task: Optional[FeaturedTask] = None
