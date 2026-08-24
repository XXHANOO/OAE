"""Exact-expiry PM option-chain decision snapshots for OAE v0.1.

The caller supplies the canonical contract and quote universes. This module
does not discover contracts or infer intraday listing availability from the
date-only first/last-seen fields.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from oae.data.decision_snapshot import (
    DecisionOptionSnapshot,
    build_decision_option_snapshot,
)
from oae.enums import SettlementStyle
from oae.schemas.options import OptionContractRecord
from oae.schemas.quotes import OptionQuoteRecord
from oae.temporal import (
    decision_ts_utc as canonical_decision_ts_utc,
    session_date_et_from_timestamp,
    to_utc,
)


__all__ = (
    "DecisionOptionChainSnapshot",
    "DecisionOptionChainSnapshotIntegrityError",
    "build_decision_option_chain_snapshot",
)


@dataclass(frozen=True, slots=True)
class DecisionOptionChainSnapshot:
    """One immutable, source-scoped, exact-expiry PM option chain."""

    product: str
    expiration_date: date
    settlement_style: SettlementStyle
    source: str
    decision_ts_utc: datetime
    snapshots: tuple[DecisionOptionSnapshot, ...]


class DecisionOptionChainSnapshotIntegrityError(RuntimeError):
    """Raised when structural chain-snapshot integrity cannot be established."""


def build_decision_option_chain_snapshot(
    contracts: Sequence[OptionContractRecord],
    quotes: Sequence[OptionQuoteRecord],
    decision_ts: datetime,
    *,
    product: str,
    expiration_date: date,
    source: str,
) -> DecisionOptionChainSnapshot:
    """Build a deterministic exact-expiry PM chain from caller-supplied records."""
    if type(product) is not str or product == "":
        raise DecisionOptionChainSnapshotIntegrityError(
            "product must be an exact non-empty str"
        )
    if type(source) is not str or source == "":
        raise DecisionOptionChainSnapshotIntegrityError(
            "source must be an exact non-empty str"
        )

    decision_ts_utc = to_utc(decision_ts)
    session_date_et = session_date_et_from_timestamp(decision_ts_utc)
    if decision_ts_utc != canonical_decision_ts_utc(session_date_et):
        raise DecisionOptionChainSnapshotIntegrityError(
            "decision_ts must be exactly 13:30:00 America/New_York"
        )

    eligible_contracts = [
        contract
        for contract in contracts
        if contract.product == product
        and contract.expiration_date == expiration_date
        and contract.settlement_style is SettlementStyle.PM
        and contract.source == source
    ]

    identities: set[tuple[str, str]] = set()
    for contract in eligible_contracts:
        identity = (contract.source, contract.contract_id)
        if identity in identities:
            raise DecisionOptionChainSnapshotIntegrityError(
                "duplicate eligible source-scoped contract identity"
            )
        identities.add(identity)

    eligible_contracts.sort(
        key=lambda contract: (
            contract.strike,
            contract.option_type.value,
            contract.contract_id,
        )
    )

    quotes_by_identity: dict[
        tuple[str, str],
        list[OptionQuoteRecord],
    ] = {}
    for quote in quotes:
        quotes_by_identity.setdefault(
            (quote.source, quote.contract_id),
            [],
        ).append(quote)

    snapshots = tuple(
        build_decision_option_snapshot(
            contract,
            tuple(
                quotes_by_identity.get(
                    (contract.source, contract.contract_id),
                    (),
                )
            ),
            decision_ts_utc,
        )
        for contract in eligible_contracts
    )

    return DecisionOptionChainSnapshot(
        product=product,
        expiration_date=expiration_date,
        settlement_style=SettlementStyle.PM,
        source=source,
        decision_ts_utc=decision_ts_utc,
        snapshots=snapshots,
    )
