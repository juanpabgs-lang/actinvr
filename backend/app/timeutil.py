"""Time zones are resolved with the IANA database, never hard-coded offsets.

Mexico City has no daylight saving time since 2022; Madrid switches on the last
Sunday of March and October, so the gap between them is 7 or 8 hours.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
MADRID = ZoneInfo("Europe/Madrid")
CDMX = ZoneInfo("America/Mexico_City")
DESK_OPENS = time(9, 0)


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime | None = None) -> str:
    dt = (dt or utcnow()).astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def madrid_today(now: datetime | None = None) -> date:
    return (now or utcnow()).astimezone(MADRID).date()


def gap_hours(now: datetime | None = None) -> int:
    now = now or utcnow()
    m = now.astimezone(MADRID).utcoffset() or timedelta()
    c = now.astimezone(CDMX).utcoffset() or timedelta()
    return int((m - c).total_seconds() // 3600)


def last_desk_opening(now: datetime | None = None) -> datetime:
    """Most recent 09:00 in Madrid that is not in the future."""
    now = now or utcnow()
    local = now.astimezone(MADRID)
    candidate = datetime.combine(local.date(), DESK_OPENS, MADRID)
    if candidate > local:
        candidate = datetime.combine(local.date() - timedelta(days=1), DESK_OPENS, MADRID)
    return candidate.astimezone(UTC)


def clock_payload(now: datetime | None = None) -> dict:
    now = now or utcnow()
    return {
        "utc": iso(now),
        "madrid_offset": (now.astimezone(MADRID).utcoffset() or timedelta()).total_seconds() / 3600,
        "cdmx_offset": (now.astimezone(CDMX).utcoffset() or timedelta()).total_seconds() / 3600,
        "gap_hours": gap_hours(now),
        "desk_opened": iso(last_desk_opening(now)),
    }


def months_between(earlier: date, later: date) -> float:
    return (later - earlier).days / 30.4375
