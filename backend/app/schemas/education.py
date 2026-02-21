from typing import List, Literal, Optional

from pydantic import BaseModel, Field


PracticeStatus = Literal["not_started", "in_progress", "solved"]
DifficultyLabel = Literal["Легко", "Средне", "Сложно"]
PracticeAccessType = Literal["vpn", "vm", "link", "file", "just_flag"]


class PracticeVpnInfo(BaseModel):
    config_ip: Optional[str] = None
    allowed_ips: Optional[str] = None
    created_at: Optional[str] = None
    how_to_connect_url: Optional[str] = None
    download_url: Optional[str] = None


class PracticeTaskMaterial(BaseModel):
    id: int
    type: str
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    storage_key: Optional[str] = None
    meta: Optional[dict] = None


class PracticeTaskCard(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    category: str
    difficulty: int
    difficulty_label: DifficultyLabel
    points: int
    passed_users_count: int = 0
    my_status: PracticeStatus
    tags: List[str] = Field(default_factory=list)


class PracticeTaskListResponse(BaseModel):
    items: List[PracticeTaskCard] = Field(default_factory=list)
    total: int = 0
    categories: List[str] = Field(default_factory=list)


class PracticeTaskDetailResponse(BaseModel):
    id: int
    title: str
    category: str
    difficulty: int
    difficulty_label: DifficultyLabel
    points: int
    tags: List[str] = Field(default_factory=list)
    participant_description: Optional[str] = None
    story: Optional[str] = None
    my_status: PracticeStatus
    solved_flags_count: int = 0
    required_flags_count: int = 0
    passed_users_count: int = 0
    hints_count: int = 0
    hints: List[str] = Field(default_factory=list)
    connection_ip: Optional[str] = None
    access_type: PracticeAccessType = "just_flag"
    materials: List[PracticeTaskMaterial] = Field(default_factory=list)
    vpn: Optional[PracticeVpnInfo] = None


class PracticeTaskSubmitRequest(BaseModel):
    flag: str
    flag_id: Optional[str] = None


class PracticeTaskSubmitResponse(BaseModel):
    is_correct: bool
    awarded_points: int
    status: PracticeStatus
    solved_flags_count: int
    required_flags_count: int
    message: str


class PracticeTaskMaterialDownloadResponse(BaseModel):
    url: str
    expires_in: int = 300
    filename: Optional[str] = None
