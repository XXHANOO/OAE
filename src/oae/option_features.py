"""Frozen option-state feature mathematics for OAE v0.1."""

import math
from decimal import Decimal

from oae.data.atm_selection import select_spx_atm_call_put_pair
from oae.data.decision_session import PITDecisionSessionDataset
from oae.data.decision_snapshot import DecisionOptionSnapshot
from oae.data.option_chain import DecisionOptionChainSnapshot
from oae.enums import QualityStatus


__all__ = (
    "OptionFeatureIntegrityError",
    "compute_x9_normalized_0dte_atm_straddle",
)


class OptionFeatureIntegrityError(RuntimeError):
    """Raised when structurally contradictory option-feature input is found."""


def _valid_quote_mid(snapshot: DecisionOptionSnapshot) -> Decimal:
    """Return the exact arithmetic mid for one already-VALID snapshot."""
    quote = snapshot.selected_quote
    if quote is None:
        raise OptionFeatureIntegrityError(
            "a VALID option snapshot must contain its selected quote"
        )
    if (
        quote.source != snapshot.contract.source
        or quote.contract_id != snapshot.contract.contract_id
    ):
        raise OptionFeatureIntegrityError(
            "selected quote must match the snapshot's source-scoped contract"
        )

    bid = quote.bid_px
    ask = quote.ask_px
    if type(bid) is not Decimal or not bid.is_finite() or bid <= 0:
        raise OptionFeatureIntegrityError(
            "a VALID option quote bid must be a finite positive Decimal"
        )
    if type(ask) is not Decimal or not ask.is_finite() or ask <= bid:
        raise OptionFeatureIntegrityError(
            "a VALID option quote ask must be a finite Decimal above bid"
        )
    return (bid + ask) / Decimal("2")


def compute_x9_normalized_0dte_atm_straddle(
    dataset: PITDecisionSessionDataset,
    chain: DecisionOptionChainSnapshot,
) -> float | None:
    """Compute frozen x9 from the approved same-day SPX ATM pair selection."""
    selection = select_spx_atm_call_put_pair(dataset, chain)

    if chain.expiration_date != dataset.session.session_date_et:
        raise OptionFeatureIntegrityError(
            "x9 requires an SPX PM chain expiring on the dataset session date"
        )
    if selection is None:
        return None

    call_snapshot = selection.call_snapshot
    put_snapshot = selection.put_snapshot
    if call_snapshot is None or put_snapshot is None:
        return None
    if (
        call_snapshot.quality_status is not QualityStatus.VALID
        or put_snapshot.quality_status is not QualityStatus.VALID
    ):
        return None

    call_mid = _valid_quote_mid(call_snapshot)
    put_mid = _valid_quote_mid(put_snapshot)
    spot = dataset.session_state.spx_decision_px
    x9 = float((call_mid + put_mid) / spot)
    if not math.isfinite(x9) or x9 <= 0:
        raise OptionFeatureIntegrityError(
            "derived x9 must be finite and strictly positive"
        )
    return x9
