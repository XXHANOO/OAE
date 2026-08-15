"""Point-in-time quote age and quality primitives for OAE v0.1."""

from collections.abc import Sequence
import math
from datetime import datetime

from oae.enums import QualityStatus
from oae.schemas.quotes import OptionQuoteRecord
from oae.temporal import age_seconds, to_utc


_FROZEN_MAX_AGE_SECONDS = 2.0
_FROZEN_MIN_BID_SIZE = 1
_FROZEN_MIN_ASK_SIZE = 1


class AsOfSelectionIntegrityError(RuntimeError):
    """Raised when an as-of quote stream cannot be selected unambiguously."""


def select_asof_quote(
    quotes: Sequence[OptionQuoteRecord],
    decision_ts: datetime,
) -> OptionQuoteRecord | None:
    """Return the latest unambiguous quote at or before ``decision_ts``."""
    decision_utc = to_utc(decision_ts)
    if not quotes:
        return None

    first_quote = quotes[0]
    stream_source = first_quote.source
    stream_contract_id = first_quote.contract_id
    for quote in quotes:
        if (
            quote.source != stream_source
            or quote.contract_id != stream_contract_id
        ):
            raise AsOfSelectionIntegrityError(
                "quotes must belong to one exact source-scoped contract stream"
            )

    latest_quote_ts_utc: datetime | None = None
    latest_quotes: list[OptionQuoteRecord] = []
    for quote in quotes:
        quote_ts_utc = to_utc(quote.quote_ts_utc)
        if quote_ts_utc > decision_utc:
            continue
        if latest_quote_ts_utc is None or quote_ts_utc > latest_quote_ts_utc:
            latest_quote_ts_utc = quote_ts_utc
            latest_quotes = [quote]
        elif quote_ts_utc == latest_quote_ts_utc:
            latest_quotes.append(quote)

    if not latest_quotes:
        return None
    if len(latest_quotes) == 1:
        return latest_quotes[0]

    canonical_payload = latest_quotes[0].model_dump(mode="python")
    if any(
        quote.model_dump(mode="python") != canonical_payload
        for quote in latest_quotes[1:]
    ):
        raise AsOfSelectionIntegrityError(
            "distinct quotes share the maximum eligible timestamp"
        )
    return latest_quotes[0]


def quote_age_seconds(
    quote_ts: datetime,
    decision_ts: datetime,
) -> float:
    """Return signed quote age on the canonical absolute timeline."""
    return age_seconds(quote_ts, decision_ts)


def _validate_frozen_max_age(max_age_seconds: float) -> None:
    if isinstance(max_age_seconds, bool):
        raise ValueError("max_age_seconds must equal the frozen 2.0 seconds")

    try:
        is_finite = math.isfinite(max_age_seconds)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "max_age_seconds must equal the frozen 2.0 seconds"
        ) from exc

    if not is_finite or max_age_seconds != _FROZEN_MAX_AGE_SECONDS:
        raise ValueError("max_age_seconds must equal the frozen 2.0 seconds")


def classify_quote_quality(
    quote: OptionQuoteRecord,
    decision_ts: datetime,
    max_age_seconds: float,
) -> QualityStatus:
    """Classify one normalized quote under the frozen OAE v0.1 policy."""
    _validate_frozen_max_age(max_age_seconds)
    age = quote_age_seconds(quote.quote_ts_utc, decision_ts)

    if age < 0.0:
        raise ValueError("quote timestamp must not be later than decision_ts")

    if quote.bid_px <= 0:
        return QualityStatus.ZERO_BID

    if quote.ask_px == quote.bid_px:
        return QualityStatus.LOCKED

    if quote.ask_px < quote.bid_px:
        return QualityStatus.CROSSED

    if (
        quote.bid_size < _FROZEN_MIN_BID_SIZE
        or quote.ask_size < _FROZEN_MIN_ASK_SIZE
    ):
        return QualityStatus.ZERO_SIZE

    if age > _FROZEN_MAX_AGE_SECONDS:
        return QualityStatus.STALE

    return QualityStatus.VALID
