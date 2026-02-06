from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AdminStats(BaseModel):
    total_users: int
    active_users_24h: int
    paid_users: int
    current_championship_submissions: int


class AdminFeedback(BaseModel):
    user_id: int
    username: Optional[str] = None
    topic: str
    message: str
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
