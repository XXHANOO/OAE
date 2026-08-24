import inspect
import math
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

import oae.option_features as option_features
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
from oae.option_features import (
    OptionFeatureIntegrityError,
    compute_x9_normalized_0dte_atm_straddle,
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


def _dataset(
    spot: Decimal = Decimal("6000.20"),
    *,
    open_px: Decimal = Decimal("5900"),
    previous_close: Decimal = Decimal("5800"),
) -> PITDecisionSessionDataset:
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
    bars = []
    for index in range(240):
        bar_open = open_px if index == 0 else spot
        bars.append(
            IndexBar1mRecord(
                symbol="SPX",
                session_date_et=SESSION_DATE,
                bar_start_ts_utc=session.open_ts_utc
                + timedelta(minutes=index),
                bar_end_ts_utc=session.open_ts_utc
                + timedelta(minutes=index + 1),
                open=bar_open,
                high=max(bar_open, spot) + Decimal("1"),
                low=min(bar_open, spot) - Decimal("1"),
                close=spot,
                observation_count=10,
                source=SOURCE,
                raw_file_id="bars-raw",
                quality_status=QualityStatus.VALID,
            )
        )
    return build_pit_decision_session_dataset(
        session,
        bars,
        spx_official_prev_close=previous_close,
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
) -> OptionContractRecord:
    return OptionContractRecord(
        contract_id=contract_id,
        vendor_symbol=f"VENDOR-{contract_id}",
        product=product,
        root_symbol="SPXW" if product == "SPX" else product,
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
    *,
    bid: Decimal = Decimal("1.00"),
    ask: Decimal = Decimal("1.10"),
    bid_size: int = 1,
    ask_size: int = 1,
    quote_ts: datetime | None = None,
    raw_file_id: str | None = None,
) -> OptionQuoteRecord:
    return OptionQuoteRecord(
        contract_id=contract.contract_id,
        quote_ts_utc=quote_ts or DECISION - timedelta(seconds=1),
        session_date_et=SESSION_DATE,
        bid_px=bid,
        ask_px=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        bid_exchange="BID",
        ask_exchange="ASK",
        quote_condition=None,
        sequence_no=None,
        source=contract.source,
        raw_file_id=raw_file_id or f"raw-{contract.contract_id}",
    )


def _build_chain(
    contracts: list[OptionContractRecord],
    quotes: list[OptionQuoteRecord],
    *,
    product: str = "SPX",
    expiration_date: date = SESSION_DATE,
    source: str = SOURCE,
) -> DecisionOptionChainSnapshot:
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
) -> tuple[OptionContractRecord, OptionContractRecord]:
    return (
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
    )


def _standard_chain(
    *,
    call_bid: Decimal = Decimal("10.10"),
    call_ask: Decimal = Decimal("10.70"),
    put_bid: Decimal = Decimal("8.20"),
    put_ask: Decimal = Decimal("9.00"),
    call_bid_size: int = 1,
    call_ask_size: int = 1,
    put_bid_size: int = 1,
    put_ask_size: int = 1,
    call_ts: datetime | None = None,
    put_ts: datetime | None = None,
) -> DecisionOptionChainSnapshot:
    call, put = _pair(Decimal("6000"), "ATM")
    return _build_chain(
        [call, put],
        [
            _quote(
                call,
                bid=call_bid,
                ask=call_ask,
                bid_size=call_bid_size,
                ask_size=call_ask_size,
                quote_ts=call_ts,
            ),
            _quote(
                put,
                bid=put_bid,
                ask=put_ask,
                bid_size=put_bid_size,
                ask_size=put_ask_size,
                quote_ts=put_ts,
            ),
        ],
    )


def _snapshot(
    chain: DecisionOptionChainSnapshot,
    contract_id: str,
) -> DecisionOptionSnapshot:
    return next(
        snapshot
        for snapshot in chain.snapshots
        if snapshot.contract.contract_id == contract_id
    )


def _replace_snapshot(
    chain: DecisionOptionChainSnapshot,
    contract_id: str,
    replacement: DecisionOptionSnapshot,
) -> DecisionOptionChainSnapshot:
    return replace(
        chain,
        snapshots=tuple(
            replacement
            if snapshot.contract.contract_id == contract_id
            else snapshot
            for snapshot in chain.snapshots
        ),
    )


def test_x9_001_to_007_public_api_and_return_contract() -> None:
    assert issubclass(OptionFeatureIntegrityError, RuntimeError)
    assert OptionFeatureIntegrityError is not RuntimeError
    signature = inspect.signature(compute_x9_normalized_0dte_atm_straddle)
    assert list(signature.parameters) == ["dataset", "chain"]
    assert option_features.__all__ == (
        "OptionFeatureIntegrityError",
        "compute_x9_normalized_0dte_atm_straddle",
    )
    value = compute_x9_normalized_0dte_atm_straddle(
        _dataset(),
        _standard_chain(),
    )
    assert type(value) is float
    assert math.isfinite(value)
    assert value > 0
    assert compute_x9_normalized_0dte_atm_straddle(
        _dataset(),
        _build_chain([], []),
    ) is None


def test_x9_008_to_018_exact_formula_and_wrong_price_mutants() -> None:
    spot = Decimal("6012.34")
    value = compute_x9_normalized_0dte_atm_straddle(
        _dataset(spot),
        _standard_chain(),
    )
    expected = float(Decimal("19.00") / spot)
    assert value == expected

    wrong_numerators = (
        Decimal("10.10") + Decimal("8.20"),
        Decimal("10.70") + Decimal("9.00"),
        Decimal("10.70") + Decimal("8.20"),
        Decimal("10.10") + Decimal("9.00"),
        Decimal("10.40"),
        Decimal("8.60"),
    )
    assert all(value != float(mutant / spot) for mutant in wrong_numerators)


def test_x9_019_to_020_quote_sizes_do_not_weight_midpoint() -> None:
    spot = Decimal("6000.20")
    value = compute_x9_normalized_0dte_atm_straddle(
        _dataset(spot),
        _standard_chain(
            call_bid_size=1,
            call_ask_size=1000,
            put_bid_size=500,
            put_ask_size=1,
        ),
    )
    assert value == float(Decimal("19.00") / spot)
    call_microprice = (
        Decimal("10.10") * Decimal("1000")
        + Decimal("10.70") * Decimal("1")
    ) / Decimal("1001")
    put_microprice = (
        Decimal("8.20") * Decimal("1")
        + Decimal("9.00") * Decimal("500")
    ) / Decimal("501")
    assert value != float((call_microprice + put_microprice) / spot)


def test_x9_021_to_027_exact_spot_denominator_and_sensitivity() -> None:
    spot_a = Decimal("6000.20")
    spot_b = Decimal("6000.40")
    chain = _standard_chain()
    dataset_a = _dataset(
        spot_a,
        open_px=Decimal("5900"),
        previous_close=Decimal("5800"),
    )
    dataset_b = _dataset(
        spot_b,
        open_px=Decimal("5900"),
        previous_close=Decimal("5800"),
    )
    value_a = compute_x9_normalized_0dte_atm_straddle(dataset_a, chain)
    value_b = compute_x9_normalized_0dte_atm_straddle(dataset_b, chain)
    assert value_a == float(Decimal("19.00") / spot_a)
    assert value_b == float(Decimal("19.00") / spot_b)
    assert value_a != value_b
    wrong_denominators = (
        Decimal("6000"),
        spot_a / Decimal("10"),
        dataset_a.session_state.spx_open,
        dataset_a.session_state.spx_official_prev_close,
    )
    assert all(
        value_a != float(Decimal("19.00") / denominator)
        for denominator in wrong_denominators
    )


def test_x9_028_to_031_same_day_only_and_no_next_expiry_surface() -> None:
    same_day = compute_x9_normalized_0dte_atm_straddle(
        _dataset(),
        _standard_chain(),
    )
    assert same_day is not None

    call, put = _pair(
        Decimal("6000"),
        "FUTURE",
        expiration_date=FUTURE_EXPIRY,
    )
    future_chain = _build_chain(
        [call, put],
        [_quote(call), _quote(put)],
        expiration_date=FUTURE_EXPIRY,
    )
    with pytest.raises(OptionFeatureIntegrityError, match="session date"):
        compute_x9_normalized_0dte_atm_straddle(_dataset(), future_chain)
    assert {"next_expiry", "select_next_expiry"}.isdisjoint(
        vars(option_features)
    )


def test_x9_032_to_035_selector_called_once_with_exact_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = _dataset()
    chain = _standard_chain()
    authoritative = select_spx_atm_call_put_pair(dataset, chain)
    observed: list[tuple[object, object]] = []

    def spy(
        observed_dataset: PITDecisionSessionDataset,
        observed_chain: DecisionOptionChainSnapshot,
    ) -> ATMCallPutPairSelection | None:
        observed.append((observed_dataset, observed_chain))
        return authoritative

    monkeypatch.setattr(
        option_features,
        "select_spx_atm_call_put_pair",
        spy,
    )
    assert compute_x9_normalized_0dte_atm_straddle(dataset, chain) is not None
    assert observed == [(dataset, chain)]
    assert {"select_atm", "nearest_strike", "spx_spot"}.isdisjoint(
        vars(option_features)
    )


def test_x9_036_to_037_selector_output_is_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    near_call, near_put = _pair(Decimal("6000"), "NEAR")
    far_call, far_put = _pair(Decimal("6010"), "FAR")
    chain = _build_chain(
        [near_call, near_put, far_call, far_put],
        [
            _quote(near_call, bid=Decimal("1"), ask=Decimal("2")),
            _quote(near_put, bid=Decimal("2"), ask=Decimal("3")),
            _quote(far_call, bid=Decimal("10"), ask=Decimal("12")),
            _quote(far_put, bid=Decimal("8"), ask=Decimal("10")),
        ],
    )
    dataset = _dataset(Decimal("6000.20"))
    far_selection = ATMCallPutPairSelection(
        strike=Decimal("6010"),
        call_snapshot=_snapshot(chain, "FAR-CALL"),
        put_snapshot=_snapshot(chain, "FAR-PUT"),
    )
    monkeypatch.setattr(
        option_features,
        "select_spx_atm_call_put_pair",
        lambda supplied_dataset, supplied_chain: far_selection,
    )
    value = compute_x9_normalized_0dte_atm_straddle(dataset, chain)
    assert value == float(Decimal("20") / Decimal("6000.20"))
    assert value != float(Decimal("4") / Decimal("6000.20"))


def test_x9_038_to_044_empty_missing_sides_and_missing_snapshot_return_none() -> None:
    dataset = _dataset()
    assert compute_x9_normalized_0dte_atm_straddle(
        dataset,
        _build_chain([], []),
    ) is None

    near_put = _contract("NEAR-PUT", Decimal("6000"), OptionType.PUT)
    far_call, far_put = _pair(Decimal("6005"), "FAR")
    missing_call_chain = _build_chain(
        [near_put, far_call, far_put],
        [_quote(near_put), _quote(far_call), _quote(far_put)],
    )
    assert compute_x9_normalized_0dte_atm_straddle(
        dataset,
        missing_call_chain,
    ) is None

    near_call = _contract("NEAR-CALL", Decimal("6000"), OptionType.CALL)
    missing_put_chain = _build_chain(
        [near_call, far_call, far_put],
        [_quote(near_call), _quote(far_call), _quote(far_put)],
    )
    assert compute_x9_normalized_0dte_atm_straddle(
        dataset,
        missing_put_chain,
    ) is None

    call, put = _pair(Decimal("6000"), "MISSING")
    missing_snapshot_chain = _build_chain([call, put], [_quote(put)])
    assert _snapshot(
        missing_snapshot_chain,
        "MISSING-CALL",
    ).quality_status is QualityStatus.MISSING
    assert compute_x9_normalized_0dte_atm_straddle(
        dataset,
        missing_snapshot_chain,
    ) is None


@pytest.mark.parametrize(
    "quality",
    [
        QualityStatus.MISSING,
        QualityStatus.STALE,
        QualityStatus.CROSSED,
        QualityStatus.LOCKED,
        QualityStatus.ZERO_BID,
        QualityStatus.ZERO_SIZE,
        QualityStatus.OUT_OF_ORDER,
        QualityStatus.DUPLICATE,
        QualityStatus.HALTED,
        QualityStatus.UNKNOWN,
    ],
)
def test_x9_045_every_non_valid_selected_leg_returns_none(
    quality: QualityStatus,
) -> None:
    call, put = _pair(Decimal("6000"), "ATM")
    call_quote: OptionQuoteRecord | None
    if quality is QualityStatus.MISSING:
        call_quote = None
    elif quality is QualityStatus.STALE:
        call_quote = _quote(
            call,
            quote_ts=DECISION - timedelta(microseconds=2_001_000),
        )
    elif quality is QualityStatus.CROSSED:
        call_quote = _quote(call, bid=Decimal("2"), ask=Decimal("1"))
    elif quality is QualityStatus.LOCKED:
        call_quote = _quote(call, bid=Decimal("1"), ask=Decimal("1"))
    elif quality is QualityStatus.ZERO_BID:
        call_quote = _quote(call, bid=Decimal("0"), ask=Decimal("1"))
    elif quality is QualityStatus.ZERO_SIZE:
        call_quote = _quote(call, bid_size=0)
    else:
        call_quote = _quote(call)

    quotes = [_quote(put)]
    if call_quote is not None:
        quotes.append(call_quote)
    chain = _build_chain([call, put], quotes)
    call_snapshot = _snapshot(chain, "ATM-CALL")
    if quality in {
        QualityStatus.OUT_OF_ORDER,
        QualityStatus.DUPLICATE,
        QualityStatus.HALTED,
        QualityStatus.UNKNOWN,
    }:
        call_snapshot = replace(call_snapshot, quality_status=quality)
        chain = _replace_snapshot(chain, "ATM-CALL", call_snapshot)
    assert call_snapshot.quality_status is quality
    assert compute_x9_normalized_0dte_atm_straddle(_dataset(), chain) is None


def test_x9_046_to_049_both_legs_must_be_valid() -> None:
    dataset = _dataset()
    valid = _standard_chain()
    call = _snapshot(valid, "ATM-CALL")
    put = _snapshot(valid, "ATM-PUT")
    call_invalid = _replace_snapshot(
        valid,
        "ATM-CALL",
        replace(call, quality_status=QualityStatus.HALTED),
    )
    put_invalid = _replace_snapshot(
        valid,
        "ATM-PUT",
        replace(put, quality_status=QualityStatus.UNKNOWN),
    )
    both_invalid = _replace_snapshot(
        call_invalid,
        "ATM-PUT",
        replace(put, quality_status=QualityStatus.UNKNOWN),
    )
    assert compute_x9_normalized_0dte_atm_straddle(
        dataset,
        call_invalid,
    ) is None
    assert compute_x9_normalized_0dte_atm_straddle(
        dataset,
        put_invalid,
    ) is None
    assert compute_x9_normalized_0dte_atm_straddle(
        dataset,
        both_invalid,
    ) is None
    assert compute_x9_normalized_0dte_atm_straddle(dataset, valid) is not None


def test_x9_050_to_052_invalid_atm_and_lower_tie_never_fall_back() -> None:
    low_call, low_put = _pair(Decimal("6000"), "LOW")
    high_call, high_put = _pair(Decimal("6005"), "HIGH")
    chain = _build_chain(
        [low_call, low_put, high_call, high_put],
        [
            _quote(low_call),
            _quote(low_put, bid=Decimal("2"), ask=Decimal("1")),
            _quote(high_call, bid=Decimal("10"), ask=Decimal("12")),
            _quote(high_put, bid=Decimal("8"), ask=Decimal("10")),
        ],
    )
    assert compute_x9_normalized_0dte_atm_straddle(
        _dataset(Decimal("6000.20")),
        chain,
    ) is None
    assert compute_x9_normalized_0dte_atm_straddle(
        _dataset(Decimal("6002.50")),
        chain,
    ) is None


def test_x9_053_to_054_frozen_two_second_quality_boundary() -> None:
    at_boundary = _standard_chain(
        call_ts=DECISION - timedelta(seconds=2),
        put_ts=DECISION - timedelta(seconds=2),
    )
    stale = _standard_chain(
        call_ts=DECISION - timedelta(microseconds=2_001_000),
        put_ts=DECISION - timedelta(seconds=2),
    )
    assert compute_x9_normalized_0dte_atm_straddle(
        _dataset(),
        at_boundary,
    ) is not None
    assert compute_x9_normalized_0dte_atm_straddle(
        _dataset(),
        stale,
    ) is None


def test_x9_055_to_056_latest_invalid_quote_has_no_earlier_valid_fallback() -> None:
    call, put = _pair(Decimal("6000"), "ATM")
    earlier_valid = _quote(
        call,
        quote_ts=DECISION - timedelta(seconds=2),
        raw_file_id="earlier-valid",
    )
    later_crossed = _quote(
        call,
        bid=Decimal("2"),
        ask=Decimal("1"),
        quote_ts=DECISION - timedelta(seconds=1),
        raw_file_id="later-crossed",
    )
    chain = _build_chain(
        [call, put],
        [earlier_valid, later_crossed, _quote(put)],
    )
    selected = _snapshot(chain, "ATM-CALL")
    assert selected.selected_quote is later_crossed
    assert selected.quality_status is QualityStatus.CROSSED
    assert compute_x9_normalized_0dte_atm_straddle(_dataset(), chain) is None


@pytest.mark.parametrize("defect", ["missing", "source", "contract"])
def test_x9_057_to_059_valid_snapshot_integrity_hard_fails(
    defect: str,
) -> None:
    chain = _standard_chain()
    call = _snapshot(chain, "ATM-CALL")
    assert call.selected_quote is not None
    if defect == "missing":
        malformed = replace(call, selected_quote=None)
    elif defect == "source":
        malformed = replace(
            call,
            selected_quote=call.selected_quote.model_copy(
                update={"source": "OTHER_SOURCE"}
            ),
        )
    else:
        malformed = replace(
            call,
            selected_quote=call.selected_quote.model_copy(
                update={"contract_id": "OTHER_CONTRACT"}
            ),
        )
    with pytest.raises(OptionFeatureIntegrityError):
        compute_x9_normalized_0dte_atm_straddle(
            _dataset(),
            _replace_snapshot(chain, "ATM-CALL", malformed),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bid_px", Decimal("NaN")),
        ("ask_px", Decimal("Infinity")),
        ("bid_px", Decimal("0")),
        ("bid_px", Decimal("-1")),
        ("ask_px", Decimal("10.10")),
        ("bid_px", 10.10),
        ("ask_px", 10.70),
    ],
)
def test_x9_060_to_063_valid_price_input_integrity_hard_fails(
    field: str,
    value: object,
) -> None:
    chain = _standard_chain()
    call = _snapshot(chain, "ATM-CALL")
    assert call.selected_quote is not None
    malformed = replace(
        call,
        selected_quote=call.selected_quote.model_copy(update={field: value}),
    )
    with pytest.raises(OptionFeatureIntegrityError):
        compute_x9_normalized_0dte_atm_straddle(
            _dataset(),
            _replace_snapshot(chain, "ATM-CALL", malformed),
        )


def test_x9_064_to_068_no_rounding_scaling_annualization_or_epsilon() -> None:
    spot = Decimal("6000.123456789012345678")
    call_bid = Decimal("10.123456789012345678")
    call_ask = Decimal("10.765432109876543210")
    put_bid = Decimal("8.234567890123456789")
    put_ask = Decimal("9.012345678901234567")
    numerator = (
        (call_bid + call_ask) / Decimal("2")
        + (put_bid + put_ask) / Decimal("2")
    )
    expected = float(numerator / spot)
    value = compute_x9_normalized_0dte_atm_straddle(
        _dataset(spot),
        _standard_chain(
            call_bid=call_bid,
            call_ask=call_ask,
            put_bid=put_bid,
            put_ask=put_ask,
        ),
    )
    assert value == expected
    assert value != round(expected, 6)
    assert value != expected * 100
    assert value != expected * 10_000
    assert value != expected * math.sqrt(252)
    assert value != float(numerator / (spot + Decimal("1e-8")))


@pytest.mark.parametrize(
    "defect",
    ["xsp", "am", "timestamp", "multiple_call", "multiple_put"],
)
def test_x9_069_to_073_structural_selector_errors_propagate(
    defect: str,
) -> None:
    dataset = _dataset()
    if defect == "xsp":
        call, put = _pair(Decimal("600"), "XSP", product="XSP")
        chain = _build_chain(
            [call, put],
            [_quote(call), _quote(put)],
            product="XSP",
        )
    else:
        chain = _standard_chain()
        if defect == "am":
            chain = replace(chain, settlement_style=SettlementStyle.AM)
        elif defect == "timestamp":
            chain = replace(
                chain,
                decision_ts_utc=chain.decision_ts_utc
                + timedelta(microseconds=1),
            )
        else:
            duplicate_type = (
                OptionType.CALL
                if defect == "multiple_call"
                else OptionType.PUT
            )
            duplicate = _contract(
                "DUPLICATE-SIDE",
                Decimal("6000"),
                duplicate_type,
            )
            original_contracts = [
                snapshot.contract for snapshot in chain.snapshots
            ]
            original_quotes = [
                snapshot.selected_quote
                for snapshot in chain.snapshots
                if snapshot.selected_quote is not None
            ]
            chain = _build_chain(
                [*original_contracts, duplicate],
                [*original_quotes, _quote(duplicate)],
            )
    with pytest.raises(ATMCallPutPairSelectionIntegrityError):
        compute_x9_normalized_0dte_atm_straddle(dataset, chain)


def test_x9_074_to_080_no_premature_surface_and_inputs_are_not_mutated() -> None:
    forbidden = {
        "compute_x10",
        "compute_x11",
        "select_next_expiry",
        "FeatureVector",
        "feature_snapshots",
        "execution_price",
        "black_scholes",
        "implied_volatility",
    }
    assert forbidden.isdisjoint(vars(option_features))
    dataset = _dataset()
    chain = _standard_chain()
    dataset_before = dataset
    chain_before = chain
    assert compute_x9_normalized_0dte_atm_straddle(dataset, chain) is not None
    assert dataset == dataset_before
    assert chain == chain_before


def test_final_float_must_remain_finite() -> None:
    chain = _standard_chain()
    call = _snapshot(chain, "ATM-CALL")
    assert call.selected_quote is not None
    huge_quote = call.selected_quote.model_copy(
        update={
            "bid_px": Decimal("1e999"),
            "ask_px": Decimal("2e999"),
        }
    )
    malformed = replace(call, selected_quote=huge_quote)
    with pytest.raises(OptionFeatureIntegrityError, match="finite"):
        compute_x9_normalized_0dte_atm_straddle(
            _dataset(),
            _replace_snapshot(chain, "ATM-CALL", malformed),
        )
