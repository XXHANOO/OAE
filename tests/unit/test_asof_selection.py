from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import inspect
from zoneinfo import ZoneInfo

import pytest

import oae.data.asof as asof
from oae.data.asof import AsOfSelectionIntegrityError, select_asof_quote
from oae.enums import QualityStatus
from oae.schemas.quotes import OptionQuoteRecord


UTC = timezone.utc
ET = ZoneInfo("America/New_York")
DECISION = datetime(2026, 7, 15, 17, 30, tzinfo=UTC)


def _quote(**overrides: object) -> OptionQuoteRecord:
    values: dict[str, object] = {
        "contract_id": "opaque-contract-id",
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
        "source": "TEST_VENDOR",
        "raw_file_id": "raw-file-a",
    }
    values.update(overrides)
    return OptionQuoteRecord.model_validate(values)


def test_asof_select_001_to_003_public_api_and_s2_04_apis_exist() -> None:
    assert asof.select_asof_quote is select_asof_quote
    assert issubclass(AsOfSelectionIntegrityError, RuntimeError)
    assert callable(asof.quote_age_seconds)
    assert callable(asof.classify_quote_quality)


def test_asof_select_004_empty_sequence_returns_none() -> None:
    assert select_asof_quote([], DECISION) is None


def test_asof_select_005_to_006_single_and_exact_decision_are_eligible() -> None:
    before = _quote()
    exact = _quote(quote_ts_utc=DECISION)
    assert select_asof_quote([before], DECISION) is before
    assert select_asof_quote([exact], DECISION) is exact


def test_asof_select_007_to_009_future_quotes_are_ignored_not_nearest() -> None:
    future = _quote(quote_ts_utc=DECISION + timedelta(microseconds=1))
    old = _quote(quote_ts_utc=DECISION - timedelta(seconds=7))
    assert select_asof_quote([future], DECISION) is None
    assert select_asof_quote([old, future], DECISION) is old


def test_asof_select_010_to_012_latest_eligible_is_order_independent() -> None:
    older = _quote(quote_ts_utc=DECISION - timedelta(seconds=3))
    latest = _quote(quote_ts_utc=DECISION - timedelta(seconds=1))
    future = _quote(quote_ts_utc=DECISION + timedelta(seconds=1))
    records = [future, older, latest]
    assert select_asof_quote(records, DECISION) is latest
    assert select_asof_quote(list(reversed(records)), DECISION) is latest


def test_asof_select_013_timezone_equivalent_decisions_have_same_winner() -> None:
    winner = _quote(quote_ts_utc=DECISION)
    et_decision = DECISION.astimezone(ET)
    assert select_asof_quote([winner], DECISION) is winner
    assert select_asof_quote([winner], et_decision) is winner


def test_asof_select_014_to_015_naive_timestamps_fail_closed() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        select_asof_quote([], datetime(2026, 7, 15, 13, 30))

    values = _quote().model_dump(mode="python")
    values["quote_ts_utc"] = datetime(2026, 7, 15, 17, 29, 59)
    malformed = OptionQuoteRecord.model_construct(**values)
    with pytest.raises(ValueError, match="timezone-aware"):
        select_asof_quote([malformed], DECISION)


@pytest.mark.parametrize(
    ("overrides", "expected_status"),
    [
        ({"quote_ts_utc": DECISION - timedelta(seconds=3)}, QualityStatus.STALE),
        ({"bid_px": Decimal("1.00"), "ask_px": Decimal("1.00")}, QualityStatus.LOCKED),
        ({"bid_px": Decimal("1.10"), "ask_px": Decimal("1.00")}, QualityStatus.CROSSED),
        ({"bid_px": Decimal("0")}, QualityStatus.ZERO_BID),
        ({"bid_size": 0}, QualityStatus.ZERO_SIZE),
    ],
)
def test_asof_select_016_to_021_quality_never_filters_latest(
    overrides: dict[str, object], expected_status: QualityStatus
) -> None:
    values = {"quote_ts_utc": DECISION - timedelta(seconds=3)}
    values.update(overrides)
    latest = _quote(**values)
    older = _quote(quote_ts_utc=latest.quote_ts_utc - timedelta(microseconds=1))
    assert asof.classify_quote_quality(latest, DECISION, 2.0) is expected_status
    assert select_asof_quote([older, latest], DECISION) is latest


def test_asof_select_021_newer_invalid_beats_older_valid() -> None:
    older_valid = _quote(quote_ts_utc=DECISION - timedelta(seconds=2))
    newer_invalid = _quote(
        quote_ts_utc=DECISION - timedelta(seconds=1),
        bid_px=Decimal("1.10"),
        ask_px=Decimal("1.00"),
    )
    assert asof.classify_quote_quality(older_valid, DECISION, 2.0) is QualityStatus.VALID
    assert asof.classify_quote_quality(newer_invalid, DECISION, 2.0) is QualityStatus.CROSSED
    assert select_asof_quote([older_valid, newer_invalid], DECISION) is newer_invalid


def test_asof_select_022_and_046_to_047_signature_has_only_required_parameters() -> None:
    signature = inspect.signature(select_asof_quote)
    assert list(signature.parameters) == ["quotes", "decision_ts"]
    assert {
        "max_age_seconds", "quality_status", "sequence_no", "tie_break",
        "dedupe", "prefer_sequence", "quality", "source_quote_id",
    }.isdisjoint(signature.parameters)
    assert signature.return_annotation == OptionQuoteRecord | None


def test_asof_select_023_does_not_call_quality_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    quote = _quote()

    def fail(*args: object, **kwargs: object) -> QualityStatus:
        raise AssertionError("quality classifier must not be called")

    monkeypatch.setattr(asof, "classify_quote_quality", fail)
    assert select_asof_quote([quote], DECISION) is quote


def test_asof_select_024_to_026_exact_duplicate_maximum_is_accepted() -> None:
    duplicate = _quote(quote_ts_utc=DECISION)
    same = _quote(quote_ts_utc=DECISION)
    selected = select_asof_quote([duplicate, same, same], DECISION)
    assert selected.model_dump(mode="python") == duplicate.model_dump(mode="python")
    assert (
        select_asof_quote([same, duplicate], DECISION).model_dump(mode="python")
        == duplicate.model_dump(mode="python")
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"bid_px": Decimal("1.01")},
        {"ask_px": Decimal("1.11")},
        {"bid_size": 2},
        {"sequence_no": 101},
        {"raw_file_id": "raw-file-b"},
        {"quote_condition": "HALT"},
    ],
)
def test_asof_select_027_to_036_distinct_maximum_records_fail(
    overrides: dict[str, object]
) -> None:
    first = _quote(quote_ts_utc=DECISION, sequence_no=100)
    second = _quote(quote_ts_utc=DECISION, **overrides)
    with pytest.raises(AsOfSelectionIntegrityError, match="distinct quotes"):
        select_asof_quote([first, second], DECISION)
    with pytest.raises(AsOfSelectionIntegrityError, match="distinct quotes"):
        select_asof_quote([second, first], DECISION)


def test_asof_select_037_older_ambiguity_does_not_block_later_unique_quote() -> None:
    earlier = DECISION - timedelta(seconds=2)
    conflicting_a = _quote(quote_ts_utc=earlier, bid_px=Decimal("1.00"))
    conflicting_b = _quote(quote_ts_utc=earlier, bid_px=Decimal("1.01"))
    winner = _quote(quote_ts_utc=DECISION - timedelta(seconds=1))
    assert (
        select_asof_quote([conflicting_a, winner, conflicting_b], DECISION)
        is winner
    )


def test_asof_select_038_different_raw_files_across_timestamps_are_permitted() -> None:
    older = _quote(raw_file_id="raw-file-a")
    winner = _quote(
        raw_file_id="raw-file-b", quote_ts_utc=DECISION - timedelta(microseconds=1)
    )
    assert select_asof_quote([older, winner], DECISION) is winner


@pytest.mark.parametrize(
    "mismatch",
    [
        {"contract_id": "other-contract"},
        {"source": "OTHER_VENDOR"},
        {"source": " TEST_VENDOR"},
        {"contract_id": "future-contract", "quote_ts_utc": DECISION + timedelta(seconds=1)},
        {"source": "FUTURE_VENDOR", "quote_ts_utc": DECISION + timedelta(seconds=1)},
    ],
)
def test_asof_select_039_to_043_mixed_streams_always_fail(
    mismatch: dict[str, object]
) -> None:
    with pytest.raises(AsOfSelectionIntegrityError, match="source-scoped"):
        select_asof_quote([_quote(), _quote(**mismatch)], DECISION)


def test_asof_select_044_to_045_does_not_mutate_and_returns_existing_winner() -> None:
    records = [_quote(quote_ts_utc=DECISION - timedelta(seconds=2)), _quote()]
    before = [quote.model_dump(mode="python") for quote in records]
    selected = select_asof_quote(records, DECISION)
    assert selected is records[1]
    assert [quote.model_dump(mode="python") for quote in records] == before


def test_asof_select_048_empty_and_all_future_never_synthesize_missing_status() -> None:
    assert select_asof_quote([], DECISION) is None
    assert (
        select_asof_quote(
            [_quote(quote_ts_utc=DECISION + timedelta(seconds=1))], DECISION
        )
        is None
    )
