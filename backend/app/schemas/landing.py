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


class LandingSettingsPublic(BaseModel):
    """Public landing config exposed to anonymous visitors."""

    is_visible: bool = True
    hunt_enabled: bool = True
    hero_eyebrow: Optional[str] = None
    hero_title: Optional[str] = None
    hero_subtitle: Optional[str] = None


class LandingSettingsUpdate(BaseModel):
    is_visible: Optional[bool] = None
    hunt_enabled: Optional[bool] = None
    reward_points: Optional[int] = Field(default=None, ge=0, le=100000)
    hero_eyebrow: Optional[str] = Field(default=None, max_length=256)
    hero_title: Optional[str] = Field(default=None, max_length=512)
    hero_subtitle: Optional[str] = Field(default=None, max_length=512)


class LandingHuntAnalytics(BaseModel):
    total_sessions: int = 0
    completed_sessions: int = 0
    total_bugs_found: int = 0
    per_bug_found: dict[str, int] = Field(default_factory=dict)
    promos_issued: int = 0
    promos_redeemed: int = 0
    points_granted: int = 0


class LandingAdminResponse(BaseModel):
    is_visible: bool
    hunt_enabled: bool
    reward_points: int
    hero_eyebrow: Optional[str] = None
    hero_title: Optional[str] = None
    hero_subtitle: Optional[str] = None
    updated_at: Optional[datetime] = None
    bug_keys: list[str] = Field(default_factory=list)
    analytics: LandingHuntAnalytics = Field(default_factory=LandingHuntAnalytics)

