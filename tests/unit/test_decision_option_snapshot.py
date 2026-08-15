from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import inspect
from zoneinfo import ZoneInfo

import pytest

import oae.data.decision_snapshot as snapshots
from oae.data.asof import AsOfSelectionIntegrityError, classify_quote_quality
from oae.data.decision_snapshot import (
    DecisionOptionSnapshot,
    DecisionOptionSnapshotIntegrityError,
    build_decision_option_snapshot,
)
from oae.enums import ExerciseStyle, OptionType, QualityStatus, SettlementStyle
from oae.schemas.options import OptionContractRecord
from oae.schemas.quotes import OptionQuoteRecord


UTC = timezone.utc
ET = ZoneInfo("America/New_York")
DECISION = datetime(2026, 7, 15, 17, 30, tzinfo=UTC)
SOURCE = "TEST_VENDOR"
CONTRACT_ID = "opaque-contract-id"


def _contract(**overrides: object) -> OptionContractRecord:
    values: dict[str, object] = {
        "contract_id": CONTRACT_ID,
        "vendor_symbol": "VENDOR_SYMBOL",
        "product": "XSP",
        "root_symbol": "XSP",
        "underlying": "XSP",
        "option_type": OptionType.CALL,
        "strike": Decimal("640.00"),
        "expiration_date": date(2026, 7, 15),
        "settlement_style": SettlementStyle.PM,
        "exercise_style": ExerciseStyle.EUROPEAN,
        "multiplier": 100,
        "series_type": "PM_WEEKLY",
        "expiration_ts_utc": datetime(2026, 7, 15, 20, 0, tzinfo=UTC),
        "first_seen_date": date(2026, 7, 1),
        "last_seen_date": date(2026, 7, 15),
        "source": SOURCE,
    }
    values.update(overrides)
    return OptionContractRecord.model_validate(values)


def _quote(**overrides: object) -> OptionQuoteRecord:
    values: dict[str, object] = {
        "contract_id": CONTRACT_ID,
        "quote_ts_utc": DECISION - timedelta(seconds=1),
        "session_date_et": date(2026, 7, 15),
        "bid_px": Decimal("1.00"),
        "ask_px": Decimal("1.10"),
        "bid_size": 1,
        "ask_size": 1,
        "bid_exchange": "X",
        "ask_exchange": "Y",
        "quote_condition": None,
        "sequence_no": None,
        "source": SOURCE,
        "raw_file_id": "raw-file-a",
    }
    values.update(overrides)
    return OptionQuoteRecord.model_validate(values)


def test_dos_001_to_004_public_immutable_api_contract() -> None:
    assert is_dataclass(DecisionOptionSnapshot)
    assert DecisionOptionSnapshot.__dataclass_params__.frozen
    assert hasattr(DecisionOptionSnapshot, "__slots__")
    assert [field.name for field in fields(DecisionOptionSnapshot)] == [
        "contract", "decision_ts_utc", "selected_quote", "quote_age_seconds",
        "quality_status",
    ]
    assert issubclass(DecisionOptionSnapshotIntegrityError, RuntimeError)
    signature = inspect.signature(build_decision_option_snapshot)
    assert list(signature.parameters) == ["contract", "quotes", "decision_ts"]
    assert {"source_quote_id", "sequence_no", "tie_break", "quality", "product",
            "expiration", "strike", "spot", "chain"}.isdisjoint(signature.parameters)
    assert "source_quote_id" not in DecisionOptionSnapshot.__annotations__
    with pytest.raises(FrozenInstanceError):
        DecisionOptionSnapshot(  # type: ignore[misc]
            _contract(), DECISION, None, None, QualityStatus.MISSING
        ).quality_status = QualityStatus.VALID


def test_dos_005_to_009_empty_and_future_only_are_missing_without_quote() -> None:
    contract = _contract()
    empty = build_decision_option_snapshot(contract, [], DECISION)
    future = build_decision_option_snapshot(
        contract, [_quote(quote_ts_utc=DECISION + timedelta(microseconds=1))], DECISION
    )
    for snapshot in (empty, future):
        assert snapshot.contract is contract
        assert snapshot.selected_quote is None
        assert snapshot.quote_age_seconds is None
        assert snapshot.quality_status is QualityStatus.MISSING


def test_dos_010_to_018_temporal_selection_identity_and_utc_canonicalization() -> None:
    contract = _contract()
    older = _quote(quote_ts_utc=DECISION - timedelta(seconds=2))
    latest = _quote(quote_ts_utc=DECISION)
    future = _quote(quote_ts_utc=DECISION + timedelta(seconds=1))
    records = [future, older, latest]
    before = [quote.model_dump(mode="python") for quote in records]
    snapshot = build_decision_option_snapshot(contract, records, DECISION.astimezone(ET))
    assert snapshot.selected_quote is latest
    assert snapshot.quote_age_seconds == 0.0
    assert snapshot.quality_status is QualityStatus.VALID
    assert snapshot.decision_ts_utc == DECISION
    assert snapshot.decision_ts_utc.tzinfo is UTC
    assert [quote.model_dump(mode="python") for quote in records] == before
    assert build_decision_option_snapshot(contract, list(reversed(records)), DECISION).selected_quote is latest


def test_dos_019_to_024_naive_failure_exact_age_and_boundaries() -> None:
    contract = _contract()
    with pytest.raises(ValueError, match="timezone-aware"):
        build_decision_option_snapshot(contract, [], DECISION.replace(tzinfo=None))
    malformed_values = _quote().model_dump(mode="python")
    malformed_values["quote_ts_utc"] = DECISION.replace(tzinfo=None)
    malformed = OptionQuoteRecord.model_construct(**malformed_values)
    with pytest.raises(ValueError, match="timezone-aware"):
        build_decision_option_snapshot(contract, [malformed], DECISION)
    for age_microseconds, expected in [
        (1_999_999, QualityStatus.VALID),
        (2_000_000, QualityStatus.VALID),
        (2_000_001, QualityStatus.STALE),
    ]:
        quote = _quote(quote_ts_utc=DECISION - timedelta(microseconds=age_microseconds))
        snapshot = build_decision_option_snapshot(contract, [quote], DECISION)
        assert snapshot.selected_quote is quote
        assert snapshot.quote_age_seconds == age_microseconds / 1_000_000
        assert snapshot.quality_status is expected


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"ask_px": Decimal("1.00")}, QualityStatus.LOCKED),
        ({"ask_px": Decimal("0.99")}, QualityStatus.CROSSED),
        ({"bid_px": Decimal("0")}, QualityStatus.ZERO_BID),
        ({"bid_size": 0}, QualityStatus.ZERO_SIZE),
    ],
)
def test_dos_025_to_030_invalid_latest_quote_is_retained_and_classified(
    overrides: dict[str, object], expected: QualityStatus
) -> None:
    contract = _contract()
    older_valid = _quote(quote_ts_utc=DECISION - timedelta(seconds=2))
    newer_invalid = _quote(quote_ts_utc=DECISION - timedelta(seconds=1), **overrides)
    snapshot = build_decision_option_snapshot(contract, [older_valid, newer_invalid], DECISION)
    assert snapshot.selected_quote is newer_invalid
    assert snapshot.quality_status is expected


@pytest.mark.parametrize(
    "overrides",
    [
        {"contract_id": "other-contract"},
        {"source": "OTHER_VENDOR"},
        {"source": " TEST_VENDOR"},
        {"contract_id": "future-contract", "quote_ts_utc": DECISION + timedelta(seconds=1)},
        {"source": "FUTURE_VENDOR", "quote_ts_utc": DECISION + timedelta(seconds=1)},
    ],
)
def test_dos_031_to_035_exact_contract_source_guard_including_future_rows(
    overrides: dict[str, object]
) -> None:
    with pytest.raises(DecisionOptionSnapshotIntegrityError, match="source-scoped"):
        build_decision_option_snapshot(_contract(), [_quote(**overrides)], DECISION)


def test_dos_036_to_041_lineage_and_same_max_ambiguity_delegate_to_selector() -> None:
    contract = _contract()
    older = _quote(raw_file_id="raw-file-a", quote_ts_utc=DECISION - timedelta(seconds=2))
    latest = _quote(raw_file_id="raw-file-b", quote_ts_utc=DECISION - timedelta(seconds=1))
    assert build_decision_option_snapshot(contract, [older, latest], DECISION).selected_quote is latest
    duplicate_a = _quote(quote_ts_utc=DECISION, sequence_no=7)
    duplicate_b = _quote(quote_ts_utc=DECISION, sequence_no=7)
    assert build_decision_option_snapshot(contract, [duplicate_a, duplicate_b], DECISION).selected_quote is duplicate_a
    ambiguous_a = _quote(quote_ts_utc=DECISION, sequence_no=7)
    ambiguous_b = _quote(quote_ts_utc=DECISION, sequence_no=8)
    quality_a = _quote(quote_ts_utc=DECISION, sequence_no=9)
    quality_b = _quote(quote_ts_utc=DECISION, sequence_no=9, ask_px=Decimal("1.00"))
    for quotes in ([ambiguous_a, ambiguous_b], [ambiguous_b, ambiguous_a], [quality_a, quality_b], [quality_b, quality_a]):
        with pytest.raises(AsOfSelectionIntegrityError, match="distinct quotes"):
            build_decision_option_snapshot(contract, quotes, DECISION)


def test_dos_042_missing_does_not_call_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> QualityStatus:
        raise AssertionError("MISSING snapshots must not classify a quote")

    monkeypatch.setattr(snapshots, "classify_quote_quality", fail)
    contract = _contract()
    future_quote = _quote(
        quote_ts_utc=DECISION + timedelta(microseconds=1),
    )
    assert future_quote.source == contract.source
    assert future_quote.contract_id == contract.contract_id
    for quotes in ([], [future_quote]):
        snapshot = build_decision_option_snapshot(contract, quotes, DECISION)
        assert snapshot.contract is contract
        assert snapshot.selected_quote is None
        assert snapshot.quote_age_seconds is None
        assert snapshot.quality_status is QualityStatus.MISSING


def test_dos_043_non_missing_delegates_frozen_two_second_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[float] = []

    def capture(quote: OptionQuoteRecord, decision_ts: datetime, max_age_seconds: float) -> QualityStatus:
        observed.append(max_age_seconds)
        return classify_quote_quality(quote, decision_ts, max_age_seconds)

    monkeypatch.setattr(snapshots, "classify_quote_quality", capture)
    assert build_decision_option_snapshot(_contract(), [_quote()], DECISION).quality_status is QualityStatus.VALID
    assert observed == [2.0]


def test_dos_049_to_050_contract_identity_and_selector_errors_propagate() -> None:
    contract = _contract()
    quote = _quote()
    snapshot = build_decision_option_snapshot(contract, [quote], DECISION)
    assert snapshot.contract is contract
    assert snapshot.selected_quote is quote
    with pytest.raises(AsOfSelectionIntegrityError):
        build_decision_option_snapshot(
            contract,
            [_quote(quote_ts_utc=DECISION, sequence_no=1), _quote(quote_ts_utc=DECISION, sequence_no=2)],
            DECISION,
        )
