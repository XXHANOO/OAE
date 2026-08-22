import inspect
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from oae.data.session_state import (
    SPXSessionStateIntegrityError,
    build_spx_session_state,
)
from oae.enums import QualityStatus
from oae.schemas.calendar import TradingSessionRecord
from oae.schemas.market import IndexBar1mRecord
from oae.schemas.session import IndexSessionRecord
from oae.temporal import decision_ts_utc, session_open_ts_utc


UTC = timezone.utc
ET = ZoneInfo("America/New_York")
SESSION_DATE = date(2026, 7, 15)
PREVIOUS_DATE = date(2026, 7, 14)
OFFICIAL_PREVIOUS_CLOSE = Decimal("6000.125000")
PRICE_FIELDS = (
    "spx_official_prev_close",
    "spx_open",
    "spx_decision_px",
    "intraday_high_to_t0",
    "intraday_low_to_t0",
)
CANONICAL_FIELDS = [
    "session_date_et",
    "spx_official_prev_close",
    "spx_open",
    "spx_decision_px",
    "intraday_high_to_t0",
    "intraday_low_to_t0",
    "is_full_session",
    "session_open_ts_utc",
    "session_close_ts_utc",
]


def _market_timestamp(
    session_date: date,
    hour: int,
    minute: int,
    second: int = 0,
    microsecond: int = 0,
) -> datetime:
    return datetime(
        session_date.year,
        session_date.month,
        session_date.day,
        hour,
        minute,
        second,
        microsecond,
        tzinfo=ET,
    )


def _session(
    session_date: date = SESSION_DATE,
    **overrides: object,
) -> TradingSessionRecord:
    values: dict[str, object] = {
        "session_date_et": session_date,
        "session_seq": 100,
        "open_ts_utc": _market_timestamp(session_date, 9, 30),
        "regular_close_ts_utc": _market_timestamp(session_date, 16, 0),
        "is_trading_day": True,
        "is_full_session": True,
        "is_half_day": False,
        "xsp_0dte_exists": True,
    }
    values.update(overrides)
    return TradingSessionRecord.model_validate(values)


def _bar(
    start: datetime,
    *,
    session_date: date = SESSION_DATE,
    open_px: Decimal = Decimal("6000.000000"),
    high: Decimal = Decimal("6002.000000"),
    low: Decimal = Decimal("5998.000000"),
    close: Decimal = Decimal("6000.500000"),
    source: str = "TEST_PROVIDER",
    raw_file_id: str = "raw-1",
    quality_status: QualityStatus = QualityStatus.VALID,
) -> IndexBar1mRecord:
    return IndexBar1mRecord(
        symbol="SPX",
        session_date_et=session_date,
        bar_start_ts_utc=start,
        bar_end_ts_utc=start + timedelta(minutes=1),
        open=open_px,
        high=high,
        low=low,
        close=close,
        observation_count=10,
        source=source,
        raw_file_id=raw_file_id,
        quality_status=quality_status,
    )


def _replace_bar(
    bar: IndexBar1mRecord,
    **overrides: object,
) -> IndexBar1mRecord:
    values = bar.model_dump()
    values.update(overrides)
    return IndexBar1mRecord.model_validate(values)


def _bars(session_date: date = SESSION_DATE) -> list[IndexBar1mRecord]:
    first_start = session_open_ts_utc(session_date)
    records: list[IndexBar1mRecord] = []
    for offset in range(240):
        open_px = Decimal("6000.000000") + Decimal(offset) / Decimal("100")
        records.append(
            _bar(
                first_start + timedelta(minutes=offset),
                session_date=session_date,
                open_px=open_px,
                high=open_px + Decimal("2.000000"),
                low=open_px - Decimal("2.000000"),
                close=open_px + Decimal("0.500000"),
            )
        )
    return records


def _record_data(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "session_date_et": SESSION_DATE,
        "spx_official_prev_close": Decimal("5999.125000"),
        "spx_open": Decimal("6000.250000"),
        "spx_decision_px": Decimal("6005.750000"),
        "intraday_high_to_t0": Decimal("6010.000000"),
        "intraday_low_to_t0": Decimal("5990.000000"),
        "is_full_session": True,
        "session_open_ts_utc": _market_timestamp(SESSION_DATE, 9, 30),
        "session_close_ts_utc": _market_timestamp(SESSION_DATE, 16, 0),
    }
    values.update(overrides)
    return values


def _record(**overrides: object) -> IndexSessionRecord:
    return IndexSessionRecord.model_validate(_record_data(**overrides))


def _state(
    bars: list[IndexBar1mRecord] | None = None,
    *,
    session: TradingSessionRecord | None = None,
    previous_close: Decimal = OFFICIAL_PREVIOUS_CLOSE,
) -> IndexSessionRecord:
    target_session = session or _session()
    target_bars = bars if bars is not None else _bars(target_session.session_date_et)
    return build_spx_session_state(
        target_session,
        target_bars,
        spx_official_prev_close=previous_close,
    )


def _future_bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "start": decision_ts_utc(SESSION_DATE),
        "session_date": SESSION_DATE,
        "open_px": Decimal("700000"),
        "high": Decimal("999999"),
        "low": Decimal("1"),
        "close": Decimal("888888"),
    }
    values.update(overrides)
    return _bar(**values)  # type: ignore[arg-type]


def _pre_open_bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "start": session_open_ts_utc(SESSION_DATE) - timedelta(minutes=1),
        "session_date": SESSION_DATE,
        "open_px": Decimal("2"),
        "high": Decimal("999999"),
        "low": Decimal("1"),
        "close": Decimal("2"),
    }
    values.update(overrides)
    return _bar(**values)  # type: ignore[arg-type]


def _other_date_bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "start": _market_timestamp(PREVIOUS_DATE, 15, 59),
        "session_date": PREVIOUS_DATE,
        "open_px": Decimal("9998"),
        "high": Decimal("999999"),
        "low": Decimal("1"),
        "close": Decimal("9999.000000"),
    }
    values.update(overrides)
    return _bar(**values)  # type: ignore[arg-type]


def test_spxs_001_exact_nine_field_contract() -> None:
    assert list(IndexSessionRecord.model_fields) == CANONICAL_FIELDS


def test_spxs_002_index_session_record_is_frozen() -> None:
    record = _record()
    with pytest.raises(ValidationError):
        record.spx_open = Decimal("1")  # type: ignore[misc]


def test_spxs_003_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        IndexSessionRecord.model_validate({**_record_data(), "source": "X"})


@pytest.mark.parametrize("value", [1, "true"])
def test_spxs_004_is_full_session_is_strict_bool(value: object) -> None:
    with pytest.raises(ValidationError):
        _record(is_full_session=value)


@pytest.mark.parametrize("field_name", PRICE_FIELDS)
def test_spxs_005_all_price_fields_require_decimal(field_name: str) -> None:
    with pytest.raises(ValidationError):
        _record(**{field_name: "6000.125000"})


@pytest.mark.parametrize("field_name", PRICE_FIELDS)
def test_spxs_006_all_price_fields_reject_zero(field_name: str) -> None:
    with pytest.raises(ValidationError):
        _record(**{field_name: Decimal("0")})


@pytest.mark.parametrize("field_name", PRICE_FIELDS)
def test_spxs_007_all_price_fields_reject_negative(field_name: str) -> None:
    with pytest.raises(ValidationError):
        _record(**{field_name: Decimal("-0.000001")})


def test_spxs_008_aware_timestamps_canonicalize_to_utc() -> None:
    record = _record()
    assert record.session_open_ts_utc == datetime(2026, 7, 15, 13, 30, tzinfo=UTC)
    assert record.session_close_ts_utc == datetime(2026, 7, 15, 20, 0, tzinfo=UTC)
    assert record.session_open_ts_utc.tzinfo is UTC
    assert record.session_close_ts_utc.tzinfo is UTC


def test_spxs_009_naive_open_timestamp_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _record(session_open_ts_utc=datetime(2026, 7, 15, 9, 30))


def test_spxs_010_naive_close_timestamp_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _record(session_close_ts_utc=datetime(2026, 7, 15, 16, 0))


def test_spxs_011_open_not_before_close_rejected() -> None:
    with pytest.raises(ValidationError, match="must precede"):
        _record(
            session_open_ts_utc=_market_timestamp(SESSION_DATE, 16, 0),
            session_close_ts_utc=_market_timestamp(SESSION_DATE, 9, 30),
        )


def test_s207r_spxs_011_equal_session_open_and_close_rejected() -> None:
    same = _market_timestamp(SESSION_DATE, 9, 30)
    with pytest.raises(ValidationError, match="must precede"):
        _record(
            session_open_ts_utc=same,
            session_close_ts_utc=same,
        )


def test_spxs_012_open_et_date_mismatch_rejected() -> None:
    with pytest.raises(ValidationError, match="open_ts_utc ET date"):
        _record(session_open_ts_utc=_market_timestamp(PREVIOUS_DATE, 9, 30))


def test_spxs_013_close_et_date_mismatch_rejected() -> None:
    next_date = date(2026, 7, 16)
    with pytest.raises(ValidationError, match="close_ts_utc ET date"):
        _record(session_close_ts_utc=_market_timestamp(next_date, 16, 0))


def test_spxs_014_low_above_high_rejected() -> None:
    with pytest.raises(ValidationError, match="must not exceed"):
        _record(
            intraday_low_to_t0=Decimal("6020"),
            intraday_high_to_t0=Decimal("6010"),
        )


def test_spxs_015_open_outside_intraday_range_rejected() -> None:
    with pytest.raises(ValidationError, match="spx_open"):
        _record(spx_open=Decimal("6020"))


def test_spxs_016_decision_price_outside_intraday_range_rejected() -> None:
    with pytest.raises(ValidationError, match="spx_decision_px"):
        _record(spx_decision_px=Decimal("6020"))


def test_spxs_017_official_previous_close_is_required_keyword_only() -> None:
    parameter = inspect.signature(build_spx_session_state).parameters[
        "spx_official_prev_close"
    ]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        build_spx_session_state(_session(), _bars())  # type: ignore[call-arg]


@pytest.mark.parametrize("value", [6000, 6000.0, "6000"])
def test_spxs_018_non_decimal_official_previous_close_rejected(value: object) -> None:
    with pytest.raises(SPXSessionStateIntegrityError, match="Decimal"):
        build_spx_session_state(
            _session(), _bars(), spx_official_prev_close=value  # type: ignore[arg-type]
        )


def test_spxs_019_zero_official_previous_close_rejected() -> None:
    with pytest.raises(SPXSessionStateIntegrityError, match="positive"):
        _state(previous_close=Decimal("0"))


def test_spxs_020_negative_official_previous_close_rejected() -> None:
    with pytest.raises(SPXSessionStateIntegrityError, match="positive"):
        _state(previous_close=Decimal("-1"))


def test_spxs_021_exact_official_previous_close_preserved() -> None:
    supplied = Decimal("6000.125000123456789")
    state = _state(previous_close=supplied)
    assert state.spx_official_prev_close is supplied
    assert state.spx_official_prev_close == supplied


def test_spxs_022_previous_date_final_bar_does_not_override_explicit_close() -> None:
    state = _state(_bars() + [_other_date_bar()])
    assert state.spx_official_prev_close == Decimal("6000.125000")
    assert state.spx_official_prev_close != Decimal("9999.000000")


def test_spxs_023_non_trading_session_raises_integrity_error() -> None:
    session = _session(
        is_trading_day=False,
        is_full_session=False,
        is_half_day=False,
    )
    with pytest.raises(SPXSessionStateIntegrityError, match="trading day"):
        _state(session=session)


def test_spxs_024_noncanonical_calendar_open_raises_integrity_error() -> None:
    session = _session(open_ts_utc=_market_timestamp(SESSION_DATE, 9, 31))
    with pytest.raises(SPXSessionStateIntegrityError, match="09:30"):
        _state(session=session)


def test_spxs_025_summer_canonical_open_accepted() -> None:
    state = _state()
    assert state.session_open_ts_utc == datetime(2026, 7, 15, 13, 30, tzinfo=UTC)


def test_spxs_026_winter_canonical_open_accepted() -> None:
    winter_date = date(2026, 1, 15)
    winter_session = _session(winter_date)
    state = _state(_bars(winter_date), session=winter_session)
    assert state.session_open_ts_utc == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)


def test_spxs_027_regular_close_before_decision_rejected() -> None:
    session = _session(
        regular_close_ts_utc=_market_timestamp(SESSION_DATE, 13, 29)
    )
    with pytest.raises(SPXSessionStateIntegrityError, match="13:30"):
        _state(session=session)


def test_spxs_028_is_full_session_copied_exactly() -> None:
    session = _session(is_full_session=False)
    assert _state(session=session).is_full_session is False


def test_spxs_029_exact_complete_240_bar_grid_passes() -> None:
    state = _state()
    assert isinstance(state, IndexSessionRecord)
    assert len(_bars()) == 240


def test_spxs_030_missing_open_bar_raises() -> None:
    with pytest.raises(SPXSessionStateIntegrityError, match="240"):
        _state(_bars()[1:])


def test_spxs_031_missing_interior_bar_raises() -> None:
    bars = _bars()
    del bars[100]
    with pytest.raises(SPXSessionStateIntegrityError, match="240"):
        _state(bars)


def test_spxs_032_missing_decision_bar_raises() -> None:
    with pytest.raises(SPXSessionStateIntegrityError, match="240"):
        _state(_bars()[:-1])


def test_spxs_033_duplicate_required_bar_end_raises() -> None:
    bars = _bars()
    bars.append(bars[100])
    with pytest.raises(SPXSessionStateIntegrityError, match="duplicate"):
        _state(bars)


def test_spxs_034_off_grid_active_window_bar_raises() -> None:
    start = session_open_ts_utc(SESSION_DATE) + timedelta(seconds=30)
    with pytest.raises(SPXSessionStateIntegrityError, match="off-grid"):
        _state(_bars() + [_bar(start)])


def test_s207r_opening_boundary_straddling_off_grid_bar_raises() -> None:
    start = session_open_ts_utc(SESSION_DATE) - timedelta(seconds=30)
    with pytest.raises(SPXSessionStateIntegrityError, match="off-grid"):
        _state(_bars() + [_bar(start)])


def test_spxs_035_reversed_complete_input_produces_same_state() -> None:
    bars = _bars()
    assert _state(list(reversed(bars))) == _state(bars)


def test_spxs_036_shuffled_complete_input_produces_same_state() -> None:
    bars = _bars()
    shuffled = list(bars)
    random.Random(20260822).shuffle(shuffled)
    assert _state(shuffled) == _state(bars)


def test_spxs_037_builder_does_not_mutate_caller_sequence() -> None:
    bars = list(reversed(_bars()))
    before = list(bars)
    _state(bars)
    assert bars == before


def test_spxs_038_required_stale_bar_raises() -> None:
    bars = _bars()
    bars[50] = _replace_bar(bars[50], quality_status=QualityStatus.STALE)
    with pytest.raises(SPXSessionStateIntegrityError, match="VALID"):
        _state(bars)


def test_spxs_039_required_representative_nonvalid_bar_raises() -> None:
    bars = _bars()
    bars[50] = _replace_bar(bars[50], quality_status=QualityStatus.HALTED)
    with pytest.raises(SPXSessionStateIntegrityError, match="VALID"):
        _state(bars)


def test_spxs_040_mixed_required_sources_raise() -> None:
    bars = _bars()
    bars[50] = _replace_bar(bars[50], source="OTHER_PROVIDER")
    with pytest.raises(SPXSessionStateIntegrityError, match="same source"):
        _state(bars)


def test_spxs_041_multiple_raw_files_from_same_source_allowed() -> None:
    bars = [
        _replace_bar(bar, raw_file_id=f"raw-{index % 3}")
        for index, bar in enumerate(_bars())
    ]
    assert isinstance(_state(bars), IndexSessionRecord)


def test_spxs_042_spx_open_is_open_of_first_required_bar() -> None:
    bars = _bars()
    assert _state(bars).spx_open == bars[0].open


def test_spxs_043_spx_open_is_not_first_bar_close_by_position() -> None:
    bars = _bars()
    assert bars[0].open != bars[0].close
    assert _state(bars).spx_open != bars[0].close


def test_spxs_044_decision_price_is_close_of_last_required_bar() -> None:
    bars = _bars()
    assert _state(bars).spx_decision_px == bars[-1].close


def test_spxs_045_decision_bar_open_differs_and_output_uses_close() -> None:
    bars = _bars()
    assert bars[-1].open != bars[-1].close
    assert _state(bars).spx_decision_px != bars[-1].open


def test_spxs_046_intraday_high_is_required_bar_maximum() -> None:
    bars = _bars()
    assert _state(bars).intraday_high_to_t0 == max(bar.high for bar in bars)


def test_spxs_047_intraday_low_is_required_bar_minimum() -> None:
    bars = _bars()
    assert _state(bars).intraday_low_to_t0 == min(bar.low for bar in bars)


def test_spxs_048_decision_bar_extreme_high_is_included() -> None:
    bars = _bars()
    bars[-1] = _replace_bar(bars[-1], high=Decimal("999999"))
    assert _state(bars).intraday_high_to_t0 == Decimal("999999")


def test_spxs_049_decision_bar_extreme_low_is_included() -> None:
    bars = _bars()
    bars[-1] = _replace_bar(bars[-1], low=Decimal("1"))
    assert _state(bars).intraday_low_to_t0 == Decimal("1")


def test_spxs_050_future_extreme_high_is_nonobservable() -> None:
    bars = _bars()
    assert _state(bars + [_future_bar()]).intraday_high_to_t0 == _state(
        bars
    ).intraday_high_to_t0


def test_spxs_051_future_extreme_low_is_nonobservable() -> None:
    bars = _bars()
    assert _state(bars + [_future_bar()]).intraday_low_to_t0 == _state(
        bars
    ).intraday_low_to_t0


def test_spxs_052_future_extreme_close_is_nonobservable() -> None:
    bars = _bars()
    assert _state(bars + [_future_bar()]).spx_decision_px == _state(
        bars
    ).spx_decision_px


def test_spxs_053_future_nonvalid_quality_does_not_raise() -> None:
    future = _future_bar(quality_status=QualityStatus.STALE)
    assert _state(_bars() + [future]) == _state()


def test_spxs_054_future_different_source_does_not_raise() -> None:
    future = _future_bar(source="FUTURE_PROVIDER")
    assert _state(_bars() + [future]) == _state()


def test_spxs_055_future_duplicates_do_not_affect_state() -> None:
    future = _future_bar()
    assert _state(_bars() + [future, future]) == _state()


def test_s207r_decision_boundary_incomplete_off_grid_bar_is_nonobservable() -> None:
    incomplete = _bar(
        decision_ts_utc(SESSION_DATE) - timedelta(seconds=30),
        open_px=Decimal("700000"),
        high=Decimal("999999"),
        low=Decimal("1"),
        close=Decimal("888888"),
        source="FUTURE_PROVIDER",
        quality_status=QualityStatus.STALE,
    )
    assert _state(_bars() + [incomplete]) == _state()


def test_spxs_056_pre_open_extremes_do_not_affect_range() -> None:
    assert _state(_bars() + [_pre_open_bar()]) == _state()


def test_spxs_057_pre_open_nonvalid_quality_does_not_raise() -> None:
    pre_open = _pre_open_bar(quality_status=QualityStatus.STALE)
    assert _state(_bars() + [pre_open]) == _state()


def test_spxs_058_pre_open_different_source_does_not_raise() -> None:
    pre_open = _pre_open_bar(source="PREOPEN_PROVIDER")
    assert _state(_bars() + [pre_open]) == _state()


def test_spxs_059_other_date_extremes_do_not_affect_range() -> None:
    assert _state(_bars() + [_other_date_bar()]) == _state()


def test_spxs_060_other_date_nonvalid_quality_does_not_raise() -> None:
    other = _other_date_bar(quality_status=QualityStatus.STALE)
    assert _state(_bars() + [other]) == _state()


def test_spxs_061_other_date_different_source_does_not_raise() -> None:
    other = _other_date_bar(source="HISTORICAL_PROVIDER")
    assert _state(_bars() + [other]) == _state()


def test_spxs_062_session_date_copied_exactly() -> None:
    session = _session()
    assert _state(session=session).session_date_et == session.session_date_et


def test_spxs_063_session_open_copied_from_calendar_record() -> None:
    session = _session()
    assert _state(session=session).session_open_ts_utc == session.open_ts_utc


def test_spxs_064_session_close_copied_from_regular_close() -> None:
    session = _session()
    assert (
        _state(session=session).session_close_ts_utc
        == session.regular_close_ts_utc
    )


def test_spxs_065_returned_model_has_no_lineage_fields() -> None:
    fields = type(_state()).model_fields
    assert "source" not in fields
    assert "raw_file_id" not in fields


def test_spxs_066_returned_model_has_no_decision_timestamp_field() -> None:
    assert "decision_ts_utc" not in type(_state()).model_fields


def test_spxs_067_returned_model_has_no_feature_validity_fields() -> None:
    fields = type(_state()).model_fields
    assert "feature_valid" not in fields
    assert "invalid_reason" not in fields


def test_spxs_068_returned_model_has_no_feature_values() -> None:
    fields = type(_state()).model_fields
    assert all(f"x{index}" not in fields for index in range(1, 9))
