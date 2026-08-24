"""Frozen direct SPX price features available at the 13:30 ET decision."""

import math
from datetime import timedelta
from decimal import Decimal

from oae.data.decision_session import PITDecisionSessionDataset
from oae.temporal import decision_ts_utc


__all__ = (
    "SPXPriceFeatureIntegrityError",
    "compute_spx_price_features_x1_x4",
    "compute_spx_price_features_x5_x8",
)


class SPXPriceFeatureIntegrityError(RuntimeError):
    """Raised when the PIT dataset cannot define frozen SPX features x1-x8."""


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


def compute_spx_price_features_x5_x8(
    dataset: PITDecisionSessionDataset,
) -> tuple[float, float, float, float]:
    """Compute frozen x5-x8 from canonical PIT state and minute returns."""
    if not isinstance(dataset, PITDecisionSessionDataset):
        raise SPXPriceFeatureIntegrityError(
            "dataset must be a PITDecisionSessionDataset"
        )

    canonical_decision = decision_ts_utc(dataset.session.session_date_et)
    if dataset.decision_ts_utc != canonical_decision:
        raise SPXPriceFeatureIntegrityError(
            "dataset decision timestamp must equal canonical 13:30 ET"
        )

    canonical_returns = dataset.canonical_minute_returns
    if not isinstance(canonical_returns, tuple):
        raise SPXPriceFeatureIntegrityError(
            "canonical minute returns must be a tuple"
        )
    if len(canonical_returns) != 240:
        raise SPXPriceFeatureIntegrityError(
            "dataset must contain exactly 240 canonical minute returns"
        )
    if any(type(value) is not float for value in canonical_returns):
        raise SPXPriceFeatureIntegrityError(
            "every canonical minute return must be a Python float"
        )
    if not all(math.isfinite(value) for value in canonical_returns):
        raise SPXPriceFeatureIntegrityError(
            "every canonical minute return must be finite"
        )

    session_open = _as_positive_finite_float(
        dataset.session_state.spx_open,
        name="session SPX open",
    )
    decision_price = _as_positive_finite_float(
        dataset.session_state.spx_decision_px,
        name="session SPX decision price",
    )
    intraday_high = _as_positive_finite_float(
        dataset.session_state.intraday_high_to_t0,
        name="intraday SPX high through decision",
    )
    intraday_low = _as_positive_finite_float(
        dataset.session_state.intraday_low_to_t0,
        name="intraday SPX low through decision",
    )
    if intraday_high < intraday_low:
        raise SPXPriceFeatureIntegrityError(
            "intraday SPX high must not be below intraday SPX low"
        )
    if not intraday_low <= decision_price <= intraday_high:
        raise SPXPriceFeatureIntegrityError(
            "session SPX decision price must lie within the intraday range"
        )

    try:
        sum_sq_30 = math.fsum(
            value * value for value in canonical_returns[-30:]
        )
        sum_sq_all = math.fsum(
            value * value for value in canonical_returns
        )
        sum_abs_all = math.fsum(
            abs(value) for value in canonical_returns
        )
    except OverflowError as error:
        raise SPXPriceFeatureIntegrityError(
            "canonical return reductions must be finite"
        ) from error
    reductions = (sum_sq_30, sum_sq_all, sum_abs_all)
    if not all(math.isfinite(value) for value in reductions):
        raise SPXPriceFeatureIntegrityError(
            "canonical return reductions must be finite"
        )

    x7_denominator = intraday_high - intraday_low + 1e-8
    x8_denominator = sum_abs_all + 1e-8
    if not math.isfinite(x7_denominator) or x7_denominator <= 0.0:
        raise SPXPriceFeatureIntegrityError(
            "x7 denominator must be finite and positive"
        )
    if not math.isfinite(x8_denominator) or x8_denominator <= 0.0:
        raise SPXPriceFeatureIntegrityError(
            "x8 denominator must be finite and positive"
        )

    x5 = math.sqrt(sum_sq_30)
    x6 = math.sqrt(sum_sq_all)
    x7 = (decision_price - intraday_low) / x7_denominator
    x8 = abs(
        _natural_log_ratio(
            decision_price,
            session_open,
            name="x8 numerator",
        )
    ) / x8_denominator
    features = (x5, x6, x7, x8)
    if not all(math.isfinite(feature) for feature in features):
        raise SPXPriceFeatureIntegrityError(
            "every computed SPX price feature must be finite"
        )
    return features
