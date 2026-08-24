"""Deterministic SPX ATM strike and call/put snapshot selection."""

from dataclasses import dataclass
from decimal import Decimal

from oae.data.decision_session import PITDecisionSessionDataset
from oae.data.decision_snapshot import DecisionOptionSnapshot
from oae.data.option_chain import DecisionOptionChainSnapshot
from oae.enums import OptionType, SettlementStyle


__all__ = (
    "ATMCallPutPairSelection",
    "ATMCallPutPairSelectionIntegrityError",
    "select_spx_atm_call_put_pair",
)


@dataclass(frozen=True, slots=True)
class ATMCallPutPairSelection:
    """The unique listed call and put snapshots at the frozen ATM strike."""

    strike: Decimal
    call_snapshot: DecisionOptionSnapshot | None
    put_snapshot: DecisionOptionSnapshot | None


class ATMCallPutPairSelectionIntegrityError(RuntimeError):
    """Raised when the supplied PIT dataset and chain cannot be paired safely."""


def select_spx_atm_call_put_pair(
    dataset: PITDecisionSessionDataset,
    chain: DecisionOptionChainSnapshot,
) -> ATMCallPutPairSelection | None:
    """Select the listed SPX ATM strike, then resolve its unique call and put."""
    if type(dataset) is not PITDecisionSessionDataset:
        raise ATMCallPutPairSelectionIntegrityError(
            "dataset must be an exact PITDecisionSessionDataset"
        )
    if type(chain) is not DecisionOptionChainSnapshot:
        raise ATMCallPutPairSelectionIntegrityError(
            "chain must be an exact DecisionOptionChainSnapshot"
        )
    if chain.product != "SPX":
        raise ATMCallPutPairSelectionIntegrityError("chain product must be SPX")
    if chain.settlement_style is not SettlementStyle.PM:
        raise ATMCallPutPairSelectionIntegrityError(
            "chain settlement style must be PM"
        )
    if chain.decision_ts_utc != dataset.decision_ts_utc:
        raise ATMCallPutPairSelectionIntegrityError(
            "chain and dataset decision timestamps must match"
        )
    if type(chain.snapshots) is not tuple:
        raise ATMCallPutPairSelectionIntegrityError(
            "chain snapshots must be an exact tuple"
        )

    spot = dataset.session_state.spx_decision_px
    if type(spot) is not Decimal or not spot.is_finite() or spot <= 0:
        raise ATMCallPutPairSelectionIntegrityError(
            "SPX decision price must be a finite positive Decimal"
        )

    strikes: set[Decimal] = set()
    identities: set[tuple[str, str]] = set()
    for snapshot in chain.snapshots:
        if type(snapshot) is not DecisionOptionSnapshot:
            raise ATMCallPutPairSelectionIntegrityError(
                "every chain element must be an exact DecisionOptionSnapshot"
            )
        if snapshot.decision_ts_utc != chain.decision_ts_utc:
            raise ATMCallPutPairSelectionIntegrityError(
                "snapshot decision timestamp must match the chain"
            )

        contract = snapshot.contract
        if contract.product != chain.product:
            raise ATMCallPutPairSelectionIntegrityError(
                "snapshot contract product must match the chain"
            )
        if contract.expiration_date != chain.expiration_date:
            raise ATMCallPutPairSelectionIntegrityError(
                "snapshot contract expiration must match the chain"
            )
        if contract.settlement_style != chain.settlement_style:
            raise ATMCallPutPairSelectionIntegrityError(
                "snapshot contract settlement style must match the chain"
            )
        if contract.source != chain.source:
            raise ATMCallPutPairSelectionIntegrityError(
                "snapshot contract source must match the chain"
            )

        identity = (contract.source, contract.contract_id)
        if identity in identities:
            raise ATMCallPutPairSelectionIntegrityError(
                "duplicate source-scoped contract identity in chain"
            )
        identities.add(identity)

        strike = contract.strike
        if type(strike) is not Decimal or not strike.is_finite() or strike <= 0:
            raise ATMCallPutPairSelectionIntegrityError(
                "every listed strike must be a finite positive Decimal"
            )
        strikes.add(strike)

    if not strikes:
        return None

    atm_strike = min(strikes, key=lambda strike: (abs(strike - spot), strike))
    selected = tuple(
        snapshot
        for snapshot in chain.snapshots
        if snapshot.contract.strike == atm_strike
    )
    calls = tuple(
        snapshot
        for snapshot in selected
        if snapshot.contract.option_type is OptionType.CALL
    )
    puts = tuple(
        snapshot
        for snapshot in selected
        if snapshot.contract.option_type is OptionType.PUT
    )
    if len(calls) > 1:
        raise ATMCallPutPairSelectionIntegrityError(
            "selected ATM strike has multiple CALL contracts"
        )
    if len(puts) > 1:
        raise ATMCallPutPairSelectionIntegrityError(
            "selected ATM strike has multiple PUT contracts"
        )

    return ATMCallPutPairSelection(
        strike=atm_strike,
        call_snapshot=calls[0] if calls else None,
        put_snapshot=puts[0] if puts else None,
    )
