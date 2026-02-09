from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class KnowledgeEntry(BaseModel):
    id: int
    source: str
    source_id: Optional[str] = None
    cve_id: Optional[str] = None
    ru_title: Optional[str] = None
    ru_summary: Optional[str] = None
    ru_explainer: Optional[str] = None
    tags: List[str] = []
    difficulty: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
