from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LandingHuntSessionRequest(BaseModel):
    session_token: Optional[str] = Field(default=None, max_length=256)


class LandingHuntFoundRequest(LandingHuntSessionRequest):
    bug_key: str = Field(..., min_length=1, max_length=64)


class LandingHuntResponse(BaseModel):
    session_token: str
    found_bug_keys: list[str]
    found_count: int
    total_count: int
    completed: bool
    promo_code: Optional[str] = None
    just_completed: bool = False


class PromoCodeRedeemRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)


class PromoCodeState(BaseModel):
    has_redeemed_landing_promo: bool = False
    landing_promo_redeemed_at: Optional[datetime] = None

