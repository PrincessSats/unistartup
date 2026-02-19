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


class ContestTaskInfo(BaseModel):
    class FlagInfo(BaseModel):
        flag_id: str
        format: Optional[str] = None
        description: Optional[str] = None
        is_solved: bool = False

    id: int
    title: str
    category: Optional[str] = None
    difficulty: Optional[int] = None
    points: int = 0
    tags: List[str] = Field(default_factory=list)
    participant_description: Optional[str] = None
    order_index: int = 0
    is_solved: bool = False
    required_flags: List[FlagInfo] = Field(default_factory=list)
    required_flags_count: int = 0
    solved_flags_count: int = 0


class ContestJoinResponse(BaseModel):
    contest_id: int
    joined_at: datetime
    is_joined: bool = True


class ContestTaskState(BaseModel):
    contest_id: int
    task: Optional[ContestTaskInfo] = None
    progress_index: int
    tasks_total: int
    solved_task_ids: List[int] = Field(default_factory=list)
    previous_tasks: List[ContestTaskInfo] = Field(default_factory=list)
    finished: bool = False


class ContestSubmissionRequest(BaseModel):
    task_id: Optional[int] = None
    flag_id: Optional[str] = None
    flag: str


class ContestSubmissionResponse(BaseModel):
    is_correct: bool
    awarded_points: int
    next_task: Optional[ContestTaskInfo] = None
    finished: bool = False
