"""Frozen option-state feature mathematics for OAE v0.1."""

import math
from decimal import Decimal

from oae.data.atm_selection import select_spx_atm_call_put_pair
from oae.data.decision_session import PITDecisionSessionDataset
from oae.data.decision_snapshot import DecisionOptionSnapshot
from oae.data.option_chain import DecisionOptionChainSnapshot
from oae.enums import OptionType, QualityStatus


__all__ = (
    "OptionFeatureIntegrityError",
    "compute_x9_normalized_0dte_atm_straddle",
    "compute_x10_price_based_downside_skew",
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


def _select_unique_nearest_side_snapshot(
    chain: DecisionOptionChainSnapshot,
    option_type: OptionType,
    target: Decimal,
) -> DecisionOptionSnapshot | None:
    """Select the unique listed side snapshot nearest the exact target."""
    side_snapshots = tuple(
        snapshot
        for snapshot in chain.snapshots
        if snapshot.contract.option_type is option_type
    )
    if not side_snapshots:
        return None

    selected_strike = min(
        {snapshot.contract.strike for snapshot in side_snapshots},
        key=lambda strike: (abs(strike - target), strike),
    )
    selected = tuple(
        snapshot
        for snapshot in side_snapshots
        if snapshot.contract.strike == selected_strike
    )
    if len(selected) > 1:
        raise OptionFeatureIntegrityError(
            f"selected x10 {option_type.name} strike has multiple contracts"
        )
    return selected[0]


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


def compute_x10_price_based_downside_skew(
    dataset: PITDecisionSessionDataset,
    chain: DecisionOptionChainSnapshot,
) -> float | None:
    """Compute frozen signed x10 from listed side targets and the ATM pair."""
    atm_selection = select_spx_atm_call_put_pair(dataset, chain)

    if chain.expiration_date != dataset.session.session_date_et:
        raise OptionFeatureIntegrityError(
            "x10 requires an SPX PM chain expiring on the dataset session date"
        )
    if atm_selection is None:
        return None

    spot = dataset.session_state.spx_decision_px
    put_snapshot = _select_unique_nearest_side_snapshot(
        chain,
        OptionType.PUT,
        Decimal("0.995") * spot,
    )
    call_snapshot = _select_unique_nearest_side_snapshot(
        chain,
        OptionType.CALL,
        Decimal("1.005") * spot,
    )
    if put_snapshot is None or call_snapshot is None:
        return None

    atm_call_snapshot = atm_selection.call_snapshot
    atm_put_snapshot = atm_selection.put_snapshot
    if atm_call_snapshot is None or atm_put_snapshot is None:
        return None
    required_snapshots = (
        atm_call_snapshot,
        atm_put_snapshot,
        put_snapshot,
        call_snapshot,
    )
    if any(
        snapshot.quality_status is not QualityStatus.VALID
        for snapshot in required_snapshots
    ):
        return None

    atm_call_mid = _valid_quote_mid(atm_call_snapshot)
    atm_put_mid = _valid_quote_mid(atm_put_snapshot)
    put_mid = _valid_quote_mid(put_snapshot)
    call_mid = _valid_quote_mid(call_snapshot)
    x10 = float((put_mid - call_mid) / (atm_call_mid + atm_put_mid))
    if not math.isfinite(x10):
        raise OptionFeatureIntegrityError("derived x10 must be finite")
    return x10
