"""Canonical timezone-aware temporal primitives for OAE v0.1."""

import math
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo


MARKET_TIMEZONE_NAME = "America/New_York"
MARKET_TIMEZONE = ZoneInfo(MARKET_TIMEZONE_NAME)
UTC = timezone.utc

SESSION_OPEN_TIME_ET = time(9, 30, 0)
DECISION_TIME_ET = time(13, 30, 0)
PM_REFERENCE_TIME_ET = time(16, 0, 0)

__all__ = (
    "MARKET_TIMEZONE_NAME",
    "MARKET_TIMEZONE",
    "UTC",
    "SESSION_OPEN_TIME_ET",
    "DECISION_TIME_ET",
    "PM_REFERENCE_TIME_ET",
    "to_utc",
    "to_market_time",
    "session_date_et_from_timestamp",
    "session_open_ts_et",
    "session_open_ts_utc",
    "decision_ts_et",
    "decision_ts_utc",
    "pm_reference_ts_et",
    "pm_reference_ts_utc",
    "is_available_asof",
    "age_seconds",
    "is_fresh_asof",
    "in_half_open_interval",
    "bar_is_usable_asof",
)


def _require_aware_datetime(timestamp: datetime, *, name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def to_utc(timestamp: datetime) -> datetime:
    """Convert an aware timestamp to the equivalent UTC instant."""
    _require_aware_datetime(timestamp, name="timestamp")
    return timestamp.astimezone(UTC)


def to_market_time(timestamp: datetime) -> datetime:
    """Convert an aware timestamp to America/New_York."""
    _require_aware_datetime(timestamp, name="timestamp")
    return timestamp.astimezone(MARKET_TIMEZONE)


def session_date_et_from_timestamp(timestamp: datetime) -> date:
    """Derive the market-local date after converting the supplied instant."""
    return to_market_time(timestamp).date()


def session_open_ts_et(session_date_et: date) -> datetime:
    """Construct the frozen 09:30 market timestamp for a supplied date."""
    return datetime.combine(
        session_date_et,
        SESSION_OPEN_TIME_ET,
        tzinfo=MARKET_TIMEZONE,
    )


def session_open_ts_utc(session_date_et: date) -> datetime:
    """Construct the UTC instant for the frozen market-session open."""
    return to_utc(session_open_ts_et(session_date_et))


def decision_ts_et(session_date_et: date) -> datetime:
    """Construct the frozen 13:30 market decision timestamp."""
    return datetime.combine(
        session_date_et,
        DECISION_TIME_ET,
        tzinfo=MARKET_TIMEZONE,
    )


def decision_ts_utc(session_date_et: date) -> datetime:
    """Construct the UTC instant for the frozen market decision time."""
    return to_utc(decision_ts_et(session_date_et))


def pm_reference_ts_et(expiration_date: date) -> datetime:
    """Construct the frozen 16:00 market reference used only for x11 tau."""
    return datetime.combine(
        expiration_date,
        PM_REFERENCE_TIME_ET,
        tzinfo=MARKET_TIMEZONE,
    )


def pm_reference_ts_utc(expiration_date: date) -> datetime:
    """Construct the UTC instant for the frozen x11 PM reference."""
    return to_utc(pm_reference_ts_et(expiration_date))


def is_available_asof(event_ts: datetime, asof_ts: datetime) -> bool:
    """Return whether the event existed at or before the as-of instant."""
    return to_utc(event_ts) <= to_utc(asof_ts)


def age_seconds(event_ts: datetime, asof_ts: datetime) -> float:
    """Return signed elapsed seconds from event to as-of on the UTC timeline."""
    return (to_utc(asof_ts) - to_utc(event_ts)).total_seconds()


def is_fresh_asof(
    event_ts: datetime,
    asof_ts: datetime,
    max_age_seconds: float,
) -> bool:
    """Return whether a non-future event is within the inclusive age limit."""
    if not math.isfinite(max_age_seconds) or max_age_seconds < 0:
        raise ValueError("max_age_seconds must be finite and non-negative")

    age = age_seconds(event_ts, asof_ts)
    return 0.0 <= age <= max_age_seconds


def in_half_open_interval(
    event_ts: datetime,
    start_ts: datetime,
    end_ts: datetime,
) -> bool:
    """Return membership in the absolute-timeline interval [start, end)."""
    event_utc = to_utc(event_ts)
    start_utc = to_utc(start_ts)
    end_utc = to_utc(end_ts)
    if start_utc >= end_utc:
        raise ValueError("start_ts must be earlier than end_ts")
    return start_utc <= event_utc < end_utc


def bar_is_usable_asof(
    bar_start_ts: datetime,
    bar_end_ts: datetime,
    asof_ts: datetime,
) -> bool:
    """Return whether a well-formed bar is fully available by the as-of time."""
    bar_start_utc = to_utc(bar_start_ts)
    bar_end_utc = to_utc(bar_end_ts)
    asof_utc = to_utc(asof_ts)
    if bar_start_utc >= bar_end_utc:
        raise ValueError("bar_start_ts must be earlier than bar_end_ts")
    return bar_end_utc <= asof_utc
