import inspect
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

import oae.data.asof as asof
from oae.data.asof import classify_quote_quality, quote_age_seconds
from oae.enums import QualityStatus
from oae.schemas.quotes import OptionQuoteRecord


UTC = timezone.utc
NEW_YORK = ZoneInfo("America/New_York")
DECISION_TS = datetime(2026, 7, 15, 17, 30, tzinfo=UTC)


def _quote(**overrides: object) -> OptionQuoteRecord:
    values: dict[str, object] = {
        "contract_id": "opaque-contract-id",
        "quote_ts_utc": DECISION_TS,
        "session_date_et": date(2026, 7, 15),
        "bid_px": Decimal("1.00"),
        "ask_px": Decimal("1.10"),
        "bid_size": 1,
        "ask_size": 1,
        "bid_exchange": None,
        "ask_exchange": None,
        "quote_condition": None,
        "sequence_no": None,
        "source": "TEST_VENDOR",
        "raw_file_id": "opaque-raw-file-id",
    }
    values.update(overrides)
    return OptionQuoteRecord.model_validate(values)


def _classify(
    quote: OptionQuoteRecord,
    decision_ts: datetime = DECISION_TS,
    max_age_seconds: float = 2.0,
) -> QualityStatus:
    return classify_quote_quality(quote, decision_ts, max_age_seconds)


def test_quote_quality_001_public_api_exists() -> None:
    assert asof.quote_age_seconds is quote_age_seconds
    assert asof.classify_quote_quality is classify_quote_quality


def test_quote_quality_002_no_asof_selector_yet() -> None:
    assert not hasattr(asof, "select_asof_quote")


def test_quote_quality_003_age_zero() -> None:
    assert quote_age_seconds(DECISION_TS, DECISION_TS) == 0.0


def test_quote_quality_004_exact_positive_age() -> None:
    quote_ts = DECISION_TS - timedelta(seconds=2)

    assert quote_age_seconds(quote_ts, DECISION_TS) == 2.0


def test_quote_quality_005_signed_future_age_is_not_clamped() -> None:
    quote_ts = DECISION_TS + timedelta(microseconds=1)

    assert quote_age_seconds(quote_ts, DECISION_TS) == -0.000001


def test_quote_quality_006_timezone_equivalent_instants() -> None:
    quote_ts_utc = DECISION_TS - timedelta(seconds=2)
    quote_ts_et = quote_ts_utc.astimezone(NEW_YORK)
    decision_ts_et = DECISION_TS.astimezone(NEW_YORK)

    assert quote_age_seconds(quote_ts_et, DECISION_TS) == 2.0
    assert quote_age_seconds(quote_ts_utc, decision_ts_et) == 2.0


def test_quote_quality_007_naive_quote_timestamp_rejected() -> None:
    naive_quote_ts = DECISION_TS.replace(tzinfo=None)

    with pytest.raises(ValueError, match="timezone-aware"):
        quote_age_seconds(naive_quote_ts, DECISION_TS)


def test_quote_quality_008_naive_decision_timestamp_rejected() -> None:
    naive_decision_ts = DECISION_TS.replace(tzinfo=None)

    with pytest.raises(ValueError, match="timezone-aware"):
        quote_age_seconds(DECISION_TS, naive_decision_ts)


def test_quote_quality_009_basic_valid_quote() -> None:
    assert _classify(_quote()) is QualityStatus.VALID


@pytest.mark.parametrize(
    ("age_microseconds", "expected"),
    [
        (1_999_999, QualityStatus.VALID),
        (2_000_000, QualityStatus.VALID),
        (2_000_001, QualityStatus.STALE),
    ],
)
def test_quote_quality_010_to_012_exact_microsecond_age_boundary(
    age_microseconds: int,
    expected: QualityStatus,
) -> None:
    quote = _quote(
        quote_ts_utc=DECISION_TS - timedelta(microseconds=age_microseconds)
    )

    assert _classify(quote) is expected


@pytest.mark.parametrize("bid_px", [Decimal("0"), Decimal("-0.01")])
def test_quote_quality_013_014_nonpositive_bid_is_zero_bid(
    bid_px: Decimal,
) -> None:
    assert _classify(_quote(bid_px=bid_px)) is QualityStatus.ZERO_BID


def test_quote_quality_015_locked_quote() -> None:
    assert _classify(
        _quote(bid_px=Decimal("1.25"), ask_px=Decimal("1.25"))
    ) is QualityStatus.LOCKED


def test_quote_quality_016_crossed_quote() -> None:
    assert _classify(
        _quote(bid_px=Decimal("1.25"), ask_px=Decimal("1.20"))
    ) is QualityStatus.CROSSED


@pytest.mark.parametrize(
    ("bid_size", "ask_size"),
    [(0, 1), (1, 0), (-1, 1)],
)
def test_quote_quality_017_to_019_subminimum_size_is_zero_size(
    bid_size: int,
    ask_size: int,
) -> None:
    assert _classify(
        _quote(bid_size=bid_size, ask_size=ask_size)
    ) is QualityStatus.ZERO_SIZE


def test_quote_quality_020_minimum_sizes_are_valid() -> None:
    assert _classify(_quote(bid_size=1, ask_size=1)) is QualityStatus.VALID


def test_quote_quality_021_future_quote_fails_closed() -> None:
    quote = _quote(quote_ts_utc=DECISION_TS + timedelta(microseconds=1))

    with pytest.raises(ValueError, match="later than decision_ts"):
        _classify(quote)


def test_quote_quality_022_future_failure_precedes_diagnostic_status() -> None:
    quote = _quote(
        quote_ts_utc=DECISION_TS + timedelta(microseconds=1),
        bid_px=Decimal("0"),
        ask_px=Decimal("-1"),
        bid_size=0,
        ask_size=0,
    )

    with pytest.raises(ValueError, match="later than decision_ts"):
        _classify(quote)


@pytest.mark.parametrize(
    ("bid_px", "ask_px"),
    [(Decimal("0"), Decimal("0")), (Decimal("0"), Decimal("-1"))],
)
def test_quote_quality_023_zero_bid_precedence(
    bid_px: Decimal,
    ask_px: Decimal,
) -> None:
    quote = _quote(
        quote_ts_utc=DECISION_TS - timedelta(seconds=3),
        bid_px=bid_px,
        ask_px=ask_px,
        bid_size=0,
        ask_size=0,
    )

    assert _classify(quote) is QualityStatus.ZERO_BID


def test_quote_quality_024_locked_precedence() -> None:
    quote = _quote(
        quote_ts_utc=DECISION_TS - timedelta(seconds=3),
        bid_px=Decimal("1.25"),
        ask_px=Decimal("1.25"),
        bid_size=0,
        ask_size=0,
    )

    assert _classify(quote) is QualityStatus.LOCKED


def test_quote_quality_025_crossed_precedence() -> None:
    quote = _quote(
        quote_ts_utc=DECISION_TS - timedelta(seconds=3),
        bid_px=Decimal("1.25"),
        ask_px=Decimal("1.20"),
        bid_size=0,
        ask_size=0,
    )

    assert _classify(quote) is QualityStatus.CROSSED


def test_quote_quality_026_zero_size_precedence() -> None:
    quote = _quote(
        quote_ts_utc=DECISION_TS - timedelta(seconds=3),
        bid_size=0,
    )

    assert _classify(quote) is QualityStatus.ZERO_SIZE


def test_quote_quality_027_stale_when_otherwise_valid() -> None:
    quote = _quote(quote_ts_utc=DECISION_TS - timedelta(microseconds=2_000_001))

    assert _classify(quote) is QualityStatus.STALE


@pytest.mark.parametrize(
    "quote_condition",
    [None, "", "HALT", "UNKNOWN_VENDOR_FLAG", "X"],
)
def test_quote_quality_028_to_030_quote_condition_is_ignored(
    quote_condition: str | None,
) -> None:
    status = _classify(_quote(quote_condition=quote_condition))

    assert status is QualityStatus.VALID
    assert status is not QualityStatus.HALTED


@pytest.mark.parametrize("sequence_no", [None, 1, 999_999])
def test_quote_quality_031_sequence_number_has_no_effect(
    sequence_no: int | None,
) -> None:
    assert _classify(_quote(sequence_no=sequence_no)) is QualityStatus.VALID


@pytest.mark.parametrize(
    ("source", "raw_file_id"),
    [("VENDOR_A", "raw-A"), (" Vendor B ", "opaque/raw file B")],
)
def test_quote_quality_032_source_and_lineage_have_no_effect(
    source: str,
    raw_file_id: str,
) -> None:
    assert _classify(
        _quote(source=source, raw_file_id=raw_file_id)
    ) is QualityStatus.VALID


@pytest.mark.parametrize("max_age_seconds", [2.0, 2])
def test_quote_quality_033_frozen_max_age_is_accepted(
    max_age_seconds: float,
) -> None:
    assert _classify(
        _quote(), max_age_seconds=max_age_seconds
    ) is QualityStatus.VALID


@pytest.mark.parametrize("max_age_seconds", [3.0, 2.001, 1.0])
def test_quote_quality_034_to_036_nonfrozen_max_age_rejected(
    max_age_seconds: float,
) -> None:
    with pytest.raises(ValueError, match="frozen 2.0"):
        _classify(_quote(), max_age_seconds=max_age_seconds)


@pytest.mark.parametrize(
    "max_age_seconds",
    [-1.0, float("nan"), float("inf"), float("-inf")],
)
def test_quote_quality_037_invalid_numeric_max_age_rejected(
    max_age_seconds: float,
) -> None:
    with pytest.raises(ValueError, match="frozen 2.0"):
        _classify(_quote(), max_age_seconds=max_age_seconds)


@pytest.mark.parametrize("max_age_seconds", [True, False])
def test_quote_quality_038_bool_max_age_rejected(
    max_age_seconds: bool,
) -> None:
    with pytest.raises(ValueError, match="frozen 2.0"):
        _classify(_quote(), max_age_seconds=max_age_seconds)


def test_quote_quality_039_no_millisecond_truncation() -> None:
    statuses = [
        _classify(
            _quote(
                quote_ts_utc=DECISION_TS - timedelta(microseconds=microseconds)
            )
        )
        for microseconds in (1_999_999, 2_000_000, 2_000_001)
    ]

    assert statuses == [
        QualityStatus.VALID,
        QualityStatus.VALID,
        QualityStatus.STALE,
    ]


def test_quote_quality_040_quote_is_not_mutated() -> None:
    quote = _quote(quote_condition=" raw ", sequence_no=17)
    before = quote.model_dump(mode="python")

    assert _classify(quote) is QualityStatus.VALID
    assert quote.model_dump(mode="python") == before


def test_quote_quality_041_only_expected_statuses_are_emitted() -> None:
    quotes = [
        _quote(),
        _quote(quote_ts_utc=DECISION_TS - timedelta(seconds=3)),
        _quote(bid_px=Decimal("1.25"), ask_px=Decimal("1.20")),
        _quote(bid_px=Decimal("1.25"), ask_px=Decimal("1.25")),
        _quote(bid_px=Decimal("0")),
        _quote(bid_size=0),
    ]

    statuses = {_classify(quote) for quote in quotes}

    assert statuses == {
        QualityStatus.VALID,
        QualityStatus.STALE,
        QualityStatus.CROSSED,
        QualityStatus.LOCKED,
        QualityStatus.ZERO_BID,
        QualityStatus.ZERO_SIZE,
    }
    assert statuses.isdisjoint(
        {
            QualityStatus.MISSING,
            QualityStatus.OUT_OF_ORDER,
            QualityStatus.DUPLICATE,
            QualityStatus.HALTED,
            QualityStatus.UNKNOWN,
        }
    )


def test_quote_quality_042_classifier_is_single_record_only() -> None:
    signature = inspect.signature(classify_quote_quality)

    assert list(signature.parameters) == [
        "quote",
        "decision_ts",
        "max_age_seconds",
    ]
    assert signature.parameters["quote"].annotation is OptionQuoteRecord
    assert signature.return_annotation is QualityStatus
    assert not any(
        parameter in signature.parameters
        for parameter in ("quotes", "sequence", "tie_break")
    )
