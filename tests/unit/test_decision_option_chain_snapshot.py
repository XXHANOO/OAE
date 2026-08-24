from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import inspect
from zoneinfo import ZoneInfo

import pytest

import oae.data.option_chain as option_chain
from oae.data.asof import AsOfSelectionIntegrityError
from oae.data.decision_snapshot import (
    DecisionOptionSnapshot,
    build_decision_option_snapshot,
)
from oae.data.option_chain import (
    DecisionOptionChainSnapshot,
    DecisionOptionChainSnapshotIntegrityError,
    build_decision_option_chain_snapshot,
)
from oae.enums import (
    ExerciseStyle,
    OptionType,
    QualityStatus,
    SettlementStyle,
)
from oae.schemas.options import OptionContractRecord
from oae.schemas.quotes import OptionQuoteRecord


UTC = timezone.utc
ET = ZoneInfo("America/New_York")
SESSION_DATE = date(2026, 7, 15)
FUTURE_EXPIRY = date(2026, 7, 17)
DECISION = datetime(2026, 7, 15, 17, 30, tzinfo=UTC)
SOURCE_A = "SOURCE_A"
SOURCE_B = "SOURCE_B"


def _contract(**overrides: object) -> OptionContractRecord:
    expiration_date = overrides.get("expiration_date", SESSION_DATE)
    assert isinstance(expiration_date, date)
    contract_id = overrides.get("contract_id", "SPX-C-6000")
    values: dict[str, object] = {
        "contract_id": contract_id,
        "vendor_symbol": f"VENDOR-{contract_id}",
        "product": "SPX",
        "root_symbol": "SPXW",
        "underlying": "SPX",
        "option_type": OptionType.CALL,
        "strike": Decimal("6000"),
        "expiration_date": expiration_date,
        "settlement_style": SettlementStyle.PM,
        "exercise_style": ExerciseStyle.EUROPEAN,
        "multiplier": 100,
        "series_type": "PM_WEEKLY",
        "expiration_ts_utc": datetime(
            expiration_date.year,
            expiration_date.month,
            expiration_date.day,
            20,
            tzinfo=UTC,
        ),
        "first_seen_date": date(2026, 7, 1),
        "last_seen_date": expiration_date,
        "source": SOURCE_A,
    }
    values.update(overrides)
    return OptionContractRecord.model_validate(values)


def _quote(**overrides: object) -> OptionQuoteRecord:
    values: dict[str, object] = {
        "contract_id": "SPX-C-6000",
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
        "source": SOURCE_A,
        "raw_file_id": "raw-file-a",
    }
    values.update(overrides)
    return OptionQuoteRecord.model_validate(values)


def _build(
    contracts: list[OptionContractRecord],
    quotes: list[OptionQuoteRecord],
    decision_ts: datetime = DECISION,
    *,
    product: str = "SPX",
    expiration_date: date = SESSION_DATE,
    source: str = SOURCE_A,
) -> DecisionOptionChainSnapshot:
    return build_decision_option_chain_snapshot(
        contracts,
        quotes,
        decision_ts,
        product=product,
        expiration_date=expiration_date,
        source=source,
    )


def test_ocs_001_to_007_public_api_and_immutability_contract() -> None:
    assert is_dataclass(DecisionOptionChainSnapshot)
    assert DecisionOptionChainSnapshot.__dataclass_params__.frozen
    assert hasattr(DecisionOptionChainSnapshot, "__slots__")
    assert [field.name for field in fields(DecisionOptionChainSnapshot)] == [
        "product",
        "expiration_date",
        "settlement_style",
        "source",
        "decision_ts_utc",
        "snapshots",
    ]
    assert issubclass(DecisionOptionChainSnapshotIntegrityError, RuntimeError)
    signature = inspect.signature(build_decision_option_chain_snapshot)
    assert list(signature.parameters) == [
        "contracts",
        "quotes",
        "decision_ts",
        "product",
        "expiration_date",
        "source",
    ]
    assert all(
        signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        for name in ("product", "expiration_date", "source")
    )
    assert option_chain.__all__ == (
        "DecisionOptionChainSnapshot",
        "DecisionOptionChainSnapshotIntegrityError",
        "build_decision_option_chain_snapshot",
    )
    chain = _build([_contract()], [])
    assert isinstance(chain.snapshots, tuple)
    with pytest.raises(FrozenInstanceError):
        chain.source = "MUTATED"  # type: ignore[misc]


def test_ocs_008_to_013_exact_target_filter_and_root_distinction() -> None:
    exact = _contract(contract_id="EXACT", root_symbol="SPXW")
    reversed_seen_dates = _contract(
        contract_id="DATE-ONLY-NOT-FILTERED",
        strike=Decimal("6001"),
        first_seen_date=date(2026, 7, 20),
        last_seen_date=date(2026, 7, 1),
    )
    am = _contract(
        contract_id="AM",
        settlement_style=SettlementStyle.AM,
    )
    other_expiry = _contract(
        contract_id="OTHER-EXPIRY",
        expiration_date=FUTURE_EXPIRY,
    )
    other_product = _contract(contract_id="XSP", product="XSP")
    other_source = _contract(contract_id="OTHER-SOURCE", source=SOURCE_B)
    universe = [
        other_source,
        am,
        other_product,
        exact,
        other_expiry,
        reversed_seen_dates,
    ]

    chain = _build(universe, [])

    assert [snapshot.contract.contract_id for snapshot in chain.snapshots] == [
        "EXACT",
        "DATE-ONLY-NOT-FILTERED",
    ]
    assert chain.snapshots[0].contract.root_symbol == "SPXW"


def test_ocs_014_to_016_generic_exact_expiry_without_next_expiry_selection() -> None:
    same_day = _contract(contract_id="SAME-DAY")
    future = _contract(
        contract_id="FUTURE-EXACT",
        expiration_date=FUTURE_EXPIRY,
    )
    contracts = [future, same_day]

    same_day_chain = _build(contracts, [])
    future_chain = _build(
        contracts,
        [],
        expiration_date=FUTURE_EXPIRY,
    )

    assert [s.contract.contract_id for s in same_day_chain.snapshots] == [
        "SAME-DAY"
    ]
    assert [s.contract.contract_id for s in future_chain.snapshots] == [
        "FUTURE-EXACT"
    ]
    signature_names = inspect.signature(
        build_decision_option_chain_snapshot
    ).parameters
    assert {
        "session_calendar",
        "calendar",
        "next_expiry",
        "select_next_expiry",
    }.isdisjoint(signature_names)


def test_ocs_017_to_020_canonical_order_and_contract_input_purity() -> None:
    contracts = [
        _contract(
            contract_id="PUT-B",
            strike=Decimal("6000"),
            option_type=OptionType.PUT,
        ),
        _contract(contract_id="CALL-B", strike=Decimal("6000")),
        _contract(contract_id="LOW", strike=Decimal("5995")),
        _contract(contract_id="CALL-A", strike=Decimal("6000")),
        _contract(contract_id="HIGH", strike=Decimal("6005")),
    ]
    before = list(contracts)

    chain = _build(contracts, [])

    assert [snapshot.contract.contract_id for snapshot in chain.snapshots] == [
        "LOW",
        "CALL-A",
        "CALL-B",
        "PUT-B",
        "HIGH",
    ]
    assert contracts == before
    assert len(chain.snapshots) == 5


def test_ocs_021_to_022_source_scoped_quote_routing_prevents_collision() -> None:
    contract = _contract(contract_id="COLLIDE")
    other_source_quote = _quote(
        contract_id="COLLIDE",
        source=SOURCE_B,
        quote_ts_utc=DECISION,
    )

    chain = _build([contract], [other_source_quote])

    snapshot = chain.snapshots[0]
    assert snapshot.selected_quote is None
    assert snapshot.quality_status is QualityStatus.MISSING


def test_ocs_023_to_027_reuses_per_contract_builder_with_exact_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_a = _contract(contract_id="CALL-A", strike=Decimal("6000"))
    put_a = _contract(
        contract_id="PUT-A",
        strike=Decimal("6000"),
        option_type=OptionType.PUT,
    )
    excluded = _contract(
        contract_id="EXCLUDED",
        settlement_style=SettlementStyle.AM,
    )
    call_quote = _quote(contract_id="CALL-A")
    put_quote = _quote(contract_id="PUT-A")
    wrong_source_collision = _quote(contract_id="CALL-A", source=SOURCE_B)
    excluded_quote = _quote(contract_id="EXCLUDED")
    observed: list[
        tuple[OptionContractRecord, tuple[OptionQuoteRecord, ...], datetime]
    ] = []

    def capture(
        contract: OptionContractRecord,
        quotes: tuple[OptionQuoteRecord, ...],
        decision_ts: datetime,
    ) -> DecisionOptionSnapshot:
        observed.append((contract, quotes, decision_ts))
        return build_decision_option_snapshot(contract, quotes, decision_ts)

    monkeypatch.setattr(
        option_chain,
        "build_decision_option_snapshot",
        capture,
    )
    chain = _build(
        [excluded, put_a, call_a],
        [wrong_source_collision, excluded_quote, put_quote, call_quote],
    )

    assert len(chain.snapshots) == 2
    assert [(call[0], call[1]) for call in observed] == [
        (call_a, (call_quote,)),
        (put_a, (put_quote,)),
    ]
    assert all(call[2] == chain.decision_ts_utc for call in observed)
    assert excluded not in [call[0] for call in observed]


def test_ocs_028_to_036_missing_and_invalid_states_are_all_preserved() -> None:
    definitions = [
        ("VALID", QualityStatus.VALID, {}),
        ("MISSING", QualityStatus.MISSING, None),
        (
            "STALE",
            QualityStatus.STALE,
            {"quote_ts_utc": DECISION - timedelta(microseconds=2_000_001)},
        ),
        (
            "CROSSED",
            QualityStatus.CROSSED,
            {"bid_px": Decimal("1.20"), "ask_px": Decimal("1.10")},
        ),
        ("LOCKED", QualityStatus.LOCKED, {"ask_px": Decimal("1.00")}),
        ("ZERO-BID", QualityStatus.ZERO_BID, {"bid_px": Decimal("0")}),
        ("ZERO-SIZE", QualityStatus.ZERO_SIZE, {"bid_size": 0}),
    ]
    contracts = [
        _contract(contract_id=name, strike=Decimal(6000 + index))
        for index, (name, _, _) in enumerate(definitions)
    ]
    quotes = [
        _quote(contract_id=name, **overrides)
        for name, _, overrides in definitions
        if overrides is not None
    ]

    chain = _build(list(reversed(contracts)), list(reversed(quotes)))

    assert len(chain.snapshots) == len(contracts)
    assert [snapshot.contract.contract_id for snapshot in chain.snapshots] == [
        name for name, _, _ in definitions
    ]
    assert [snapshot.quality_status for snapshot in chain.snapshots] == [
        status for _, status, _ in definitions
    ]


def test_ocs_037_to_039_latest_invalid_remains_authoritative() -> None:
    contract = _contract()
    earlier_valid = _quote(
        quote_ts_utc=DECISION - timedelta(seconds=1),
        raw_file_id="earlier",
    )
    later_crossed = _quote(
        quote_ts_utc=DECISION - timedelta(microseconds=100_000),
        bid_px=Decimal("1.20"),
        ask_px=Decimal("1.10"),
        raw_file_id="later",
    )

    snapshot = _build(
        [contract],
        [earlier_valid, later_crossed],
    ).snapshots[0]

    assert snapshot.selected_quote is later_crossed
    assert snapshot.quality_status is QualityStatus.CROSSED
    assert snapshot.selected_quote is not earlier_valid


def test_ocs_040_to_043_empty_and_future_only_streams_remain_missing() -> None:
    empty_contract = _contract(contract_id="EMPTY", strike=Decimal("6000"))
    future_contract = _contract(contract_id="FUTURE", strike=Decimal("6001"))
    future_quote = _quote(
        contract_id="FUTURE",
        quote_ts_utc=DECISION + timedelta(microseconds=1),
    )

    chain = _build([future_contract, empty_contract], [future_quote])

    assert all(
        snapshot.quality_status is QualityStatus.MISSING
        for snapshot in chain.snapshots
    )
    assert all(snapshot.selected_quote is None for snapshot in chain.snapshots)
    assert all(snapshot.quote_age_seconds is None for snapshot in chain.snapshots)


@pytest.mark.parametrize(
    ("age_microseconds", "expected"),
    [
        (1_999_000, QualityStatus.VALID),
        (2_000_000, QualityStatus.VALID),
        (2_001_000, QualityStatus.STALE),
    ],
)
def test_ocs_044_to_046_two_second_boundary_survives_composition(
    age_microseconds: int,
    expected: QualityStatus,
) -> None:
    quote = _quote(
        quote_ts_utc=DECISION - timedelta(microseconds=age_microseconds)
    )

    snapshot = _build([_contract()], [quote]).snapshots[0]

    assert snapshot.quality_status is expected
    assert snapshot.quote_age_seconds == age_microseconds / 1_000_000


def test_ocs_047_to_050_same_maximum_ambiguity_propagates_without_tie_break() -> None:
    first = _quote(quote_ts_utc=DECISION, sequence_no=1)
    second = _quote(quote_ts_utc=DECISION, sequence_no=2)

    for quotes in ([first, second], [second, first]):
        with pytest.raises(AsOfSelectionIntegrityError) as exc_info:
            _build([_contract()], quotes)
        assert type(exc_info.value) is AsOfSelectionIntegrityError


def test_ocs_051_to_054_duplicate_identity_fails_but_same_strike_does_not() -> None:
    duplicate_a = _contract(contract_id="DUPLICATE", strike=Decimal("6000"))
    duplicate_b = _contract(
        contract_id="DUPLICATE",
        strike=Decimal("6001"),
        option_type=OptionType.PUT,
    )
    with pytest.raises(
        DecisionOptionChainSnapshotIntegrityError,
        match="duplicate eligible",
    ):
        _build([duplicate_a, duplicate_b], [])
    with pytest.raises(DecisionOptionChainSnapshotIntegrityError):
        _build([duplicate_a, duplicate_a], [])

    other_source_same_id = _contract(
        contract_id="DUPLICATE",
        source=SOURCE_B,
    )
    distinct_same_strike = _contract(
        contract_id="DISTINCT",
        strike=Decimal("6000"),
        option_type=OptionType.PUT,
    )
    chain = _build(
        [duplicate_a, other_source_same_id, distinct_same_strike],
        [],
    )
    assert {snapshot.contract.contract_id for snapshot in chain.snapshots} == {
        "DUPLICATE",
        "DISTINCT",
    }


def test_ocs_055_to_057_empty_target_chain_has_exact_metadata_without_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> DecisionOptionSnapshot:
        raise AssertionError("per-contract builder must not be called")

    monkeypatch.setattr(option_chain, "build_decision_option_snapshot", fail)
    chain = _build(
        [_contract(product="XSP")],
        [_quote(contract_id="UNKNOWN")],
    )

    assert chain.snapshots == ()
    assert (
        chain.product,
        chain.expiration_date,
        chain.settlement_style,
        chain.source,
        chain.decision_ts_utc,
    ) == (
        "SPX",
        SESSION_DATE,
        SettlementStyle.PM,
        SOURCE_A,
        DECISION,
    )


@pytest.mark.parametrize(
    ("decision_ts", "expected_utc"),
    [
        (datetime(2026, 7, 15, 13, 30, tzinfo=ET), DECISION),
        (
            datetime(2026, 1, 15, 13, 30, tzinfo=ET),
            datetime(2026, 1, 15, 18, 30, tzinfo=UTC),
        ),
        (DECISION.astimezone(timezone(timedelta(hours=9))), DECISION),
    ],
)
def test_ocs_058_to_060_exact_decision_time_is_dst_aware_and_canonical(
    decision_ts: datetime,
    expected_utc: datetime,
) -> None:
    chain = _build([], [], decision_ts)

    assert chain.decision_ts_utc == expected_utc
    assert chain.decision_ts_utc.tzinfo is UTC


@pytest.mark.parametrize(
    "decision_ts",
    [
        datetime(2026, 7, 15, 13, 29, 59, tzinfo=ET),
        datetime(2026, 7, 15, 13, 30, 1, tzinfo=ET),
        datetime(2026, 7, 15, 14, 30, tzinfo=ET),
    ],
)
def test_ocs_061_to_063_noncanonical_aware_decision_time_hard_fails(
    decision_ts: datetime,
) -> None:
    with pytest.raises(
        DecisionOptionChainSnapshotIntegrityError,
        match="13:30:00",
    ):
        _build([], [], decision_ts)


def test_naive_decision_timestamp_rejection_propagates() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _build([], [], datetime(2026, 7, 15, 13, 30))


def test_ocs_064_to_069_contract_and_quote_order_independence_and_purity() -> None:
    call = _contract(contract_id="CALL", strike=Decimal("6000"))
    put = _contract(
        contract_id="PUT",
        strike=Decimal("6000"),
        option_type=OptionType.PUT,
    )
    high = _contract(contract_id="HIGH", strike=Decimal("6005"))
    contracts = [put, high, call]
    quotes = [
        _quote(
            contract_id="CALL",
            quote_ts_utc=DECISION - timedelta(seconds=2),
            raw_file_id="call-old",
        ),
        _quote(contract_id="PUT", raw_file_id="put"),
        _quote(contract_id="HIGH", raw_file_id="high"),
        _quote(contract_id="CALL", raw_file_id="call-latest"),
    ]
    contracts_before = list(contracts)
    quote_payloads_before = [quote.model_dump(mode="python") for quote in quotes]

    baseline = _build(contracts, quotes)
    reversed_chain = _build(list(reversed(contracts)), list(reversed(quotes)))
    shuffled_chain = _build(
        [high, call, put],
        [quotes[2], quotes[0], quotes[3], quotes[1]],
    )

    assert baseline == reversed_chain == shuffled_chain
    assert contracts == contracts_before
    assert [quote.model_dump(mode="python") for quote in quotes] == (
        quote_payloads_before
    )


def test_ocs_070_to_072_hostile_irrelevant_data_cannot_contaminate_target() -> None:
    target_contract = _contract(contract_id="TARGET")
    target_quote = _quote(contract_id="TARGET", raw_file_id="target")
    baseline = _build([target_contract], [target_quote])
    hostile_contracts = [
        _contract(contract_id="WRONG-PRODUCT", product="XSP"),
        _contract(contract_id="WRONG-EXPIRY", expiration_date=FUTURE_EXPIRY),
        _contract(contract_id="AM", settlement_style=SettlementStyle.AM),
        _contract(contract_id="WRONG-SOURCE", source=SOURCE_B),
    ]
    hostile_quotes = [
        _quote(
            contract_id=contract.contract_id,
            source=contract.source,
            quote_ts_utc=DECISION + timedelta(seconds=10),
            bid_px=Decimal("999999"),
            ask_px=Decimal("0"),
            raw_file_id=f"hostile-{contract.contract_id}",
        )
        for contract in hostile_contracts
    ]
    hostile_quotes.extend(
        [
            _quote(
                contract_id="UNKNOWN",
                quote_ts_utc=DECISION,
                bid_px=Decimal("999999"),
                ask_px=Decimal("0"),
                raw_file_id="unknown",
            ),
            _quote(
                contract_id="TARGET",
                source=SOURCE_B,
                quote_ts_utc=DECISION,
                bid_px=Decimal("999999"),
                ask_px=Decimal("0"),
                raw_file_id="wrong-source-collision",
            ),
        ]
    )

    augmented = _build(
        hostile_contracts + [target_contract],
        hostile_quotes + [target_quote],
    )

    assert augmented == baseline
    assert augmented.snapshots[0].selected_quote is target_quote
    assert augmented.snapshots[0].quality_status is QualityStatus.VALID


def test_ocs_073_to_081_no_premature_atm_mid_or_feature_surface() -> None:
    signature_names = set(
        inspect.signature(build_decision_option_chain_snapshot).parameters
    )
    assert {
        "spx_spot",
        "spot",
        "S_t",
        "target_strike",
    }.isdisjoint(signature_names)
    assert {
        "select_atm",
        "nearest_strike",
        "pair_call_put",
        "compute_x9",
        "compute_x10",
        "compute_x11",
        "FeatureVector",
    }.isdisjoint(vars(option_chain))
    assert [field.name for field in fields(DecisionOptionChainSnapshot)] == [
        "product",
        "expiration_date",
        "settlement_style",
        "source",
        "decision_ts_utc",
        "snapshots",
    ]
    chain = _build(
        [
            _contract(contract_id="CALL"),
            _contract(contract_id="PUT", option_type=OptionType.PUT),
        ],
        [],
    )
    assert len(chain.snapshots) == 2
    assert not hasattr(chain, "mid_price")
    assert not hasattr(chain, "feature_valid")
    assert not hasattr(chain, "invalid_reason")


class _StringSubclass(str):
    pass


@pytest.mark.parametrize("product", ["", 1, True, _StringSubclass("SPX")])
def test_target_product_must_be_exact_non_empty_str(product: object) -> None:
    with pytest.raises(
        DecisionOptionChainSnapshotIntegrityError,
        match="product",
    ):
        _build([], [], product=product)  # type: ignore[arg-type]


@pytest.mark.parametrize("source", ["", 1, True, _StringSubclass(SOURCE_A)])
def test_target_source_must_be_exact_non_empty_str(source: object) -> None:
    with pytest.raises(
        DecisionOptionChainSnapshotIntegrityError,
        match="source",
    ):
        _build([], [], source=source)  # type: ignore[arg-type]


def test_target_product_and_source_are_preserved_without_normalization() -> None:
    contract = _contract(product=" SPX ", source=" SOURCE_A ")

    chain = _build(
        [contract],
        [],
        product=" SPX ",
        source=" SOURCE_A ",
    )

    assert chain.product == " SPX "
    assert chain.source == " SOURCE_A "
    assert chain.snapshots[0].contract is contract
