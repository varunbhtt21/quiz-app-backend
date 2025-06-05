"""
Time utilities for consistent UTC handling across the application.
"""

from datetime import datetime, timezone
from typing import Optional


def now_utc() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """Convert datetime to UTC, handling both naive and timezone-aware datetimes."""
    if dt.tzinfo is None:
        # Assume naive datetime is already in UTC
        return dt.replace(tzinfo=timezone.utc)
    else:
        # Convert timezone-aware datetime to UTC
        return dt.astimezone(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is UTC timezone-aware, return None if input is None."""
    if dt is None:
        return None
    return to_utc(dt)


def utc_timestamp_ms() -> int:
    """Get current UTC timestamp in milliseconds for frontend sync."""
    return int(now_utc().timestamp() * 1000)


def parse_iso_to_utc(iso_string: str) -> datetime:
    """Parse ISO string to UTC datetime."""
    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    return to_utc(dt) 