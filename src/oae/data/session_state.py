"""Pure point-in-time construction of canonical SPX session state."""

from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from oae.enums import QualityStatus
from oae.schemas.calendar import TradingSessionRecord
from oae.schemas.market import IndexBar1mRecord
from oae.schemas.session import IndexSessionRecord
from oae.temporal import decision_ts_utc, session_open_ts_utc


class SPXSessionStateIntegrityError(RuntimeError):
    """Raised when supplied session-state inputs violate identity rules."""


def build_spx_session_state(
    session: TradingSessionRecord,
    bars: Sequence[IndexBar1mRecord],
    *,
    spx_official_prev_close: Decimal,
) -> IndexSessionRecord:
    """Build the exact 13:30 ET SPX state for one supplied trading session."""
    if not isinstance(spx_official_prev_close, Decimal):
        raise SPXSessionStateIntegrityError(
            "spx_official_prev_close must be a Decimal"
        )
    if spx_official_prev_close <= 0:
        raise SPXSessionStateIntegrityError(
            "spx_official_prev_close must be positive"
        )
    if session.is_trading_day is not True:
        raise SPXSessionStateIntegrityError(
            "session must be a trading day"
        )

    canonical_open = session_open_ts_utc(session.session_date_et)
    if session.open_ts_utc != canonical_open:
        raise SPXSessionStateIntegrityError(
            "session open must equal canonical 09:30 ET"
        )

    decision = decision_ts_utc(session.session_date_et)
    if decision > session.regular_close_ts_utc:
        raise SPXSessionStateIntegrityError(
            "session regular close must not precede the 13:30 ET decision"
        )

    expected_starts = tuple(
        canonical_open + timedelta(minutes=offset) for offset in range(240)
    )
    expected_by_end = {
        start + timedelta(minutes=1): start for start in expected_starts
    }
    required_by_end: dict[datetime, IndexBar1mRecord] = {}

    for bar in bars:
        if bar.session_date_et != session.session_date_et:
            continue
        if bar.bar_start_ts_utc < canonical_open:
            continue
        if bar.bar_end_ts_utc > decision:
            continue

        expected_start = expected_by_end.get(bar.bar_end_ts_utc)
        if expected_start is None or bar.bar_start_ts_utc != expected_start:
            raise SPXSessionStateIntegrityError(
                "off-grid bar in the active decision window"
            )
        if bar.bar_end_ts_utc in required_by_end:
            raise SPXSessionStateIntegrityError(
                "duplicate required bar-end timestamp"
            )
        required_by_end[bar.bar_end_ts_utc] = bar

    if len(required_by_end) != 240:
        raise SPXSessionStateIntegrityError(
            "exactly 240 canonical decision-window bars are required"
        )

    required_bars = tuple(
        required_by_end[start + timedelta(minutes=1)]
        for start in expected_starts
    )
    if any(
        bar.quality_status is not QualityStatus.VALID
        for bar in required_bars
    ):
        raise SPXSessionStateIntegrityError(
            "every required bar must have VALID quality"
        )
    if len({bar.source for bar in required_bars}) != 1:
        raise SPXSessionStateIntegrityError(
            "all required bars must have the same source"
        )

    return IndexSessionRecord(
        session_date_et=session.session_date_et,
        spx_official_prev_close=spx_official_prev_close,
        spx_open=required_bars[0].open,
        spx_decision_px=required_bars[-1].close,
        intraday_high_to_t0=max(bar.high for bar in required_bars),
        intraday_low_to_t0=min(bar.low for bar in required_bars),
        is_full_session=session.is_full_session,
        session_open_ts_utc=session.open_ts_utc,
        session_close_ts_utc=session.regular_close_ts_utc,
    )
