"""Canonical point-in-time SPX decision-session dataset construction."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from oae.data.minute_returns import build_canonical_minute_return_series
from oae.data.session_state import build_spx_session_state
from oae.schemas.calendar import TradingSessionRecord
from oae.schemas.market import IndexBar1mRecord
from oae.schemas.session import IndexSessionRecord
from oae.temporal import decision_ts_utc, session_open_ts_utc


__all__ = (
    "PITDecisionSessionDataset",
    "PITDecisionSessionDatasetIntegrityError",
    "build_pit_decision_session_dataset",
)


@dataclass(frozen=True, slots=True)
class PITDecisionSessionDataset:
    """Immutable canonical SPX inputs available at the 13:30 ET decision."""

    session: TradingSessionRecord
    session_state: IndexSessionRecord
    decision_ts_utc: datetime
    canonical_bars: tuple[IndexBar1mRecord, ...]
    canonical_minute_returns: tuple[float, ...]


class PITDecisionSessionDatasetIntegrityError(RuntimeError):
    """Raised when validated upstream results cannot form the PIT bundle."""


def build_pit_decision_session_dataset(
    session: TradingSessionRecord,
    bars: Sequence[IndexBar1mRecord],
    *,
    spx_official_prev_close: Decimal,
) -> PITDecisionSessionDataset:
    """Compose the canonical 13:30 ET SPX decision-session dataset."""
    session_state = build_spx_session_state(
        session,
        bars,
        spx_official_prev_close=spx_official_prev_close,
    )
    canonical_minute_returns = build_canonical_minute_return_series(
        session_state,
        bars,
    )

    canonical_open = session_open_ts_utc(session.session_date_et)
    decision_timestamp = decision_ts_utc(session.session_date_et)
    expected_intervals = tuple(
        (
            canonical_open + timedelta(minutes=offset),
            canonical_open + timedelta(minutes=offset + 1),
        )
        for offset in range(240)
    )
    bars_by_interval = {
        (bar.bar_start_ts_utc, bar.bar_end_ts_utc): bar
        for bar in bars
        if bar.session_date_et == session.session_date_et
        and (bar.bar_start_ts_utc, bar.bar_end_ts_utc) in expected_intervals
    }
    canonical_bars = tuple(
        bars_by_interval[interval]
        for interval in expected_intervals
        if interval in bars_by_interval
    )

    if decision_timestamp != expected_intervals[-1][1]:
        raise PITDecisionSessionDatasetIntegrityError(
            "canonical decision timestamp must end the final required interval"
        )
    if len(canonical_bars) != 240:
        raise PITDecisionSessionDatasetIntegrityError(
            "validated session must contain exactly 240 canonical bars"
        )
    if tuple(
        (bar.bar_start_ts_utc, bar.bar_end_ts_utc)
        for bar in canonical_bars
    ) != expected_intervals:
        raise PITDecisionSessionDatasetIntegrityError(
            "canonical bars must match the exact chronological interval grid"
        )
    if len(canonical_minute_returns) != 240:
        raise PITDecisionSessionDatasetIntegrityError(
            "validated session must contain exactly 240 canonical returns"
        )
    if canonical_bars[0].open != session_state.spx_open:
        raise PITDecisionSessionDatasetIntegrityError(
            "canonical first-bar open must match the session state"
        )
    if canonical_bars[-1].close != session_state.spx_decision_px:
        raise PITDecisionSessionDatasetIntegrityError(
            "canonical final-bar close must match the session state"
        )

    return PITDecisionSessionDataset(
        session=session,
        session_state=session_state,
        decision_ts_utc=decision_timestamp,
        canonical_bars=canonical_bars,
        canonical_minute_returns=canonical_minute_returns,
    )
