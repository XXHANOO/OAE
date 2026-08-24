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
    compute_x10_price_based_downside_skew,
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

ATM_CALL = "ATM-CALL"
ATM_PUT = "ATM-PUT"
TARGET_PUT = "TARGET-PUT"
TARGET_CALL = "TARGET-CALL"


def _dataset(spot: Decimal = Decimal("6000")) -> PITDecisionSessionDataset:
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


def _mid_quote(
    contract: OptionContractRecord,
    mid: Decimal,
    **kwargs: object,
) -> OptionQuoteRecord:
    return _quote(
        contract,
        bid=mid - Decimal("0.10"),
        ask=mid + Decimal("0.10"),
        **kwargs,
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


def _standard_chain(
    *,
    expiration_date: date = SESSION_DATE,
    price_overrides: dict[str, tuple[Decimal, Decimal]] | None = None,
    quote_times: dict[str, datetime] | None = None,
    quote_sizes: dict[str, tuple[int, int]] | None = None,
    missing_quotes: frozenset[str] = frozenset(),
    extra_contracts: tuple[OptionContractRecord, ...] = (),
    extra_quotes: tuple[OptionQuoteRecord, ...] = (),
) -> DecisionOptionChainSnapshot:
    contracts = {
        ATM_CALL: _contract(
            ATM_CALL,
            Decimal("6000"),
            OptionType.CALL,
            expiration_date=expiration_date,
        ),
        ATM_PUT: _contract(
            ATM_PUT,
            Decimal("6000"),
            OptionType.PUT,
            expiration_date=expiration_date,
        ),
        TARGET_PUT: _contract(
            TARGET_PUT,
            Decimal("5970"),
            OptionType.PUT,
            expiration_date=expiration_date,
        ),
        TARGET_CALL: _contract(
            TARGET_CALL,
            Decimal("6030"),
            OptionType.CALL,
            expiration_date=expiration_date,
        ),
    }
    prices = {
        ATM_CALL: (Decimal("10.10"), Decimal("10.70")),
        ATM_PUT: (Decimal("8.20"), Decimal("9.00")),
        TARGET_PUT: (Decimal("12.20"), Decimal("12.80")),
        TARGET_CALL: (Decimal("7.10"), Decimal("7.90")),
    }
    prices.update(price_overrides or {})
    times = quote_times or {}
    sizes = quote_sizes or {}
    quotes = [
        _quote(
            contract,
            bid=prices[contract_id][0],
            ask=prices[contract_id][1],
            bid_size=sizes.get(contract_id, (1, 1))[0],
            ask_size=sizes.get(contract_id, (1, 1))[1],
            quote_ts=times.get(contract_id),
        )
        for contract_id, contract in contracts.items()
        if contract_id not in missing_quotes
    ]
    return _build_chain(
        [*contracts.values(), *extra_contracts],
        [*quotes, *extra_quotes],
        expiration_date=expiration_date,
    )


def _selection_chain(
    puts: tuple[tuple[str, Decimal, Decimal], ...],
    calls: tuple[tuple[str, Decimal, Decimal], ...],
) -> DecisionOptionChainSnapshot:
    atm_call = _contract(ATM_CALL, Decimal("6000"), OptionType.CALL)
    atm_put = _contract(ATM_PUT, Decimal("6000"), OptionType.PUT)
    side_contracts = [
        *(
            _contract(contract_id, strike, OptionType.PUT)
            for contract_id, strike, _ in puts
        ),
        *(
            _contract(contract_id, strike, OptionType.CALL)
            for contract_id, strike, _ in calls
        ),
    ]
    mids = {
        contract_id: mid
        for contract_id, _, mid in (*puts, *calls)
    }
    return _build_chain(
        [atm_call, atm_put, *side_contracts],
        [
            _mid_quote(atm_call, Decimal("2")),
            _mid_quote(atm_put, Decimal("3")),
            *(_mid_quote(contract, mids[contract.contract_id]) for contract in side_contracts),
        ],
    )


def _with_quality(
    chain: DecisionOptionChainSnapshot,
    contract_id: str,
    quality: QualityStatus,
) -> DecisionOptionChainSnapshot:
    snapshot = _snapshot(chain, contract_id)
    if quality is QualityStatus.MISSING:
        replacement = replace(
            snapshot,
            selected_quote=None,
            quote_age_seconds=None,
            quality_status=quality,
        )
    else:
        replacement = replace(snapshot, quality_status=quality)
    return _replace_snapshot(chain, contract_id, replacement)


def test_x10_001_to_007_public_api_return_contract_and_x9_survival() -> None:
    assert option_features.__all__ == (
        "OptionFeatureIntegrityError",
        "compute_x9_normalized_0dte_atm_straddle",
        "compute_x10_price_based_downside_skew",
    )
    signature = inspect.signature(compute_x10_price_based_downside_skew)
    assert list(signature.parameters) == ["dataset", "chain"]
    assert all(
        parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        for parameter in signature.parameters.values()
    )
    assert option_features.OptionFeatureIntegrityError is OptionFeatureIntegrityError
    assert issubclass(OptionFeatureIntegrityError, RuntimeError)
    assert not any(
        name.endswith("IntegrityError") and name != "OptionFeatureIntegrityError"
        for name in option_features.__all__
    )

    dataset = _dataset()
    chain = _standard_chain()
    value = compute_x10_price_based_downside_skew(dataset, chain)
    assert type(value) is float
    assert value == float(Decimal("5.00") / Decimal("19.00"))
    assert compute_x10_price_based_downside_skew(
        dataset,
        _build_chain([], []),
    ) is None
    assert compute_x9_normalized_0dte_atm_straddle(dataset, chain) == float(
        Decimal("19.00") / Decimal("6000")
    )


def test_x10_008_to_011_exact_noninteger_targets_use_spot_without_rounding() -> None:
    spot = Decimal("6000.2")
    chain = _selection_chain(
        (
            ("PUT-ROUND-MUTANT", Decimal("5969.9"), Decimal("2")),
            ("PUT-EXACT", Decimal("5970.2"), Decimal("8")),
        ),
        (
            ("CALL-ROUND-MUTANT", Decimal("6029.9"), Decimal("1")),
            ("CALL-EXACT", Decimal("6030.2"), Decimal("3")),
        ),
    )
    assert Decimal("0.995") * spot == Decimal("5970.199")
    assert Decimal("1.005") * spot == Decimal("6030.201")
    value = compute_x10_price_based_downside_skew(_dataset(spot), chain)
    assert value == float(Decimal("5") / Decimal("5"))
    assert value != float(Decimal("1") / Decimal("5"))


def test_x10_exact_decimal_targets_kill_float_arithmetic_mutant() -> None:
    spot = Decimal("6000.123456789012345678")
    put_target = Decimal("0.995") * spot
    call_target = Decimal("1.005") * spot
    chain = _selection_chain(
        (
            ("PUT-LOW", put_target - Decimal("1e-13"), Decimal("4")),
            ("PUT-HIGH", put_target + Decimal("1e-13"), Decimal("8")),
        ),
        (
            ("CALL-LOW", call_target - Decimal("2e-13"), Decimal("1")),
            ("CALL-HIGH", call_target + Decimal("1e-13"), Decimal("3")),
        ),
    )
    value = compute_x10_price_based_downside_skew(_dataset(spot), chain)
    assert value == float(Decimal("1") / Decimal("5"))
    assert value != float(Decimal("7") / Decimal("5"))


@pytest.mark.parametrize(
    ("puts", "expected_mid"),
    [
        (
            (
                ("PUT-LOW", Decimal("5969"), Decimal("4")),
                ("PUT-HIGH", Decimal("5972"), Decimal("8")),
                ("PUT-FAR", Decimal("5950"), Decimal("12")),
            ),
            Decimal("4"),
        ),
        (
            (
                ("PUT-LOW", Decimal("5968"), Decimal("4")),
                ("PUT-HIGH", Decimal("5971"), Decimal("8")),
                ("PUT-FAR", Decimal("5990"), Decimal("12")),
            ),
            Decimal("8"),
        ),
    ],
)
def test_x10_012_to_015_put_selection_is_side_specific_and_strictly_nearest(
    puts: tuple[tuple[str, Decimal, Decimal], ...],
    expected_mid: Decimal,
) -> None:
    calls = (
        ("CALL-AT-PUT-TARGET", Decimal("5970"), Decimal("99")),
        ("TARGET-CALL", Decimal("6030"), Decimal("3")),
    )
    value = compute_x10_price_based_downside_skew(
        _dataset(),
        _selection_chain(puts, calls),
    )
    assert value == float((expected_mid - Decimal("3")) / Decimal("5"))


@pytest.mark.parametrize(
    ("calls", "expected_mid"),
    [
        (
            (
                ("CALL-LOW", Decimal("6029"), Decimal("2")),
                ("CALL-HIGH", Decimal("6032"), Decimal("6")),
                ("CALL-FAR", Decimal("6050"), Decimal("10")),
            ),
            Decimal("2"),
        ),
        (
            (
                ("CALL-LOW", Decimal("6028"), Decimal("2")),
                ("CALL-HIGH", Decimal("6031"), Decimal("6")),
                ("CALL-FAR", Decimal("6010"), Decimal("10")),
            ),
            Decimal("6"),
        ),
    ],
)
def test_x10_016_to_019_call_selection_is_side_specific_and_strictly_nearest(
    calls: tuple[tuple[str, Decimal, Decimal], ...],
    expected_mid: Decimal,
) -> None:
    puts = (
        ("TARGET-PUT", Decimal("5970"), Decimal("8")),
        ("PUT-AT-CALL-TARGET", Decimal("6030"), Decimal("99")),
    )
    value = compute_x10_price_based_downside_skew(
        _dataset(),
        _selection_chain(puts, calls),
    )
    assert value == float((Decimal("8") - expected_mid) / Decimal("5"))


def test_x10_020_to_025_lower_tie_wins_for_both_sides_in_any_order() -> None:
    chain = _selection_chain(
        (
            ("PUT-LOW", Decimal("5965"), Decimal("8")),
            ("PUT-HIGH", Decimal("5975"), Decimal("20")),
        ),
        (
            ("CALL-LOW", Decimal("6025"), Decimal("3")),
            ("CALL-HIGH", Decimal("6035"), Decimal("30")),
        ),
    )
    dataset = _dataset()
    expected = float(Decimal("5") / Decimal("5"))
    assert compute_x10_price_based_downside_skew(dataset, chain) == expected
    assert compute_x10_price_based_downside_skew(
        dataset,
        replace(chain, snapshots=tuple(reversed(chain.snapshots))),
    ) == expected
    higher_tie_mutant = float((Decimal("20") - Decimal("30")) / Decimal("5"))
    assert expected != higher_tie_mutant


def test_x10_026_to_027_no_put_floor_or_call_ceiling_filter() -> None:
    chain = _selection_chain(
        (
            ("PUT-ABOVE", Decimal("5972"), Decimal("8")),
            ("PUT-FLOOR", Decimal("5960"), Decimal("20")),
        ),
        (
            ("CALL-BELOW", Decimal("6028"), Decimal("3")),
            ("CALL-CEILING", Decimal("6040"), Decimal("30")),
        ),
    )
    assert compute_x10_price_based_downside_skew(
        _dataset(),
        chain,
    ) == float(Decimal("5") / Decimal("5"))


def test_x10_028_to_042_exact_formula_and_denominator_mutants() -> None:
    spot = Decimal("6000.2")
    value = compute_x10_price_based_downside_skew(
        _dataset(spot),
        _standard_chain(),
    )
    numerator = Decimal("12.50") - Decimal("7.50")
    denominator = Decimal("10.40") + Decimal("8.60")
    assert value == float(numerator / denominator)

    wrong_numerators = (
        Decimal("7.50") - Decimal("12.50"),
        Decimal("12.50") + Decimal("7.50"),
        Decimal("12.50"),
        Decimal("7.50"),
    )
    assert all(value != float(mutant / denominator) for mutant in wrong_numerators)
    wrong_denominators = (
        spot,
        Decimal("6000"),
        denominator / spot,
        Decimal("12.50") + Decimal("7.50"),
        Decimal("10.40"),
        Decimal("8.60"),
    )
    assert all(value != float(numerator / mutant) for mutant in wrong_denominators)


@pytest.mark.parametrize(
    ("put_mid", "call_mid", "expected"),
    [
        (Decimal("12.5"), Decimal("7.5"), Decimal("5") / Decimal("19")),
        (Decimal("7.5"), Decimal("7.5"), Decimal("0")),
        (Decimal("5.0"), Decimal("7.5"), Decimal("-2.5") / Decimal("19")),
    ],
)
def test_x10_043_to_048_signed_positive_zero_and_negative_are_valid(
    put_mid: Decimal,
    call_mid: Decimal,
    expected: Decimal,
) -> None:
    chain = _standard_chain(
        price_overrides={
            TARGET_PUT: (put_mid - Decimal("0.1"), put_mid + Decimal("0.1")),
            TARGET_CALL: (
                call_mid - Decimal("0.1"),
                call_mid + Decimal("0.1"),
            ),
        }
    )
    value = compute_x10_price_based_downside_skew(_dataset(), chain)
    assert value == float(expected)
    assert type(value) is float
    if expected < 0:
        assert value is not None and value < 0
        assert value != abs(value)
    if expected == 0:
        assert value == 0.0


def test_x10_049_to_052_atm_selector_called_once_with_exact_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset = _dataset()
    chain = _standard_chain()
    authoritative = select_spx_atm_call_put_pair(dataset, chain)
    observed: list[tuple[object, object]] = []

    def spy(
        supplied_dataset: PITDecisionSessionDataset,
        supplied_chain: DecisionOptionChainSnapshot,
    ) -> ATMCallPutPairSelection | None:
        observed.append((supplied_dataset, supplied_chain))
        return authoritative

    monkeypatch.setattr(option_features, "select_spx_atm_call_put_pair", spy)
    assert compute_x10_price_based_downside_skew(dataset, chain) is not None
    assert observed == [(dataset, chain)]
    assert {
        "select_atm",
        "nearest_atm_strike",
        "select_valid_atm_pair",
    }.isdisjoint(vars(option_features))


def test_x10_053_to_054_selector_atm_denominator_is_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alt_call = _contract("ALT-CALL", Decimal("6010"), OptionType.CALL)
    alt_put = _contract("ALT-PUT", Decimal("6010"), OptionType.PUT)
    chain = _standard_chain(
        extra_contracts=(alt_call, alt_put),
        extra_quotes=(
            _mid_quote(alt_call, Decimal("30")),
            _mid_quote(alt_put, Decimal("20")),
        ),
    )
    controlled = ATMCallPutPairSelection(
        strike=Decimal("6010"),
        call_snapshot=_snapshot(chain, "ALT-CALL"),
        put_snapshot=_snapshot(chain, "ALT-PUT"),
    )
    observed = 0

    def controlled_selector(
        supplied_dataset: PITDecisionSessionDataset,
        supplied_chain: DecisionOptionChainSnapshot,
    ) -> ATMCallPutPairSelection:
        nonlocal observed
        observed += 1
        assert supplied_chain is chain
        return controlled

    monkeypatch.setattr(
        option_features,
        "select_spx_atm_call_put_pair",
        controlled_selector,
    )
    value = compute_x10_price_based_downside_skew(_dataset(), chain)
    assert observed == 1
    assert value == float(Decimal("5") / Decimal("50"))
    assert value != float(Decimal("5") / Decimal("19"))


def test_x10_055_to_056_decimal_denominator_never_reconstructed_from_x9(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spot = Decimal("6000.123456789012345678")
    prices = {
        ATM_CALL: (
            Decimal("10.123456789012345678"),
            Decimal("10.765432109876543210"),
        ),
        ATM_PUT: (
            Decimal("8.234567890123456789"),
            Decimal("9.012345678901234567"),
        ),
        TARGET_PUT: (
            Decimal("12.234567890123456789"),
            Decimal("12.876543210987654321"),
        ),
        TARGET_CALL: (
            Decimal("7.123456789012345678"),
            Decimal("7.987654321098765432"),
        ),
    }
    chain = _standard_chain(price_overrides=prices)
    denominator = sum(
        (
            (prices[ATM_CALL][0] + prices[ATM_CALL][1]) / Decimal("2"),
            (prices[ATM_PUT][0] + prices[ATM_PUT][1]) / Decimal("2"),
        ),
        Decimal("0"),
    )
    numerator = (
        (prices[TARGET_PUT][0] + prices[TARGET_PUT][1]) / Decimal("2")
        - (prices[TARGET_CALL][0] + prices[TARGET_CALL][1]) / Decimal("2")
    )
    x9_float = float(denominator / spot)
    reconstructed_denominator = Decimal(str(x9_float)) * spot

    def forbidden_x9(*args: object, **kwargs: object) -> float:
        raise AssertionError("x10 must not call or reconstruct its denominator from x9")

    monkeypatch.setattr(
        option_features,
        "compute_x9_normalized_0dte_atm_straddle",
        forbidden_x9,
    )
    value = compute_x10_price_based_downside_skew(_dataset(spot), chain)
    assert value == float(numerator / denominator)
    assert value != float(numerator / reconstructed_denominator)


def test_x10_057_to_059_quote_sizes_never_weight_any_midpoint() -> None:
    sizes = {
        ATM_CALL: (1, 1000),
        ATM_PUT: (500, 1),
        TARGET_PUT: (1, 999),
        TARGET_CALL: (777, 1),
    }
    value = compute_x10_price_based_downside_skew(
        _dataset(),
        _standard_chain(quote_sizes=sizes),
    )
    assert value == float(Decimal("5") / Decimal("19"))


def test_x10_060_closest_invalid_put_does_not_fall_back() -> None:
    far_put = _contract("FAR-PUT", Decimal("5960"), OptionType.PUT)
    chain = _standard_chain(
        price_overrides={TARGET_PUT: (Decimal("2"), Decimal("1"))},
        extra_contracts=(far_put,),
        extra_quotes=(_mid_quote(far_put, Decimal("30")),),
    )
    assert _snapshot(chain, TARGET_PUT).quality_status is QualityStatus.CROSSED
    assert compute_x10_price_based_downside_skew(_dataset(), chain) is None


def test_x10_061_closest_invalid_call_does_not_fall_back() -> None:
    far_call = _contract("FAR-CALL", Decimal("6040"), OptionType.CALL)
    chain = _standard_chain(
        quote_times={
            TARGET_CALL: DECISION - timedelta(microseconds=2_001_000),
        },
        extra_contracts=(far_call,),
        extra_quotes=(_mid_quote(far_call, Decimal("30")),),
    )
    assert _snapshot(chain, TARGET_CALL).quality_status is QualityStatus.STALE
    assert compute_x10_price_based_downside_skew(_dataset(), chain) is None


def test_x10_062_put_tie_keeps_invalid_lower_strike() -> None:
    chain = _selection_chain(
        (
            ("PUT-LOW", Decimal("5965"), Decimal("8")),
            ("PUT-HIGH", Decimal("5975"), Decimal("30")),
        ),
        ((TARGET_CALL, Decimal("6030"), Decimal("3")),),
    )
    chain = _with_quality(chain, "PUT-LOW", QualityStatus.MISSING)
    assert _snapshot(chain, "PUT-LOW").quality_status is QualityStatus.MISSING
    assert compute_x10_price_based_downside_skew(_dataset(), chain) is None


def test_x10_063_call_tie_keeps_invalid_lower_strike() -> None:
    chain = _selection_chain(
        ((TARGET_PUT, Decimal("5970"), Decimal("8")),),
        (
            ("CALL-LOW", Decimal("6025"), Decimal("3")),
            ("CALL-HIGH", Decimal("6035"), Decimal("30")),
        ),
    )
    chain = _with_quality(chain, "CALL-LOW", QualityStatus.CROSSED)
    assert _snapshot(chain, "CALL-LOW").quality_status is QualityStatus.CROSSED
    assert compute_x10_price_based_downside_skew(_dataset(), chain) is None


@pytest.mark.parametrize(
    "invalid_roles",
    [
        (ATM_CALL,),
        (ATM_PUT,),
        (ATM_CALL, ATM_PUT),
    ],
)
def test_x10_064_to_066_invalid_atm_roles_return_none(
    invalid_roles: tuple[str, ...],
) -> None:
    chain = _standard_chain()
    for contract_id in invalid_roles:
        chain = _with_quality(chain, contract_id, QualityStatus.HALTED)
    assert compute_x10_price_based_downside_skew(_dataset(), chain) is None


def test_x10_067_invalid_atm_never_falls_back_to_far_valid_pair() -> None:
    far_call = _contract("FAR-ATM-CALL", Decimal("6005"), OptionType.CALL)
    far_put = _contract("FAR-ATM-PUT", Decimal("6005"), OptionType.PUT)
    chain = _standard_chain(
        price_overrides={ATM_PUT: (Decimal("2"), Decimal("1"))},
        extra_contracts=(far_call, far_put),
        extra_quotes=(
            _mid_quote(far_call, Decimal("30")),
            _mid_quote(far_put, Decimal("40")),
        ),
    )
    assert compute_x10_price_based_downside_skew(_dataset(), chain) is None


def test_x10_068_to_069_missing_candidate_side_returns_none() -> None:
    only_calls = [
        _contract(ATM_CALL, Decimal("6000"), OptionType.CALL),
        _contract(TARGET_CALL, Decimal("6030"), OptionType.CALL),
    ]
    only_puts = [
        _contract(ATM_PUT, Decimal("6000"), OptionType.PUT),
        _contract(TARGET_PUT, Decimal("5970"), OptionType.PUT),
    ]
    assert compute_x10_price_based_downside_skew(
        _dataset(),
        _build_chain(only_calls, [_mid_quote(c, Decimal("2")) for c in only_calls]),
    ) is None
    assert compute_x10_price_based_downside_skew(
        _dataset(),
        _build_chain(only_puts, [_mid_quote(c, Decimal("2")) for c in only_puts]),
    ) is None


@pytest.mark.parametrize("target_id", [TARGET_PUT, TARGET_CALL])
def test_x10_070_to_071_missing_selected_quote_never_uses_farther_contract(
    target_id: str,
) -> None:
    option_type = OptionType.PUT if target_id == TARGET_PUT else OptionType.CALL
    farther_strike = Decimal("5960") if option_type is OptionType.PUT else Decimal("6040")
    farther = _contract(f"FAR-{option_type.name}", farther_strike, option_type)
    chain = _standard_chain(
        missing_quotes=frozenset({target_id}),
        extra_contracts=(farther,),
        extra_quotes=(_mid_quote(farther, Decimal("30")),),
    )
    assert _snapshot(chain, target_id).quality_status is QualityStatus.MISSING
    assert compute_x10_price_based_downside_skew(_dataset(), chain) is None


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
@pytest.mark.parametrize(
    "required_role",
    [ATM_CALL, ATM_PUT, TARGET_PUT, TARGET_CALL],
)
def test_x10_072_every_non_valid_required_role_returns_none(
    quality: QualityStatus,
    required_role: str,
) -> None:
    chain = _with_quality(_standard_chain(), required_role, quality)
    assert compute_x10_price_based_downside_skew(_dataset(), chain) is None


def test_x10_073_to_076_frozen_two_second_boundary_is_consumed_upstream() -> None:
    at_boundary = {
        contract_id: DECISION - timedelta(seconds=2)
        for contract_id in (ATM_CALL, ATM_PUT, TARGET_PUT, TARGET_CALL)
    }
    assert compute_x10_price_based_downside_skew(
        _dataset(),
        _standard_chain(quote_times=at_boundary),
    ) == float(Decimal("5") / Decimal("19"))
    for stale_role in (TARGET_PUT, TARGET_CALL, ATM_CALL):
        times = dict(at_boundary)
        times[stale_role] = DECISION - timedelta(microseconds=2_001_000)
        assert compute_x10_price_based_downside_skew(
            _dataset(),
            _standard_chain(quote_times=times),
        ) is None


@pytest.mark.parametrize("role", [TARGET_PUT, TARGET_CALL, ATM_CALL])
def test_x10_077_to_078_latest_invalid_quote_has_no_earlier_valid_fallback(
    role: str,
) -> None:
    template = {
        TARGET_PUT: _contract(TARGET_PUT, Decimal("5970"), OptionType.PUT),
        TARGET_CALL: _contract(TARGET_CALL, Decimal("6030"), OptionType.CALL),
        ATM_CALL: _contract(ATM_CALL, Decimal("6000"), OptionType.CALL),
    }[role]
    earlier = _mid_quote(
        template,
        Decimal("5"),
        quote_ts=DECISION - timedelta(seconds=2),
        raw_file_id=f"earlier-{role}",
    )
    later = _quote(
        template,
        bid=Decimal("2"),
        ask=Decimal("1"),
        quote_ts=DECISION - timedelta(seconds=1),
        raw_file_id=f"later-{role}",
    )
    chain = _standard_chain(
        missing_quotes=frozenset({role}),
        extra_quotes=(earlier, later),
    )
    assert _snapshot(chain, role).selected_quote is later
    assert _snapshot(chain, role).quality_status is QualityStatus.CROSSED
    assert compute_x10_price_based_downside_skew(_dataset(), chain) is None


@pytest.mark.parametrize("side", [OptionType.PUT, OptionType.CALL])
def test_x10_079_to_080_selected_target_same_side_multiplicity_hard_fails(
    side: OptionType,
) -> None:
    strike = Decimal("5970") if side is OptionType.PUT else Decimal("6030")
    duplicate = _contract(f"SECOND-{side.name}", strike, side)
    chain = _standard_chain(
        extra_contracts=(duplicate,),
        extra_quotes=(_mid_quote(duplicate, Decimal("30")),),
    )
    with pytest.raises(OptionFeatureIntegrityError, match="multiple contracts"):
        compute_x10_price_based_downside_skew(_dataset(), chain)


def test_x10_081_nonselected_same_side_multiplicity_does_not_block() -> None:
    extras = (
        _contract("FAR-PUT-A", Decimal("5900"), OptionType.PUT),
        _contract("FAR-PUT-B", Decimal("5900"), OptionType.PUT),
        _contract("FAR-CALL-A", Decimal("6100"), OptionType.CALL),
        _contract("FAR-CALL-B", Decimal("6100"), OptionType.CALL),
    )
    chain = _standard_chain(
        extra_contracts=extras,
        extra_quotes=tuple(_mid_quote(contract, Decimal("30")) for contract in extras),
    )
    assert compute_x10_price_based_downside_skew(
        _dataset(),
        chain,
    ) == float(Decimal("5") / Decimal("19"))


@pytest.mark.parametrize(
    "role",
    [ATM_CALL, ATM_PUT, TARGET_PUT, TARGET_CALL],
)
@pytest.mark.parametrize(
    "defect",
    ["missing", "source", "contract", "prices"],
)
def test_x10_082_to_085_contradictory_valid_snapshot_hard_fails(
    role: str,
    defect: str,
) -> None:
    chain = _standard_chain()
    snapshot = _snapshot(chain, role)
    assert snapshot.selected_quote is not None
    if defect == "missing":
        malformed = replace(snapshot, selected_quote=None)
    elif defect == "source":
        malformed = replace(
            snapshot,
            selected_quote=snapshot.selected_quote.model_copy(
                update={"source": "OTHER_SOURCE"}
            ),
        )
    elif defect == "contract":
        malformed = replace(
            snapshot,
            selected_quote=snapshot.selected_quote.model_copy(
                update={"contract_id": "OTHER_CONTRACT"}
            ),
        )
    else:
        malformed = replace(
            snapshot,
            selected_quote=snapshot.selected_quote.model_copy(
                update={"ask_px": snapshot.selected_quote.bid_px}
            ),
        )
    with pytest.raises(OptionFeatureIntegrityError):
        compute_x10_price_based_downside_skew(
            _dataset(),
            _replace_snapshot(chain, role, malformed),
        )


def test_x10_086_future_expiry_is_structural_misuse() -> None:
    with pytest.raises(OptionFeatureIntegrityError, match="session date"):
        compute_x10_price_based_downside_skew(
            _dataset(),
            _standard_chain(expiration_date=FUTURE_EXPIRY),
        )


@pytest.mark.parametrize("defect", ["xsp", "am", "timestamp", "atm_multiple"])
def test_x10_087_to_090_structural_s2_12_errors_propagate(defect: str) -> None:
    dataset = _dataset()
    if defect == "xsp":
        call = _contract("XSP-CALL", Decimal("600"), OptionType.CALL, product="XSP")
        put = _contract("XSP-PUT", Decimal("600"), OptionType.PUT, product="XSP")
        chain = _build_chain(
            [call, put],
            [_mid_quote(call, Decimal("2")), _mid_quote(put, Decimal("3"))],
            product="XSP",
        )
    else:
        chain = _standard_chain()
        if defect == "am":
            chain = replace(chain, settlement_style=SettlementStyle.AM)
        elif defect == "timestamp":
            chain = replace(
                chain,
                decision_ts_utc=chain.decision_ts_utc + timedelta(microseconds=1),
            )
        else:
            duplicate = _contract("SECOND-ATM-CALL", Decimal("6000"), OptionType.CALL)
            chain = _standard_chain(
                extra_contracts=(duplicate,),
                extra_quotes=(_mid_quote(duplicate, Decimal("30")),),
            )
    with pytest.raises(ATMCallPutPairSelectionIntegrityError):
        compute_x10_price_based_downside_skew(dataset, chain)


def test_x10_091_to_095_input_order_independence_and_purity() -> None:
    dataset = _dataset()
    chain = _selection_chain(
        (
            ("PUT-LOW", Decimal("5965"), Decimal("8")),
            ("PUT-HIGH", Decimal("5975"), Decimal("20")),
        ),
        (
            ("CALL-LOW", Decimal("6025"), Decimal("3")),
            ("CALL-HIGH", Decimal("6035"), Decimal("30")),
        ),
    )
    dataset_before = dataset
    chain_before = chain
    expected = compute_x10_price_based_downside_skew(dataset, chain)
    reversed_value = compute_x10_price_based_downside_skew(
        dataset,
        replace(chain, snapshots=tuple(reversed(chain.snapshots))),
    )
    shuffled = (
        chain.snapshots[4],
        chain.snapshots[1],
        chain.snapshots[5],
        chain.snapshots[0],
        chain.snapshots[3],
        chain.snapshots[2],
    )
    shuffled_value = compute_x10_price_based_downside_skew(
        dataset,
        replace(chain, snapshots=shuffled),
    )
    assert expected == reversed_value == shuffled_value
    assert dataset == dataset_before
    assert chain == chain_before


def test_x10_096_to_100_no_premature_x11_or_later_surface() -> None:
    assert {
        "compute_x11",
        "select_next_expiry",
        "next_expiry",
        "compute_tau",
        "tau",
        "FeatureVector",
        "feature_snapshots",
        "persist_features",
    }.isdisjoint(vars(option_features))


def test_x10_final_float_requires_only_finiteness() -> None:
    chain = _standard_chain(
        price_overrides={
            TARGET_PUT: (Decimal("1e999"), Decimal("2e999")),
        }
    )
    with pytest.raises(OptionFeatureIntegrityError, match="finite"):
        compute_x10_price_based_downside_skew(_dataset(), chain)
