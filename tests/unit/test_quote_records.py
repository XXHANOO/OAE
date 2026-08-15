from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from oae.schemas.quotes import OptionQuoteRecord


UTC = timezone.utc
NEW_YORK = ZoneInfo("America/New_York")
CANONICAL_FIELDS = [
    "contract_id",
    "quote_ts_utc",
    "session_date_et",
    "bid_px",
    "ask_px",
    "bid_size",
    "ask_size",
    "bid_exchange",
    "ask_exchange",
    "quote_condition",
    "sequence_no",
    "source",
    "raw_file_id",
]


def _record_data(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "contract_id": "provider:opaque-contract/001",
        "quote_ts_utc": datetime(
            2026,
            7,
            15,
            17,
            29,
            59,
            123456,
            tzinfo=UTC,
        ),
        "session_date_et": date(2026, 7, 15),
        "bid_px": Decimal("1.123456789"),
        "ask_px": Decimal("1.234567891"),
        "bid_size": 10,
        "ask_size": 12,
        "bid_exchange": "BID VENUE",
        "ask_exchange": "ASK VENUE",
        "quote_condition": "RAW_CONDITION",
        "sequence_no": 123456789,
        "source": "TEST_VENDOR",
        "raw_file_id": "provider:opaque/raw-file#001",
    }
    values.update(overrides)
    return values


def _record(**overrides: object) -> OptionQuoteRecord:
    return OptionQuoteRecord.model_validate(_record_data(**overrides))


def test_option_quote_001_exact_field_contract() -> None:
    assert list(OptionQuoteRecord.model_fields) == CANONICAL_FIELDS


def test_option_quote_002_strict_extra_field_rejection() -> None:
    with pytest.raises(ValidationError):
        OptionQuoteRecord.model_validate(
            {**_record_data(), "unexpected": "forbidden"}
        )


def test_option_quote_003_frozen_model() -> None:
    record = _record()

    with pytest.raises(ValidationError):
        record.source = "MUTATED"  # type: ignore[misc]


@pytest.mark.parametrize(
    "field_name",
    ["bid_exchange", "ask_exchange", "quote_condition", "sequence_no"],
)
def test_option_quote_004_nullable_fields_remain_required(
    field_name: str,
) -> None:
    values = _record_data()
    del values[field_name]

    with pytest.raises(ValidationError):
        OptionQuoteRecord.model_validate(values)


def test_option_quote_005_opaque_contract_id_accepted() -> None:
    opaque_id = "not-a-uuid/vendor contract:ABC#17"

    assert _record(contract_id=opaque_id).contract_id == opaque_id


def test_option_quote_006_empty_contract_id_rejected() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        _record(contract_id="")


def test_option_quote_007_no_contract_master_lookup() -> None:
    synthetic_id = "synthetic-contract-without-master-row"

    assert _record(contract_id=synthetic_id).contract_id == synthetic_id


def test_option_quote_008_naive_quote_timestamp_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _record(quote_ts_utc=datetime(2026, 7, 15, 13, 29, 59, 123456))


def test_option_quote_009_summer_et_timestamp_canonicalizes_to_utc() -> None:
    record = _record(
        quote_ts_utc=datetime(
            2026,
            7,
            15,
            13,
            29,
            59,
            123456,
            tzinfo=NEW_YORK,
        )
    )

    assert record.quote_ts_utc == datetime(
        2026,
        7,
        15,
        17,
        29,
        59,
        123456,
        tzinfo=UTC,
    )
    assert record.quote_ts_utc.tzinfo is UTC


def test_option_quote_010_winter_dst_conversion() -> None:
    record = _record(
        session_date_et=date(2026, 1, 15),
        quote_ts_utc=datetime(
            2026,
            1,
            15,
            13,
            29,
            59,
            654321,
            tzinfo=NEW_YORK,
        ),
    )

    assert record.quote_ts_utc == datetime(
        2026,
        1,
        15,
        18,
        29,
        59,
        654321,
        tzinfo=UTC,
    )


def test_option_quote_011_subsecond_timestamp_preserved() -> None:
    timestamp = datetime(2026, 7, 15, 17, 29, 59, 999999, tzinfo=UTC)

    assert _record(quote_ts_utc=timestamp).quote_ts_utc == timestamp


def test_option_quote_012_explicit_session_date_et_retained() -> None:
    explicit_date = date(1999, 12, 31)

    assert _record(session_date_et=explicit_date).session_date_et == explicit_date


def test_option_quote_013_decimal_prices_preserved() -> None:
    bid = Decimal("1.00000000123456789")
    ask = Decimal("1.99999999876543211")
    record = _record(bid_px=bid, ask_px=ask)

    assert isinstance(record.bid_px, Decimal)
    assert isinstance(record.ask_px, Decimal)
    assert record.bid_px == bid
    assert record.ask_px == ask


def test_option_quote_014_locked_quote_structurally_accepted() -> None:
    price = Decimal("1.250000")
    record = _record(bid_px=price, ask_px=price)

    assert record.bid_px == record.ask_px == price


def test_option_quote_015_crossed_quote_structurally_accepted() -> None:
    record = _record(bid_px=Decimal("1.50"), ask_px=Decimal("1.25"))

    assert record.bid_px > record.ask_px


def test_option_quote_016_zero_bid_structurally_accepted() -> None:
    assert _record(bid_px=Decimal("0")).bid_px == Decimal("0")


def test_option_quote_017_zero_bid_size_structurally_accepted() -> None:
    assert _record(bid_size=0).bid_size == 0


def test_option_quote_018_zero_ask_size_structurally_accepted() -> None:
    assert _record(ask_size=0).ask_size == 0


def test_option_quote_019_no_premature_quality_field() -> None:
    assert "quality_status" not in OptionQuoteRecord.model_fields
    assert "quote_valid" not in OptionQuoteRecord.model_fields


def test_option_quote_020_bid_exchange_none_accepted() -> None:
    assert _record(bid_exchange=None).bid_exchange is None


def test_option_quote_021_ask_exchange_none_accepted() -> None:
    assert _record(ask_exchange=None).ask_exchange is None


def test_option_quote_022_exchange_strings_preserved() -> None:
    record = _record(
        bid_exchange=" Bid Venue MixedCase ",
        ask_exchange=" Ask Venue MixedCase ",
    )

    assert record.bid_exchange == " Bid Venue MixedCase "
    assert record.ask_exchange == " Ask Venue MixedCase "


def test_option_quote_023_quote_condition_none_accepted() -> None:
    assert _record(quote_condition=None).quote_condition is None


def test_option_quote_024_quote_condition_raw_text_preserved() -> None:
    raw_condition = " VendorCondition:X-17 "

    assert _record(quote_condition=raw_condition).quote_condition == raw_condition


@pytest.mark.parametrize(
    "field_name",
    ["bid_exchange", "ask_exchange", "quote_condition"],
)
def test_option_quote_025_empty_optional_vendor_text_not_rewritten(
    field_name: str,
) -> None:
    record = _record(**{field_name: ""})

    assert getattr(record, field_name) == ""


def test_option_quote_026_sequence_no_none_accepted() -> None:
    assert _record(sequence_no=None).sequence_no is None


def test_option_quote_027_sequence_no_integer_preserved() -> None:
    sequence_no = 9_876_543_210

    assert _record(sequence_no=sequence_no).sequence_no == sequence_no


def test_option_quote_028_same_timestamp_has_no_dto_tie_break() -> None:
    timestamp = datetime(2026, 7, 15, 17, 29, 59, 123456, tzinfo=UTC)
    first = _record(
        quote_ts_utc=timestamp,
        bid_px=Decimal("1.00"),
        sequence_no=10,
    )
    second = _record(
        quote_ts_utc=timestamp,
        bid_px=Decimal("1.01"),
        sequence_no=11,
    )

    assert first.quote_ts_utc == second.quote_ts_utc
    assert first.bid_px != second.bid_px
    assert first.sequence_no != second.sequence_no


def test_option_quote_029_source_required_non_empty_without_rewrite() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        _record(source="")

    assert _record(source=" Vendor Source ").source == " Vendor Source "


def test_option_quote_030_raw_file_id_required_non_empty_and_opaque() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        _record(raw_file_id="")

    opaque_id = "not-a-uuid/raw source:part A#9"
    assert _record(raw_file_id=opaque_id).raw_file_id == opaque_id


def test_option_quote_031_no_raw_manifest_lookup() -> None:
    synthetic_id = "synthetic-raw-file-without-manifest-row"

    assert _record(raw_file_id=synthetic_id).raw_file_id == synthetic_id


def test_option_quote_032_no_decision_time_filter() -> None:
    post_decision = datetime(
        2026,
        7,
        15,
        13,
        30,
        0,
        1000,
        tzinfo=NEW_YORK,
    )

    assert _record(quote_ts_utc=post_decision).quote_ts_utc == datetime(
        2026,
        7,
        15,
        17,
        30,
        0,
        1000,
        tzinfo=UTC,
    )


def test_option_quote_033_no_freshness_filter() -> None:
    old_quote = datetime(2026, 7, 15, 15, 0, tzinfo=UTC)
    record = _record(quote_ts_utc=old_quote)

    assert record.quote_ts_utc == old_quote
    assert "quote_age" not in OptionQuoteRecord.model_fields


def test_option_quote_034_no_future_schema_expansion() -> None:
    assert "recv_ts_utc" not in OptionQuoteRecord.model_fields
    assert "source_quote_id" not in OptionQuoteRecord.model_fields
    assert "quote_age_ms" not in OptionQuoteRecord.model_fields


def test_option_quote_035_model_dump_persistence_names() -> None:
    assert list(_record().model_dump()) == CANONICAL_FIELDS
