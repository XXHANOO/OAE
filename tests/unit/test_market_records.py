from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from oae.enums import QualityStatus
from oae.schemas.market import IndexBar1mRecord


UTC = timezone.utc
NEW_YORK = ZoneInfo("America/New_York")
CANONICAL_FIELDS = [
    "symbol",
    "session_date_et",
    "bar_start_ts_utc",
    "bar_end_ts_utc",
    "open",
    "high",
    "low",
    "close",
    "observation_count",
    "source",
    "raw_file_id",
    "quality_status",
]


def _record_data(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "symbol": "SPX",
        "session_date_et": date(2026, 7, 15),
        "bar_start_ts_utc": datetime(2026, 7, 15, 17, 29, tzinfo=UTC),
        "bar_end_ts_utc": datetime(2026, 7, 15, 17, 30, tzinfo=UTC),
        "open": Decimal("6375.125001"),
        "high": Decimal("6376.250002"),
        "low": Decimal("6374.500003"),
        "close": Decimal("6375.875004"),
        "observation_count": 42,
        "source": "TEST_VENDOR",
        "raw_file_id": "vendor:opaque/bar-file#001",
        "quality_status": QualityStatus.VALID,
    }
    values.update(overrides)
    return values


def _record(**overrides: object) -> IndexBar1mRecord:
    return IndexBar1mRecord.model_validate(_record_data(**overrides))


def test_index_bar_001_exact_field_contract() -> None:
    assert list(IndexBar1mRecord.model_fields) == CANONICAL_FIELDS


def test_index_bar_002_strict_extra_field_rejection() -> None:
    with pytest.raises(ValidationError):
        IndexBar1mRecord.model_validate(
            {**_record_data(), "unexpected": "forbidden"}
        )


def test_index_bar_003_frozen_model() -> None:
    record = _record()

    with pytest.raises(ValidationError):
        record.source = "MUTATED"  # type: ignore[misc]


def test_index_bar_004_canonical_spx_accepted() -> None:
    assert _record(symbol="SPX").symbol == "SPX"


@pytest.mark.parametrize("symbol", ["XSP", "^SPX", "spx", " SPX "])
def test_index_bar_005_non_spx_symbol_rejected(symbol: str) -> None:
    with pytest.raises(ValidationError, match="exactly 'SPX'"):
        _record(symbol=symbol)


def test_index_bar_006_naive_start_timestamp_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _record(bar_start_ts_utc=datetime(2026, 7, 15, 13, 29))


def test_index_bar_007_naive_end_timestamp_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _record(bar_end_ts_utc=datetime(2026, 7, 15, 13, 30))


def test_index_bar_008_aware_et_timestamps_canonicalize_to_utc() -> None:
    record = _record(
        bar_start_ts_utc=datetime(2026, 7, 15, 13, 29, tzinfo=NEW_YORK),
        bar_end_ts_utc=datetime(2026, 7, 15, 13, 30, tzinfo=NEW_YORK),
    )

    assert record.bar_start_ts_utc == datetime(
        2026,
        7,
        15,
        17,
        29,
        tzinfo=UTC,
    )
    assert record.bar_end_ts_utc == datetime(
        2026,
        7,
        15,
        17,
        30,
        tzinfo=UTC,
    )
    assert record.bar_start_ts_utc.tzinfo is UTC
    assert record.bar_end_ts_utc.tzinfo is UTC


def test_index_bar_009_winter_dst_conversion() -> None:
    record = _record(
        session_date_et=date(2026, 1, 15),
        bar_start_ts_utc=datetime(2026, 1, 15, 13, 29, tzinfo=NEW_YORK),
        bar_end_ts_utc=datetime(2026, 1, 15, 13, 30, tzinfo=NEW_YORK),
    )

    assert record.bar_start_ts_utc == datetime(
        2026,
        1,
        15,
        18,
        29,
        tzinfo=UTC,
    )
    assert record.bar_end_ts_utc == datetime(
        2026,
        1,
        15,
        18,
        30,
        tzinfo=UTC,
    )


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (
            datetime(2026, 7, 15, 17, 30, tzinfo=UTC),
            datetime(2026, 7, 15, 17, 30, tzinfo=UTC),
        ),
        (
            datetime(2026, 7, 15, 17, 31, tzinfo=UTC),
            datetime(2026, 7, 15, 17, 30, tzinfo=UTC),
        ),
    ],
)
def test_index_bar_010_start_must_precede_end(
    start: datetime,
    end: datetime,
) -> None:
    with pytest.raises(ValidationError, match="must precede"):
        _record(bar_start_ts_utc=start, bar_end_ts_utc=end)


def test_index_bar_011_exact_one_minute_interval() -> None:
    start = datetime(2026, 7, 15, 17, 29, 0, 123456, tzinfo=UTC)
    exact = _record(
        bar_start_ts_utc=start,
        bar_end_ts_utc=start + timedelta(seconds=60),
    )

    assert exact.bar_end_ts_utc - exact.bar_start_ts_utc == timedelta(
        seconds=60
    )

    for duration_seconds in (59, 61):
        with pytest.raises(ValidationError, match="exactly 60 seconds"):
            _record(
                bar_start_ts_utc=start,
                bar_end_ts_utc=start + timedelta(seconds=duration_seconds),
            )


def test_index_bar_012_decimal_prices_preserved() -> None:
    prices = {
        "open": Decimal("6375.123456789"),
        "high": Decimal("6376.987654321"),
        "low": Decimal("6374.000000001"),
        "close": Decimal("6375.555555555"),
    }

    record = _record(**prices)

    for field_name, expected in prices.items():
        value = getattr(record, field_name)
        assert isinstance(value, Decimal)
        assert value == expected


def test_index_bar_013_observation_count_nonnegative() -> None:
    with pytest.raises(ValidationError):
        _record(observation_count=-1)


def test_index_bar_014_zero_observations_structurally_allowed() -> None:
    assert _record(observation_count=0).observation_count == 0


def test_index_bar_015_source_required_non_empty_without_rewrite() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        _record(source="")

    assert _record(source=" Vendor Source ").source == " Vendor Source "


def test_index_bar_016_raw_file_id_required_non_empty_and_opaque() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        _record(raw_file_id="")

    opaque_id = "vendor:2026/07/15 file#part-A"
    assert _record(raw_file_id=opaque_id).raw_file_id == opaque_id


@pytest.mark.parametrize("quality_status", list(QualityStatus))
def test_index_bar_017_canonical_quality_status_accepted(
    quality_status: QualityStatus,
) -> None:
    record = _record(quality_status=quality_status.value)

    assert record.quality_status is quality_status


def test_index_bar_018_unknown_quality_rejected() -> None:
    with pytest.raises(ValidationError):
        _record(quality_status="NOT_A_CANONICAL_STATUS")


def test_index_bar_019_non_valid_quality_remains_representable() -> None:
    record = _record(quality_status=QualityStatus.STALE)

    assert record.quality_status is QualityStatus.STALE


def test_index_bar_020_no_premature_ohlc_quality_classification() -> None:
    suspect_prices = {
        "open": Decimal("100.123456789"),
        "high": Decimal("90.987654321"),
        "low": Decimal("110.000000001"),
        "close": Decimal("105.555555555"),
    }

    record = _record(
        **suspect_prices,
        quality_status=QualityStatus.UNKNOWN,
    )

    for field_name, expected in suspect_prices.items():
        assert getattr(record, field_name) == expected
    assert record.quality_status is QualityStatus.UNKNOWN


def test_index_bar_021_session_date_et_remains_explicit() -> None:
    explicit_date = date(1999, 12, 31)

    assert _record(session_date_et=explicit_date).session_date_et == explicit_date


def test_index_bar_022_model_dump_persistence_names() -> None:
    assert list(_record().model_dump()) == CANONICAL_FIELDS


def test_index_bar_does_not_apply_decision_time_filter() -> None:
    start = datetime(2026, 7, 15, 17, 30, tzinfo=UTC)
    record = _record(
        bar_start_ts_utc=start,
        bar_end_ts_utc=start + timedelta(minutes=1),
    )

    assert record.bar_start_ts_utc == start
    assert record.bar_end_ts_utc == start + timedelta(minutes=1)
