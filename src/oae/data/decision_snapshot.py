"""Per-contract decision-time option quote snapshots for OAE v0.1."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from oae.data.asof import (
    classify_quote_quality,
    quote_age_seconds,
    select_asof_quote,
)
from oae.enums import QualityStatus
from oae.schemas.options import OptionContractRecord
from oae.schemas.quotes import OptionQuoteRecord
from oae.temporal import to_utc


_FROZEN_MAX_AGE_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class DecisionOptionSnapshot:
    """The selected point-in-time quote state for one source-scoped contract."""

    contract: OptionContractRecord
    decision_ts_utc: datetime
    selected_quote: OptionQuoteRecord | None
    quote_age_seconds: float | None
    quality_status: QualityStatus


class DecisionOptionSnapshotIntegrityError(RuntimeError):
    """Raised when supplied quotes do not match the supplied contract stream."""


def build_decision_option_snapshot(
    contract: OptionContractRecord,
    quotes: Sequence[OptionQuoteRecord],
    decision_ts: datetime,
) -> DecisionOptionSnapshot:
    """Build one immutable decision-time snapshot without quality-first filtering."""
    decision_ts_utc = to_utc(decision_ts)

    for quote in quotes:
        if (
            quote.source != contract.source
            or quote.contract_id != contract.contract_id
        ):
            raise DecisionOptionSnapshotIntegrityError(
                "quotes must match the supplied exact source-scoped contract"
            )

    selected_quote = select_asof_quote(quotes, decision_ts_utc)
    if selected_quote is None:
        return DecisionOptionSnapshot(
            contract=contract,
            decision_ts_utc=decision_ts_utc,
            selected_quote=None,
            quote_age_seconds=None,
            quality_status=QualityStatus.MISSING,
        )

    age = quote_age_seconds(selected_quote.quote_ts_utc, decision_ts_utc)
    quality_status = classify_quote_quality(
        selected_quote,
        decision_ts_utc,
        _FROZEN_MAX_AGE_SECONDS,
    )
    return DecisionOptionSnapshot(
        contract=contract,
        decision_ts_utc=decision_ts_utc,
        selected_quote=selected_quote,
        quote_age_seconds=age,
        quality_status=quality_status,
    )
