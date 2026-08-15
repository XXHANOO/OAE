"""Pure trading-session and FOMC afternoon calendar gate."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from oae.schemas.calendar import MacroEventRecord, TradingSessionRecord
from oae.temporal import decision_ts_et, pm_reference_ts_et, to_utc


class CalendarIntegrityError(RuntimeError):
    """Raised when a supplied calendar collection violates its identity rules."""


def validate_trading_session_sequence(
    sessions: Sequence[TradingSessionRecord],
) -> None:
    """Validate date uniqueness and chronological trading-session sequence."""
    dates = [session.session_date_et for session in sessions]
    if len(dates) != len(set(dates)):
        raise CalendarIntegrityError("duplicate session_date_et values")

    trading_sessions = sorted(
        (session for session in sessions if session.is_trading_day),
        key=lambda session: session.session_date_et,
    )
    for earlier, later in zip(trading_sessions, trading_sessions[1:]):
        if later.session_seq <= earlier.session_seq:
            raise CalendarIntegrityError(
                "session_seq must strictly increase with trading date"
            )


@dataclass(frozen=True, slots=True)
class SessionCalendarGate:
    session: TradingSessionRecord
    decision_ts_utc: datetime
    full_session_eligible: bool
    fomc_afternoon_blocked: bool
    calendar_gate_pass: bool


def _event_overlaps_afternoon(
    event: MacroEventRecord,
    window_start_utc: datetime,
    window_end_utc: datetime,
) -> bool:
    if event.event_start_ts_utc == event.event_end_ts_utc:
        return window_start_utc <= event.event_start_ts_utc < window_end_utc
    return (
        event.event_start_ts_utc < window_end_utc
        and event.event_end_ts_utc > window_start_utc
    )


def build_session_calendar_gate(
    session: TradingSessionRecord,
    macro_events: Sequence[MacroEventRecord],
) -> SessionCalendarGate:
    """Build the immutable current-session calendar-only eligibility gate."""
    event_ids: set[str] = set()
    for event in macro_events:
        if event.event_id in event_ids:
            raise CalendarIntegrityError("duplicate event_id values")
        event_ids.add(event.event_id)

    decision_ts_utc = to_utc(decision_ts_et(session.session_date_et))
    window_start_utc = decision_ts_utc
    window_end_utc = to_utc(pm_reference_ts_et(session.session_date_et))

    target_events = [
        event
        for event in macro_events
        if event.event_date_et == session.session_date_et
    ]
    for event in target_events:
        if not event.verified:
            raise CalendarIntegrityError("target-date macro event is unverified")

    fomc_afternoon_blocked = any(
        _event_overlaps_afternoon(event, window_start_utc, window_end_utc)
        for event in target_events
    )
    full_session_eligible = (
        session.is_trading_day
        and session.is_full_session
        and not session.is_half_day
    )
    return SessionCalendarGate(
        session=session,
        decision_ts_utc=decision_ts_utc,
        full_session_eligible=full_session_eligible,
        fomc_afternoon_blocked=fomc_afternoon_blocked,
        calendar_gate_pass=full_session_eligible and not fomc_afternoon_blocked,
    )
