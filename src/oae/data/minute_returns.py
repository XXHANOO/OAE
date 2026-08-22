"""Canonical SPX regular-session one-minute log-return construction."""

import math
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from oae.enums import QualityStatus
from oae.schemas.market import IndexBar1mRecord
from oae.schemas.session import IndexSessionRecord
from oae.temporal import decision_ts_utc, session_open_ts_utc


__all__ = (
    "CanonicalMinuteReturnIntegrityError",
    "build_canonical_minute_return_series",
)


class CanonicalMinuteReturnIntegrityError(RuntimeError):
    """Raised when supplied bars cannot define the canonical return series."""


def _as_positive_finite_float(value: Decimal, *, name: str) -> float:
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise CanonicalMinuteReturnIntegrityError(
            f"{name} must be finite and positive after float conversion"
        ) from error
    if not math.isfinite(converted) or converted <= 0.0:
        raise CanonicalMinuteReturnIntegrityError(
            f"{name} must be finite and positive after float conversion"
        )
    return converted


def build_canonical_minute_return_series(
    session_state: IndexSessionRecord,
    bars: Sequence[IndexBar1mRecord],
) -> tuple[float, ...]:
    """Build the 240 log returns ending from 09:31 through 13:30 ET."""
    canonical_open = session_open_ts_utc(session_state.session_date_et)
    if session_state.session_open_ts_utc != canonical_open:
        raise CanonicalMinuteReturnIntegrityError(
            "session open must equal canonical 09:30 ET"
        )

    decision = decision_ts_utc(session_state.session_date_et)
    if decision > session_state.session_close_ts_utc:
        raise CanonicalMinuteReturnIntegrityError(
            "session close must not precede the 13:30 ET decision"
        )

    expected_starts = tuple(
        canonical_open + timedelta(minutes=offset) for offset in range(240)
    )
    expected_by_end = {
        start + timedelta(minutes=1): start for start in expected_starts
    }
    required_by_end: dict[datetime, IndexBar1mRecord] = {}

    for bar in bars:
        if bar.session_date_et != session_state.session_date_et:
            continue
        if bar.bar_end_ts_utc <= canonical_open:
            continue
        if bar.bar_end_ts_utc > decision:
            continue

        expected_start = expected_by_end.get(bar.bar_end_ts_utc)
        if expected_start is None or bar.bar_start_ts_utc != expected_start:
            raise CanonicalMinuteReturnIntegrityError(
                "off-grid bar in the active decision window"
            )
        if bar.bar_end_ts_utc in required_by_end:
            raise CanonicalMinuteReturnIntegrityError(
                "duplicate required bar-end timestamp"
            )
        required_by_end[bar.bar_end_ts_utc] = bar

    if len(required_by_end) != 240:
        raise CanonicalMinuteReturnIntegrityError(
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
        raise CanonicalMinuteReturnIntegrityError(
            "every required bar must have VALID quality"
        )
    if len({bar.source for bar in required_bars}) != 1:
        raise CanonicalMinuteReturnIntegrityError(
            "all required bars must have the same source"
        )
    if required_bars[0].open != session_state.spx_open:
        raise CanonicalMinuteReturnIntegrityError(
            "first required bar open must equal session SPX open"
        )
    if required_bars[-1].close != session_state.spx_decision_px:
        raise CanonicalMinuteReturnIntegrityError(
            "last required bar close must equal session SPX decision price"
        )

    previous_price = _as_positive_finite_float(
        session_state.spx_open,
        name="session SPX open",
    )
    returns: list[float] = []
    for bar in required_bars:
        current_close = _as_positive_finite_float(
            bar.close,
            name="required bar close",
        )
        ratio = current_close / previous_price
        if not math.isfinite(ratio) or ratio <= 0.0:
            raise CanonicalMinuteReturnIntegrityError(
                "required price ratio must be finite and positive"
            )
        minute_return = math.log(ratio)
        if not math.isfinite(minute_return):
            raise CanonicalMinuteReturnIntegrityError(
                "canonical minute return must be finite"
            )
        returns.append(minute_return)
        previous_price = current_close

    return tuple(returns)
