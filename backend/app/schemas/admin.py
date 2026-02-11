from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AdminStats(BaseModel):
    total_users: int
    active_users_24h: int
    paid_users: int
    current_championship_submissions: int


class AdminFeedback(BaseModel):
    id: int
    user_id: int
    username: Optional[str] = None
    topic: str
    message: str
    resolved: bool = False
    created_at: Optional[datetime] = None


class AdminChampionship(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    start_at: datetime
    end_at: datetime
    is_public: bool
    leaderboard_visible: bool


class AdminArticle(BaseModel):
    id: int
    source: str
    source_id: Optional[str] = None
    cve_id: Optional[str] = None
    raw_en_text: Optional[str] = None
    ru_title: Optional[str] = None
    ru_summary: Optional[str] = None
    ru_explainer: Optional[str] = None
    tags: Optional[List[str]] = None
    difficulty: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class AdminNvdSync(BaseModel):
    last_fetch_at: Optional[datetime] = None
    last_inserted: Optional[int] = None
    status: Optional[str] = None


class AdminDashboardResponse(BaseModel):
    stats: AdminStats
    latest_feedbacks: List[AdminFeedback]
    current_championship: Optional[AdminChampionship] = None
    last_article: Optional[AdminArticle] = None
    nvd_sync: Optional[AdminNvdSync] = None


class AdminArticleCreateRequest(BaseModel):
    source: str
    source_id: Optional[str] = None
    cve_id: Optional[str] = None
    raw_en_text: Optional[str] = None
    ru_title: Optional[str] = None
    ru_summary: Optional[str] = None
    ru_explainer: Optional[str] = None
    tags: Optional[List[str]] = None
    difficulty: Optional[int] = None


class AdminArticleGenerateRequest(BaseModel):
    raw_en_text: str


class AdminArticleGenerateResponse(BaseModel):
    ru_title: str
    ru_summary: str
    ru_explainer: str
    tags: List[str] = Field(default_factory=list)
    model: str
    raw_text: str


class AdminPromptTemplate(BaseModel):
    code: str
    title: str
    description: Optional[str] = None
    content: str
    is_overridden: bool = False
    updated_at: Optional[datetime] = None


class AdminPromptUpdateRequest(BaseModel):
    content: str


class AdminTaskFlag(BaseModel):
    flag_id: str
    format: str
    expected_value: str
    description: Optional[str] = None


class AdminTaskBase(BaseModel):
    title: str
    category: str
    difficulty: int
    points: int
    tags: Optional[List[str]] = None
    language: str = "ru"
    story: Optional[str] = None
    participant_description: Optional[str] = None
    state: str = "draft"
    task_kind: str = "contest"
    llm_raw_response: Optional[dict] = None
    creation_solution: Optional[str] = None


class AdminTaskCreateRequest(AdminTaskBase):
    flags: List[AdminTaskFlag]


class AdminTaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[int] = None
    points: Optional[int] = None
    tags: Optional[List[str]] = None
    language: Optional[str] = None
    story: Optional[str] = None
    participant_description: Optional[str] = None
    state: Optional[str] = None
    task_kind: Optional[str] = None
    llm_raw_response: Optional[dict] = None
    creation_solution: Optional[str] = None
    flags: Optional[List[AdminTaskFlag]] = None


class AdminTaskResponse(AdminTaskBase):
    id: int
    created_at: datetime
    flags: List[AdminTaskFlag] = Field(default_factory=list)


class AdminTaskGenerateRequest(BaseModel):
    difficulty: int
    tags: List[str] = []
    description: str


class AdminTaskGenerateResponse(BaseModel):
    model: str
    task: dict
    raw_text: str


class AdminContestTask(BaseModel):
    task_id: int
    order_index: int
    points_override: Optional[int] = None
    override_title: Optional[str] = None
    override_participant_description: Optional[str] = None
    override_tags: Optional[List[str]] = None
    override_category: Optional[str] = None
    override_difficulty: Optional[int] = None


class AdminContestBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_at: datetime
    end_at: datetime
    is_public: bool = False
    leaderboard_visible: bool = True


class AdminContestCreateRequest(AdminContestBase):
    tasks: List[AdminContestTask]


class AdminContestUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    is_public: Optional[bool] = None
    leaderboard_visible: Optional[bool] = None
    tasks: Optional[List[AdminContestTask]] = None


class AdminContestTaskResponse(AdminContestTask):
    title: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[int] = None
    points: Optional[int] = None
    tags: Optional[List[str]] = None
    participant_description: Optional[str] = None


class AdminContestResponse(AdminContestBase):
    id: int
    tasks: List[AdminContestTaskResponse] = Field(default_factory=list)


class AdminContestListItem(AdminContestBase):
    id: int
    status: str
    tasks_count: int = 0
