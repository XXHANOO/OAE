from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from oae.enums import ExerciseStyle, OptionType, SettlementStyle
from oae.schemas.options import OptionContractRecord


UTC = timezone.utc
NEW_YORK = ZoneInfo("America/New_York")
CANONICAL_FIELDS = [
    "contract_id",
    "vendor_symbol",
    "product",
    "root_symbol",
    "underlying",
    "option_type",
    "strike",
    "expiration_date",
    "settlement_style",
    "exercise_style",
    "multiplier",
    "series_type",
    "expiration_ts_utc",
    "first_seen_date",
    "last_seen_date",
    "source",
]


def _record_data(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "contract_id": "vendor:SPXW/2026-07-17/C/6400",
        "vendor_symbol": "SPXW260717C06400000",
        "product": "SPX",
        "root_symbol": "SPXW",
        "underlying": "SPX",
        "option_type": OptionType.CALL,
        "strike": Decimal("6400.1250"),
        "expiration_date": date(2026, 7, 17),
        "settlement_style": SettlementStyle.PM,
        "exercise_style": ExerciseStyle.EUROPEAN,
        "multiplier": 100,
        "series_type": "PM_WEEKLY_VENDOR_TEXT",
        "expiration_ts_utc": datetime(2026, 7, 17, 20, 15, tzinfo=UTC),
        "first_seen_date": date(2026, 6, 1),
        "last_seen_date": date(2026, 7, 17),
        "source": "TEST_VENDOR",
    }
    values.update(overrides)
    return values


def _record(**overrides: object) -> OptionContractRecord:
    return OptionContractRecord.model_validate(_record_data(**overrides))


def test_option_contract_001_exact_field_contract() -> None:
    assert list(OptionContractRecord.model_fields) == CANONICAL_FIELDS


def test_option_contract_002_strict_extra_field_rejection() -> None:
    with pytest.raises(ValidationError):
        OptionContractRecord.model_validate(
            {**_record_data(), "unexpected": "forbidden"}
        )


def test_option_contract_003_frozen_model() -> None:
    record = _record()

    with pytest.raises(ValidationError):
        record.source = "MUTATED"  # type: ignore[misc]


def test_option_contract_004_opaque_contract_id_accepted() -> None:
    opaque_id = "vendor:SPXW/2026-07-17/C/6400"

    assert _record(contract_id=opaque_id).contract_id == opaque_id


def test_option_contract_005_empty_contract_id_rejected() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        _record(contract_id="")


def test_option_contract_006_no_contract_id_derivation() -> None:
    first_id = "provider-A:opaque-series-001"
    second_id = "provider-A:opaque-series-002"

    assert _record(contract_id=first_id).contract_id == first_id
    assert _record(contract_id=second_id).contract_id == second_id


@pytest.mark.parametrize(
    "field_name",
    ["vendor_symbol", "product", "root_symbol", "underlying", "source"],
)
def test_option_contract_007_required_identity_strings(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        _record(**{field_name: ""})


def test_option_contract_008_strings_are_not_silently_normalized() -> None:
    record = _record(
        vendor_symbol=" VendorSymbol MixedCase ",
        product=" Product MixedCase ",
        root_symbol=" Root MixedCase ",
        underlying=" Underlying MixedCase ",
        source=" Vendor Source MixedCase ",
    )

    assert record.vendor_symbol == " VendorSymbol MixedCase "
    assert record.product == " Product MixedCase "
    assert record.root_symbol == " Root MixedCase "
    assert record.underlying == " Underlying MixedCase "
    assert record.source == " Vendor Source MixedCase "


def test_option_contract_009_spxw_root_semantics() -> None:
    record = _record(product="SPX", underlying="SPX", root_symbol="SPXW")

    assert record.product == "SPX"
    assert record.underlying == "SPX"
    assert record.root_symbol == "SPXW"


def test_option_contract_010_xsp_contract_structurally_representable() -> None:
    record = _record(
        product="XSP",
        underlying="XSP",
        root_symbol="XSP",
        settlement_style=SettlementStyle.AM,
        expiration_date=date(2026, 8, 21),
    )

    assert record.product == "XSP"
    assert record.underlying == "XSP"
    assert record.root_symbol == "XSP"
    assert record.settlement_style is SettlementStyle.AM
    assert record.expiration_date == date(2026, 8, 21)


def test_option_contract_011_call_accepted() -> None:
    assert _record(option_type="C").option_type is OptionType.CALL


def test_option_contract_012_put_accepted() -> None:
    assert _record(option_type="P").option_type is OptionType.PUT


def test_option_contract_013_unknown_option_type_rejected() -> None:
    with pytest.raises(ValidationError):
        _record(option_type="UNKNOWN")


def test_option_contract_014_decimal_strike_preserved() -> None:
    strike = Decimal("6400.123456789")
    record = _record(strike=strike)

    assert isinstance(record.strike, Decimal)
    assert record.strike == strike


def test_option_contract_015_pm_settlement_accepted() -> None:
    record = _record(settlement_style="PM")

    assert record.settlement_style is SettlementStyle.PM


def test_option_contract_016_am_settlement_accepted() -> None:
    record = _record(settlement_style="AM")

    assert record.settlement_style is SettlementStyle.AM


def test_option_contract_017_unknown_settlement_style_rejected() -> None:
    with pytest.raises(ValidationError):
        _record(settlement_style="UNKNOWN")


@pytest.mark.parametrize("exercise_style", list(ExerciseStyle))
def test_option_contract_018_exercise_style_enum_accepted(
    exercise_style: ExerciseStyle,
) -> None:
    record = _record(exercise_style=exercise_style.value)

    assert record.exercise_style is exercise_style


def test_option_contract_019_unknown_exercise_style_rejected() -> None:
    with pytest.raises(ValidationError):
        _record(exercise_style="UNKNOWN")


def test_option_contract_020_positive_strict_multiplier() -> None:
    assert _record(multiplier=100).multiplier == 100


@pytest.mark.parametrize("multiplier", [0, -1, True, 100.0, "100"])
def test_option_contract_021_invalid_multiplier_rejected(
    multiplier: object,
) -> None:
    with pytest.raises(ValidationError):
        _record(multiplier=multiplier)


def test_option_contract_022_multiplier_not_hard_coded_to_100() -> None:
    assert _record(multiplier=10).multiplier == 10


def test_option_contract_023_nullable_series_type() -> None:
    assert _record(series_type=None).series_type is None


def test_option_contract_024_series_type_preserved() -> None:
    series_type = " PM_WEEKLY_VENDOR_TEXT "

    assert _record(series_type=series_type).series_type == series_type
    assert _record(series_type="").series_type == ""


def test_option_contract_025_naive_expiration_timestamp_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _record(expiration_ts_utc=datetime(2026, 7, 17, 16, 15))


def test_option_contract_026_aware_expiration_timestamp_canonicalizes_to_utc(
) -> None:
    record = _record(
        expiration_ts_utc=datetime(
            2026,
            7,
            17,
            16,
            15,
            tzinfo=NEW_YORK,
        )
    )

    assert record.expiration_ts_utc == datetime(
        2026,
        7,
        17,
        20,
        15,
        tzinfo=UTC,
    )
    assert record.expiration_ts_utc.tzinfo is UTC


def test_option_contract_027_dst_conversion_contract() -> None:
    record = _record(
        expiration_date=date(2026, 1, 16),
        expiration_ts_utc=datetime(
            2026,
            1,
            16,
            16,
            15,
            tzinfo=NEW_YORK,
        ),
    )

    assert record.expiration_ts_utc == datetime(
        2026,
        1,
        16,
        21,
        15,
        tzinfo=UTC,
    )


def test_option_contract_028_expiration_date_remains_explicit() -> None:
    explicit_date = date(1999, 12, 31)
    record = _record(
        expiration_date=explicit_date,
        expiration_ts_utc=datetime(2026, 7, 17, 20, 15, tzinfo=UTC),
    )

    assert record.expiration_date == explicit_date


def test_option_contract_029_no_premature_0dte_eligibility() -> None:
    future_expiration = date(2030, 12, 20)
    record = _record(
        settlement_style=SettlementStyle.AM,
        expiration_date=future_expiration,
    )

    assert record.expiration_date == future_expiration
    assert record.settlement_style is SettlementStyle.AM


def test_option_contract_030_first_last_seen_remain_explicit() -> None:
    first_seen = date(2025, 12, 1)
    last_seen = date(2026, 2, 3)
    record = _record(first_seen_date=first_seen, last_seen_date=last_seen)

    assert record.first_seen_date == first_seen
    assert record.last_seen_date == last_seen


def test_option_contract_031_no_invented_first_last_ordering_rule() -> None:
    first_seen = date(2026, 8, 1)
    last_seen = date(2026, 7, 1)
    record = _record(first_seen_date=first_seen, last_seen_date=last_seen)

    assert record.first_seen_date == first_seen
    assert record.last_seen_date == last_seen


def test_option_contract_032_model_dump_persistence_names() -> None:
    assert list(_record().model_dump()) == CANONICAL_FIELDS
