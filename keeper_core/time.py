"""UTC database timestamps and explicit user-timezone display."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def to_storage(value: datetime | None) -> str | None:
    """Return an ISO 8601 UTC timestamp, or NULL for an unknown instant."""
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must have a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def from_storage(value: str | None) -> datetime | None:
    """Read a stored UTC timestamp without assigning a date to NULL."""
    if value is None:
        return None
    if not value.endswith("Z"):
        raise ValueError("stored timestamp must end in Z (UTC)")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    return parsed.astimezone(timezone.utc)


def for_display(value: datetime | None, timezone_name: str) -> str:
    """Format an instant for a named IANA timezone; never infer a timezone."""
    zone = ZoneInfo(timezone_name)
    if value is None:
        return "Unknown"
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must have a timezone")
    local = value.astimezone(zone)
    return local.strftime("%Y-%m-%d %H:%M %Z (%z)")
