import inspect
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

import oae.data.atm_selection as atm_selection
from oae.data.atm_selection import (
    ATMCallPutPairSelection,
    ATMCallPutPairSelectionIntegrityError,
    select_spx_atm_call_put_pair,
)
from oae.data.decision_session import (
    PITDecisionSessionDataset,
    build_pit_decision_session_dataset,
)
from oae.data.decision_snapshot import DecisionOptionSnapshot
from oae.data.option_chain import (
    DecisionOptionChainSnapshot,
    build_decision_option_chain_snapshot,
)
from oae.enums import (
    ExerciseStyle,
    OptionType,
    QualityStatus,
    SettlementStyle,
)
from oae.schemas.calendar import TradingSessionRecord
from oae.schemas.market import IndexBar1mRecord
from oae.schemas.options import OptionContractRecord
from oae.schemas.quotes import OptionQuoteRecord
from oae.temporal import decision_ts_utc, session_open_ts_utc


UTC = timezone.utc
SESSION_DATE = date(2026, 7, 15)
FUTURE_EXPIRY = date(2026, 7, 17)
DECISION = decision_ts_utc(SESSION_DATE)
SOURCE = "TEST_PROVIDER"
SELECTION_FIELDS = ["strike", "call_snapshot", "put_snapshot"]


def _dataset(spot: Decimal = Decimal("6000.25")) -> PITDecisionSessionDataset:
    session = TradingSessionRecord(
        session_date_et=SESSION_DATE,
        session_seq=100,
        open_ts_utc=session_open_ts_utc(SESSION_DATE),
        regular_close_ts_utc=datetime(2026, 7, 15, 20, tzinfo=UTC),
        is_trading_day=True,
        is_full_session=True,
        is_half_day=False,
        xsp_0dte_exists=True,
    )
    bars = [
        IndexBar1mRecord(
            symbol="SPX",
            session_date_et=SESSION_DATE,
            bar_start_ts_utc=session.open_ts_utc + timedelta(minutes=index),
            bar_end_ts_utc=session.open_ts_utc + timedelta(minutes=index + 1),
            open=spot,
            high=spot + Decimal("1"),
            low=spot - Decimal("1"),
            close=spot,
            observation_count=10,
            source=SOURCE,
            raw_file_id="bars-raw",
            quality_status=QualityStatus.VALID,
        )
        for index in range(240)
    ]
    return build_pit_decision_session_dataset(
        session,
        bars,
        spx_official_prev_close=spot,
    )


def _contract(
    contract_id: str,
    strike: Decimal,
    option_type: OptionType,
    *,
    product: str = "SPX",
    expiration_date: date = SESSION_DATE,
    settlement_style: SettlementStyle = SettlementStyle.PM,
    source: str = SOURCE,
    root_symbol: str = "SPXW",
) -> OptionContractRecord:
    return OptionContractRecord(
        contract_id=contract_id,
        vendor_symbol=f"VENDOR-{contract_id}",
        product=product,
        root_symbol=root_symbol,
        underlying=product,
        option_type=option_type,
        strike=strike,
        expiration_date=expiration_date,
        settlement_style=settlement_style,
        exercise_style=ExerciseStyle.EUROPEAN,
        multiplier=100,
        series_type="PM_WEEKLY",
        expiration_ts_utc=datetime(
            expiration_date.year,
            expiration_date.month,
            expiration_date.day,
            20,
            tzinfo=UTC,
        ),
        first_seen_date=date(2026, 7, 1),
        last_seen_date=expiration_date,
        source=source,
    )


def _quote(
    contract: OptionContractRecord,
    quality: QualityStatus,
) -> OptionQuoteRecord | None:
    if quality is QualityStatus.MISSING:
        return None
    values: dict[str, object] = {
        "contract_id": contract.contract_id,
        "quote_ts_utc": DECISION - timedelta(seconds=1),
        "session_date_et": SESSION_DATE,
        "bid_px": Decimal("1.00"),
        "ask_px": Decimal("1.10"),
        "bid_size": 1,
        "ask_size": 1,
        "bid_exchange": "BID",
        "ask_exchange": "ASK",
        "quote_condition": None,
        "sequence_no": None,
        "source": contract.source,
        "raw_file_id": f"raw-{contract.contract_id}",
    }
    if quality is QualityStatus.STALE:
        values["quote_ts_utc"] = DECISION - timedelta(microseconds=2_000_001)
    elif quality is QualityStatus.CROSSED:
        values["bid_px"] = Decimal("1.20")
        values["ask_px"] = Decimal("1.10")
    elif quality is QualityStatus.LOCKED:
        values["ask_px"] = Decimal("1.00")
    elif quality is QualityStatus.ZERO_BID:
        values["bid_px"] = Decimal("0")
    elif quality is QualityStatus.ZERO_SIZE:
        values["bid_size"] = 0
    elif quality is not QualityStatus.VALID:
        raise AssertionError(f"unsupported test quality: {quality}")
    return OptionQuoteRecord.model_validate(values)


def _chain(
    contracts: list[OptionContractRecord],
    *,
    qualities: dict[str, QualityStatus] | None = None,
    product: str = "SPX",
    expiration_date: date = SESSION_DATE,
    source: str = SOURCE,
) -> DecisionOptionChainSnapshot:
    quality_map = qualities or {}
    quotes = [
        quote
        for contract in contracts
        if (quote := _quote(
            contract,
            quality_map.get(contract.contract_id, QualityStatus.MISSING),
        ))
        is not None
    ]
    return build_decision_option_chain_snapshot(
        contracts,
        quotes,
        DECISION,
        product=product,
        expiration_date=expiration_date,
        source=source,
    )


def _pair(
    strike: Decimal,
    prefix: str,
    *,
    expiration_date: date = SESSION_DATE,
    product: str = "SPX",
) -> list[OptionContractRecord]:
    return [
        _contract(
            f"{prefix}-CALL",
            strike,
            OptionType.CALL,
            expiration_date=expiration_date,
            product=product,
        ),
        _contract(
            f"{prefix}-PUT",
            strike,
            OptionType.PUT,
            expiration_date=expiration_date,
            product=product,
        ),
    ]


def _snapshot(
    chain: DecisionOptionChainSnapshot,
    contract_id: str,
) -> DecisionOptionSnapshot:
    return next(
        snapshot
        for snapshot in chain.snapshots
        if snapshot.contract.contract_id == contract_id
    )


def test_atm_001_to_007_public_api_immutability_and_empty_chain() -> None:
    assert is_dataclass(ATMCallPutPairSelection)
    assert ATMCallPutPairSelection.__dataclass_params__.frozen
    assert ATMCallPutPairSelection.__slots__ == tuple(SELECTION_FIELDS)
    assert [field.name for field in fields(ATMCallPutPairSelection)] == (
        SELECTION_FIELDS
    )
    assert issubclass(ATMCallPutPairSelectionIntegrityError, RuntimeError)
    assert ATMCallPutPairSelectionIntegrityError is not RuntimeError
    signature = inspect.signature(select_spx_atm_call_put_pair)
    assert list(signature.parameters) == ["dataset", "chain"]
    assert all(
        parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        for parameter in signature.parameters.values()
    )
    assert atm_selection.__all__ == (
        "ATMCallPutPairSelection",
        "ATMCallPutPairSelectionIntegrityError",
        "select_spx_atm_call_put_pair",
    )
    selection = ATMCallPutPairSelection(Decimal("6000"), None, None)
    assert not hasattr(selection, "__dict__")
    with pytest.raises(FrozenInstanceError):
        selection.strike = Decimal("6001")  # type: ignore[misc]
    assert select_spx_atm_call_put_pair(_dataset(), _chain([])) is None


def test_atm_008_to_011_exact_and_strictly_nearest_strikes() -> None:
    contracts = (
        _pair(Decimal("5987.25"), "LOW")
        + _pair(Decimal("6000.125"), "EXACT")
        + _pair(Decimal("6017.875"), "HIGH")
    )
    chain = _chain(contracts)
    exact = select_spx_atm_call_put_pair(_dataset(Decimal("6000.125")), chain)
    nearer_lower = select_spx_atm_call_put_pair(_dataset(Decimal("5998")), chain)
    nearer_higher = select_spx_atm_call_put_pair(_dataset(Decimal("6013")), chain)
    assert exact is not None and exact.strike == Decimal("6000.125")
    assert nearer_lower is not None and nearer_lower.strike == Decimal("6000.125")
    assert nearer_higher is not None and nearer_higher.strike == Decimal("6017.875")


def test_atm_012_to_016_lower_tie_is_independent_of_chain_order() -> None:
    chain = _chain(
        _pair(Decimal("5995"), "FAR-LOW")
        + _pair(Decimal("6000"), "LOW")
        + _pair(Decimal("6005"), "HIGH")
    )
    dataset = _dataset(Decimal("6002.5"))
    forward = select_spx_atm_call_put_pair(dataset, chain)
    reversed_chain = replace(chain, snapshots=tuple(reversed(chain.snapshots)))
    reversed_result = select_spx_atm_call_put_pair(dataset, reversed_chain)
    assert forward is not None and forward.strike == Decimal("6000")
    assert reversed_result is not None
    assert reversed_result.strike == Decimal("6000")
    assert reversed_result.call_snapshot is forward.call_snapshot
    assert reversed_result.put_snapshot is forward.put_snapshot


def test_atm_017_to_027_put_only_and_call_only_nearest_strikes_do_not_fallback() -> None:
    put_only = _contract("NEAR-PUT", Decimal("6000"), OptionType.PUT)
    complete = _pair(Decimal("6005"), "FAR")
    put_chain = _chain(
        [put_only, *complete],
        qualities={
            "NEAR-PUT": QualityStatus.MISSING,
            "FAR-CALL": QualityStatus.VALID,
            "FAR-PUT": QualityStatus.VALID,
        },
    )
    put_result = select_spx_atm_call_put_pair(
        _dataset(Decimal("6000.2")),
        put_chain,
    )
    assert put_result is not None and put_result.strike == Decimal("6000")
    assert put_result.call_snapshot is None
    assert put_result.put_snapshot is _snapshot(put_chain, "NEAR-PUT")

    call_only = _contract("NEAR-CALL", Decimal("6000"), OptionType.CALL)
    call_chain = _chain([call_only, *complete])
    call_result = select_spx_atm_call_put_pair(
        _dataset(Decimal("6000.2")),
        call_chain,
    )
    assert call_result is not None and call_result.strike == Decimal("6000")
    assert call_result.call_snapshot is _snapshot(call_chain, "NEAR-CALL")
    assert call_result.put_snapshot is None


def test_atm_028_to_030_missing_snapshot_is_not_an_absent_contract() -> None:
    missing_call = _contract("MISSING-CALL", Decimal("6000"), OptionType.CALL)
    chain = _chain(
        [missing_call, *_pair(Decimal("6007"), "FAR")],
        qualities={
            "MISSING-CALL": QualityStatus.MISSING,
            "FAR-CALL": QualityStatus.VALID,
            "FAR-PUT": QualityStatus.VALID,
        },
    )
    missing_snapshot = _snapshot(chain, "MISSING-CALL")
    result = select_spx_atm_call_put_pair(_dataset(Decimal("6000.1")), chain)
    assert result is not None
    assert result.call_snapshot is missing_snapshot
    assert result.call_snapshot is not None
    assert result.call_snapshot.quality_status is QualityStatus.MISSING
    assert result.call_snapshot.selected_quote is None


@pytest.mark.parametrize(
    "invalid_quality",
    [
        QualityStatus.MISSING,
        QualityStatus.STALE,
        QualityStatus.CROSSED,
        QualityStatus.LOCKED,
        QualityStatus.ZERO_BID,
        QualityStatus.ZERO_SIZE,
    ],
)
def test_atm_031_to_033_invalid_selected_side_never_triggers_fallback(
    invalid_quality: QualityStatus,
) -> None:
    near = _pair(Decimal("6000"), "NEAR")
    far = _pair(Decimal("6006"), "FAR")
    chain = _chain(
        [*near, *far],
        qualities={
            "NEAR-CALL": QualityStatus.VALID,
            "NEAR-PUT": invalid_quality,
            "FAR-CALL": QualityStatus.VALID,
            "FAR-PUT": QualityStatus.VALID,
        },
    )
    result = select_spx_atm_call_put_pair(_dataset(Decimal("6000.2")), chain)
    invalid_snapshot = _snapshot(chain, "NEAR-PUT")
    assert result is not None and result.strike == Decimal("6000")
    assert result.put_snapshot is invalid_snapshot
    assert result.put_snapshot.quality_status is invalid_quality


def test_atm_034_lower_invalid_pair_beats_equidistant_higher_valid_pair() -> None:
    chain = _chain(
        [
            *_pair(Decimal("6000"), "LOW"),
            *_pair(Decimal("6005"), "HIGH"),
        ],
        qualities={
            "LOW-CALL": QualityStatus.MISSING,
            "LOW-PUT": QualityStatus.CROSSED,
            "HIGH-CALL": QualityStatus.VALID,
            "HIGH-PUT": QualityStatus.VALID,
        },
    )
    result = select_spx_atm_call_put_pair(_dataset(Decimal("6002.5")), chain)
    assert result is not None and result.strike == Decimal("6000")
    assert result.call_snapshot is _snapshot(chain, "LOW-CALL")
    assert result.put_snapshot is _snapshot(chain, "LOW-PUT")


def test_atm_035_to_039_unique_pair_preserves_exact_object_identity() -> None:
    chain = _chain(
        [
            *_pair(Decimal("5993"), "FAR"),
            *_pair(Decimal("6000"), "ATM"),
        ]
    )
    result = select_spx_atm_call_put_pair(_dataset(Decimal("6000.1")), chain)
    call = _snapshot(chain, "ATM-CALL")
    put = _snapshot(chain, "ATM-PUT")
    assert result is not None
    assert result.call_snapshot is call
    assert result.put_snapshot is put
    assert result.call_snapshot.contract.option_type is OptionType.CALL
    assert result.put_snapshot.contract.option_type is OptionType.PUT
    assert result.call_snapshot.contract.strike == result.strike
    assert result.put_snapshot.contract.strike == result.strike


@pytest.mark.parametrize("duplicate_side", [OptionType.CALL, OptionType.PUT])
def test_atm_040_to_043_selected_multiple_side_contracts_hard_fail(
    duplicate_side: OptionType,
) -> None:
    other_side = (
        OptionType.PUT if duplicate_side is OptionType.CALL else OptionType.CALL
    )
    contracts = [
        _contract("Z-DUPLICATE", Decimal("6000"), duplicate_side),
        _contract("A-DUPLICATE", Decimal("6000"), duplicate_side),
        _contract("OTHER-SIDE", Decimal("6000"), other_side),
    ]
    chain = _chain(
        contracts,
        qualities={
            "Z-DUPLICATE": QualityStatus.VALID,
            "A-DUPLICATE": QualityStatus.MISSING,
            "OTHER-SIDE": QualityStatus.VALID,
        },
    )
    with pytest.raises(
        ATMCallPutPairSelectionIntegrityError,
        match="multiple (CALL|PUT)",
    ):
        select_spx_atm_call_put_pair(_dataset(Decimal("6000")), chain)


def test_atm_044_to_045_nonselected_multiplicity_does_not_block() -> None:
    selected_pair = _pair(Decimal("6000"), "ATM")
    far_duplicates = [
        _contract("FAR-CALL-A", Decimal("6010"), OptionType.CALL),
        _contract("FAR-CALL-B", Decimal("6010"), OptionType.CALL),
    ]
    chain = _chain([*selected_pair, *far_duplicates])
    result = select_spx_atm_call_put_pair(_dataset(Decimal("6000.1")), chain)
    assert result is not None and result.strike == Decimal("6000")
    assert result.call_snapshot is _snapshot(chain, "ATM-CALL")
    assert result.put_snapshot is _snapshot(chain, "ATM-PUT")


def test_atm_046_to_048_fractional_decimal_tie_and_float_mutant_resistance() -> None:
    fractional_chain = _chain(
        _pair(Decimal("6000.125"), "LOW")
        + _pair(Decimal("6000.375"), "HIGH")
    )
    fractional_result = select_spx_atm_call_put_pair(
        _dataset(Decimal("6000.250")),
        fractional_chain,
    )
    assert fractional_result is not None
    assert fractional_result.strike == Decimal("6000.125")

    exact_low = Decimal("6000.00000000000000000000")
    exact_high = Decimal("6000.00000000000000000009")
    exact_spot = Decimal("6000.00000000000000000005")
    assert float(exact_low) == float(exact_high) == float(exact_spot)
    precision_chain = _chain(
        _pair(exact_low, "PRECISION-LOW")
        + _pair(exact_high, "PRECISION-HIGH")
    )
    precision_result = select_spx_atm_call_put_pair(
        _dataset(exact_spot),
        precision_chain,
    )
    assert precision_result is not None
    assert precision_result.strike == exact_high


def test_atm_049_to_053_pit_spot_authority_and_timestamp_coherence() -> None:
    signature = inspect.signature(select_spx_atm_call_put_pair)
    assert set(signature.parameters) == {"dataset", "chain"}
    chain = _chain(
        _pair(Decimal("6000"), "LOW")
        + _pair(Decimal("6005"), "HIGH")
    )
    low_dataset = _dataset(Decimal("6000.1"))
    high_dataset = _dataset(Decimal("6004.9"))
    low_result = select_spx_atm_call_put_pair(low_dataset, chain)
    high_result = select_spx_atm_call_put_pair(high_dataset, chain)
    assert low_result is not None and low_result.strike == Decimal("6000")
    assert high_result is not None and high_result.strike == Decimal("6005")
    assert chain.decision_ts_utc == low_dataset.decision_ts_utc
    mismatched = replace(
        chain,
        decision_ts_utc=chain.decision_ts_utc + timedelta(microseconds=1),
    )
    with pytest.raises(
        ATMCallPutPairSelectionIntegrityError,
        match="timestamps",
    ):
        select_spx_atm_call_put_pair(low_dataset, mismatched)


def test_atm_054_to_057_spx_pm_only_and_root_symbol_is_irrelevant() -> None:
    spxw_chain = _chain(
        [
            _contract(
                "SPXW-CALL",
                Decimal("6000"),
                OptionType.CALL,
                root_symbol="SPXW",
            )
        ]
    )
    result = select_spx_atm_call_put_pair(_dataset(), spxw_chain)
    assert result is not None and result.call_snapshot is spxw_chain.snapshots[0]

    xsp_contract = _contract(
        "XSP-CALL",
        Decimal("600"),
        OptionType.CALL,
        product="XSP",
        root_symbol="XSP",
    )
    xsp_chain = _chain([xsp_contract], product="XSP")
    with pytest.raises(ATMCallPutPairSelectionIntegrityError, match="SPX"):
        select_spx_atm_call_put_pair(_dataset(), xsp_chain)

    alias_chain = replace(spxw_chain, product="SPXW")
    with pytest.raises(ATMCallPutPairSelectionIntegrityError, match="SPX"):
        select_spx_atm_call_put_pair(_dataset(), alias_chain)

    am_chain = replace(spxw_chain, settlement_style=SettlementStyle.AM)
    with pytest.raises(ATMCallPutPairSelectionIntegrityError, match="PM"):
        select_spx_atm_call_put_pair(_dataset(), am_chain)


def test_atm_058_to_061_same_day_and_future_expiry_chains_are_supported() -> None:
    same_day = _chain(_pair(Decimal("6000"), "SAME-DAY"))
    future_contracts = _pair(
        Decimal("6000"),
        "FUTURE",
        expiration_date=FUTURE_EXPIRY,
    )
    future = _chain(future_contracts, expiration_date=FUTURE_EXPIRY)
    dataset = _dataset(Decimal("6000"))
    same_day_result = select_spx_atm_call_put_pair(dataset, same_day)
    future_result = select_spx_atm_call_put_pair(dataset, future)
    assert same_day_result is not None and same_day_result.strike == Decimal("6000")
    assert future_result is not None and future_result.strike == Decimal("6000")
    assert {
        "next_expiry",
        "select_next_expiry",
        "expiration_calendar",
    }.isdisjoint(vars(atm_selection))


def test_atm_062_to_064_wrong_bundle_types_and_snapshot_container_fail() -> None:
    dataset = _dataset()
    chain = _chain(_pair(Decimal("6000"), "ATM"))
    with pytest.raises(ATMCallPutPairSelectionIntegrityError, match="dataset"):
        select_spx_atm_call_put_pair(object(), chain)  # type: ignore[arg-type]
    with pytest.raises(ATMCallPutPairSelectionIntegrityError, match="chain"):
        select_spx_atm_call_put_pair(dataset, object())  # type: ignore[arg-type]
    list_chain = replace(chain, snapshots=list(chain.snapshots))  # type: ignore[arg-type]
    with pytest.raises(ATMCallPutPairSelectionIntegrityError, match="tuple"):
        select_spx_atm_call_put_pair(dataset, list_chain)


def test_atm_065_to_069_snapshot_bundle_coherence_failures() -> None:
    dataset = _dataset()
    chain = _chain(_pair(Decimal("6000"), "ATM"))
    first = chain.snapshots[0]

    malformed_cases = [
        replace(
            first,
            decision_ts_utc=first.decision_ts_utc + timedelta(microseconds=1),
        ),
        replace(first, contract=first.contract.model_copy(update={"product": "XSP"})),
        replace(
            first,
            contract=first.contract.model_copy(update={"expiration_date": FUTURE_EXPIRY}),
        ),
        replace(
            first,
            contract=first.contract.model_copy(
                update={"settlement_style": SettlementStyle.AM}
            ),
        ),
        replace(
            first,
            contract=first.contract.model_copy(update={"source": "OTHER_SOURCE"}),
        ),
    ]
    for malformed in malformed_cases:
        malformed_chain = replace(
            chain,
            snapshots=(malformed, *chain.snapshots[1:]),
        )
        with pytest.raises(ATMCallPutPairSelectionIntegrityError):
            select_spx_atm_call_put_pair(dataset, malformed_chain)


def test_atm_070_duplicate_identity_and_non_snapshot_element_fail() -> None:
    dataset = _dataset()
    chain = _chain(_pair(Decimal("6000"), "ATM"))
    duplicate_identity = replace(
        chain,
        snapshots=(chain.snapshots[0], chain.snapshots[0]),
    )
    with pytest.raises(
        ATMCallPutPairSelectionIntegrityError,
        match="duplicate source-scoped",
    ):
        select_spx_atm_call_put_pair(dataset, duplicate_identity)

    non_snapshot = replace(chain, snapshots=(object(),))  # type: ignore[arg-type]
    with pytest.raises(
        ATMCallPutPairSelectionIntegrityError,
        match="DecisionOptionSnapshot",
    ):
        select_spx_atm_call_put_pair(dataset, non_snapshot)


@pytest.mark.parametrize(
    "bad_spot",
    [0.0, Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")],
)
def test_atm_071_to_072_spot_must_be_exact_finite_positive_decimal(
    bad_spot: object,
) -> None:
    dataset = _dataset()
    malformed_state = dataset.session_state.model_copy(
        update={"spx_decision_px": bad_spot}
    )
    malformed_dataset = replace(dataset, session_state=malformed_state)
    with pytest.raises(ATMCallPutPairSelectionIntegrityError, match="price"):
        select_spx_atm_call_put_pair(
            malformed_dataset,
            _chain(_pair(Decimal("6000"), "ATM")),
        )


@pytest.mark.parametrize(
    "bad_strike",
    [6000.0, Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")],
)
def test_atm_073_to_074_strike_must_be_exact_finite_positive_decimal(
    bad_strike: object,
) -> None:
    dataset = _dataset()
    chain = _chain(_pair(Decimal("6000"), "ATM"))
    first = chain.snapshots[0]
    malformed_contract = first.contract.model_copy(update={"strike": bad_strike})
    malformed_snapshot = replace(first, contract=malformed_contract)
    malformed_chain = replace(
        chain,
        snapshots=(malformed_snapshot, *chain.snapshots[1:]),
    )
    with pytest.raises(ATMCallPutPairSelectionIntegrityError, match="strike"):
        select_spx_atm_call_put_pair(dataset, malformed_chain)


def test_atm_075_to_079_order_independence_and_input_purity() -> None:
    chain = _chain(
        _pair(Decimal("5995"), "LOW")
        + _pair(Decimal("6000"), "ATM")
        + _pair(Decimal("6005"), "HIGH")
    )
    dataset = _dataset(Decimal("6000.1"))
    dataset_before = dataset
    chain_before = chain
    baseline = select_spx_atm_call_put_pair(dataset, chain)
    reversed_result = select_spx_atm_call_put_pair(
        dataset,
        replace(chain, snapshots=tuple(reversed(chain.snapshots))),
    )
    shuffled = (
        chain.snapshots[2],
        chain.snapshots[5],
        chain.snapshots[0],
        chain.snapshots[4],
        chain.snapshots[1],
        chain.snapshots[3],
    )
    shuffled_result = select_spx_atm_call_put_pair(
        dataset,
        replace(chain, snapshots=shuffled),
    )
    assert baseline is not None
    assert reversed_result is not None
    assert shuffled_result is not None
    assert baseline.strike == reversed_result.strike == shuffled_result.strike
    assert baseline.call_snapshot is reversed_result.call_snapshot
    assert baseline.call_snapshot is shuffled_result.call_snapshot
    assert baseline.put_snapshot is reversed_result.put_snapshot
    assert baseline.put_snapshot is shuffled_result.put_snapshot
    assert dataset == dataset_before
    assert chain == chain_before


def test_atm_080_to_086_no_premature_feature_or_quote_rebuild_surface() -> None:
    assert {
        "compute_x9",
        "compute_x10",
        "compute_x11",
        "select_next_expiry",
        "build_decision_option_snapshot",
        "select_asof_quote",
        "classify_quote_quality",
        "build_decision_option_chain_snapshot",
    }.isdisjoint(vars(atm_selection))
    assert [field.name for field in fields(ATMCallPutPairSelection)] == (
        SELECTION_FIELDS
    )
    selection = select_spx_atm_call_put_pair(
        _dataset(Decimal("6000")),
        _chain(
            _pair(Decimal("6000"), "ATM"),
            qualities={
                "ATM-CALL": QualityStatus.MISSING,
                "ATM-PUT": QualityStatus.CROSSED,
            },
        ),
    )
    assert selection is not None
    assert not hasattr(selection, "call_mid")
    assert not hasattr(selection, "put_mid")
    assert not hasattr(selection, "mid_price")
    assert not hasattr(selection, "feature_valid")
    assert not hasattr(selection, "invalid_reason")
    assert selection.call_snapshot is not None
    assert selection.call_snapshot.quality_status is QualityStatus.MISSING
    assert selection.put_snapshot is not None
    assert selection.put_snapshot.quality_status is QualityStatus.CROSSED
