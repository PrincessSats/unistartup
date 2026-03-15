from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import secrets
from typing import Iterable

PROMO_SOURCE_LANDING_HUNT = "landing_hunt"
PROMO_REWARD_POINTS = 10
PROMO_TTL = timedelta(days=3)
PROMO_CODE_LENGTH = 5
PROMO_CODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
LANDING_HUNT_BUG_KEYS = (
    "hero_console",
    "championship_card",
    "learning_split",
    "audience_slider",
    "faq_console",
    "footer_logo",
)
_PROMO_CODE_RE = re.compile(r"^[A-Z0-9]{5}$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_session_token(value: str | None) -> str:
    return str(value or "").strip()


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def normalize_bug_key(value: str | None) -> str:
    return str(value or "").strip().lower()


def is_valid_bug_key(value: str | None) -> bool:
    return normalize_bug_key(value) in LANDING_HUNT_BUG_KEYS


def ordered_found_bug_keys(found_bug_keys: Iterable[str]) -> list[str]:
    normalized = {normalize_bug_key(item) for item in found_bug_keys if normalize_bug_key(item)}
    return [bug_key for bug_key in LANDING_HUNT_BUG_KEYS if bug_key in normalized]


def apply_found_bug(found_bug_keys: Iterable[str], bug_key: str) -> tuple[list[str], bool, bool]:
    normalized_bug_key = normalize_bug_key(bug_key)
    current = ordered_found_bug_keys(found_bug_keys)
    already_completed = len(current) == len(LANDING_HUNT_BUG_KEYS)

    if normalized_bug_key not in LANDING_HUNT_BUG_KEYS:
        return current, False, False

    if normalized_bug_key in current:
        return current, False, False

    updated = ordered_found_bug_keys([*current, normalized_bug_key])
    just_completed = not already_completed and len(updated) == len(LANDING_HUNT_BUG_KEYS)
    return updated, True, just_completed


def is_promo_code_format(value: str | None) -> bool:
    return bool(_PROMO_CODE_RE.fullmatch(str(value or "").strip().upper()))


def normalize_promo_code(value: str | None) -> str:
    return str(value or "").strip().upper()


def create_promo_code() -> str:
    return "".join(secrets.choice(PROMO_CODE_ALPHABET) for _ in range(PROMO_CODE_LENGTH))

