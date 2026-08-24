"""Frozen direct SPX price features available at the 13:30 ET decision."""

import math
from datetime import timedelta
from decimal import Decimal

from oae.data.decision_session import PITDecisionSessionDataset
from oae.temporal import decision_ts_utc


__all__ = (
    "SPXPriceFeatureIntegrityError",
    "compute_spx_price_features_x1_x4",
)


class SPXPriceFeatureIntegrityError(RuntimeError):
    """Raised when the PIT dataset cannot define frozen SPX features x1-x4."""


def _as_positive_finite_float(value: Decimal, *, name: str) -> float:
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise SPXPriceFeatureIntegrityError(
            f"{name} must be finite and positive after float conversion"
        ) from error
    if not math.isfinite(converted) or converted <= 0.0:
        raise SPXPriceFeatureIntegrityError(
            f"{name} must be finite and positive after float conversion"
        )
    return converted


def _natural_log_ratio(
    numerator: float,
    denominator: float,
    *,
    name: str,
) -> float:
    try:
        ratio = numerator / denominator
    except OverflowError as error:
        raise SPXPriceFeatureIntegrityError(
            f"{name} price ratio must be finite and positive"
        ) from error
    if not math.isfinite(ratio) or ratio <= 0.0:
        raise SPXPriceFeatureIntegrityError(
            f"{name} price ratio must be finite and positive"
        )
    result = math.log(ratio)
    if not math.isfinite(result):
        raise SPXPriceFeatureIntegrityError(f"{name} must be finite")
    return result


def compute_spx_price_features_x1_x4(
    dataset: PITDecisionSessionDataset,
) -> tuple[float, float, float, float]:
    """Compute frozen x1-x4 directly from canonical PIT state and bar prices."""
    if not isinstance(dataset, PITDecisionSessionDataset):
        raise SPXPriceFeatureIntegrityError(
            "dataset must be a PITDecisionSessionDataset"
        )

    canonical_decision = decision_ts_utc(dataset.session.session_date_et)
    if dataset.decision_ts_utc != canonical_decision:
        raise SPXPriceFeatureIntegrityError(
            "dataset decision timestamp must equal canonical 13:30 ET"
        )
    if len(dataset.canonical_bars) != 240:
        raise SPXPriceFeatureIntegrityError(
            "dataset must contain exactly 240 canonical bars"
        )
    if len(dataset.canonical_minute_returns) != 240:
        raise SPXPriceFeatureIntegrityError(
            "dataset must contain exactly 240 canonical minute returns"
        )

    five_minute_end = canonical_decision - timedelta(minutes=5)
    thirty_minute_end = canonical_decision - timedelta(minutes=30)
    current_bars = tuple(
        bar
        for bar in dataset.canonical_bars
        if bar.bar_end_ts_utc == canonical_decision
    )
    five_minute_bars = tuple(
        bar
        for bar in dataset.canonical_bars
        if bar.bar_end_ts_utc == five_minute_end
    )
    thirty_minute_bars = tuple(
        bar
        for bar in dataset.canonical_bars
        if bar.bar_end_ts_utc == thirty_minute_end
    )
    if len(current_bars) != 1:
        raise SPXPriceFeatureIntegrityError(
            "exactly one 13:30 close anchor is required"
        )
    if len(five_minute_bars) != 1:
        raise SPXPriceFeatureIntegrityError(
            "exactly one 13:25 close anchor is required"
        )
    if len(thirty_minute_bars) != 1:
        raise SPXPriceFeatureIntegrityError(
            "exactly one 13:00 close anchor is required"
        )

    if dataset.canonical_bars[0].open != dataset.session_state.spx_open:
        raise SPXPriceFeatureIntegrityError(
            "dataset first-bar open must equal session-state SPX open"
        )
    if dataset.canonical_bars[-1].close != dataset.session_state.spx_decision_px:
        raise SPXPriceFeatureIntegrityError(
            "dataset final-bar close must equal session-state decision price"
        )
    if dataset.canonical_bars[-1].bar_end_ts_utc != canonical_decision:
        raise SPXPriceFeatureIntegrityError(
            "the 13:30 close anchor must be the final canonical bar"
        )

    official_previous_close = _as_positive_finite_float(
        dataset.session_state.spx_official_prev_close,
        name="official previous SPX close",
    )
    session_open = _as_positive_finite_float(
        dataset.session_state.spx_open,
        name="session SPX open",
    )
    decision_price = _as_positive_finite_float(
        dataset.session_state.spx_decision_px,
        name="session SPX decision price",
    )
    current_close = _as_positive_finite_float(
        current_bars[0].close,
        name="13:30 SPX close",
    )
    five_minute_close = _as_positive_finite_float(
        five_minute_bars[0].close,
        name="13:25 SPX close",
    )
    thirty_minute_close = _as_positive_finite_float(
        thirty_minute_bars[0].close,
        name="13:00 SPX close",
    )

    x1 = _natural_log_ratio(
        session_open,
        official_previous_close,
        name="x1",
    )
    x2 = _natural_log_ratio(
        decision_price,
        session_open,
        name="x2",
    )
    x3 = _natural_log_ratio(
        current_close,
        five_minute_close,
        name="x3",
    )
    x4 = _natural_log_ratio(
        current_close,
        thirty_minute_close,
        name="x4",
    )
    features = (x1, x2, x3, x4)
    if not all(math.isfinite(feature) for feature in features):
        raise SPXPriceFeatureIntegrityError(
            "every computed SPX price feature must be finite"
        )
    return features
