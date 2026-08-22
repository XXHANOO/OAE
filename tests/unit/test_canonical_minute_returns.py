import inspect
import math
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from oae.data.minute_returns import (
    CanonicalMinuteReturnIntegrityError,
    build_canonical_minute_return_series,
)
from oae.enums import QualityStatus
from oae.schemas.market import IndexBar1mRecord
from oae.schemas.session import IndexSessionRecord
from oae.temporal import decision_ts_utc, session_open_ts_utc


ET = ZoneInfo("America/New_York")
SUMMER_DATE = date(2026, 7, 15)
WINTER_DATE = date(2026, 1, 15)
PREVIOUS_DATE = date(2026, 7, 14)
OPEN_PRICE = Decimal("6000.000000")
PREVIOUS_CLOSE = Decimal("5990.125000")


def _market_timestamp(
    session_date: date,
    hour: int,
    minute: int,
    second: int = 0,
) -> datetime:
    return datetime(
        session_date.year,
        session_date.month,
        session_date.day,
        hour,
        minute,
        second,
        tzinfo=ET,
    )


def _bar(
    start: datetime,
    *,
    session_date: date = SUMMER_DATE,
    open_px: Decimal = OPEN_PRICE,
    close: Decimal = Decimal("6000.250000"),
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
        high=max(open_px, close) + Decimal("1"),
        low=min(open_px, close) - Decimal("1"),
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


def _bars(
    session_date: date = SUMMER_DATE,
    *,
    open_px: Decimal = OPEN_PRICE,
    closes: list[Decimal] | None = None,
) -> list[IndexBar1mRecord]:
    path = closes or [
        open_px + Decimal(index + 1) / Decimal("4")
        for index in range(240)
    ]
    assert len(path) == 240
    canonical_open = session_open_ts_utc(session_date)
    records: list[IndexBar1mRecord] = []
    for index, close in enumerate(path):
        previous = open_px if index == 0 else path[index - 1]
        records.append(
            _bar(
                canonical_open + timedelta(minutes=index),
                session_date=session_date,
                open_px=previous,
                close=close,
            )
        )
    return records


def _state(
    bars: list[IndexBar1mRecord],
    *,
    session_date: date = SUMMER_DATE,
    previous_close: Decimal = PREVIOUS_CLOSE,
    is_full_session: bool = True,
    session_open: datetime | None = None,
    session_close: datetime | None = None,
) -> IndexSessionRecord:
    return IndexSessionRecord(
        session_date_et=session_date,
        spx_official_prev_close=previous_close,
        spx_open=bars[0].open,
        spx_decision_px=bars[-1].close,
        intraday_high_to_t0=max(bar.high for bar in bars),
        intraday_low_to_t0=min(bar.low for bar in bars),
        is_full_session=is_full_session,
        session_open_ts_utc=session_open or session_open_ts_utc(session_date),
        session_close_ts_utc=session_close
        or _market_timestamp(session_date, 16, 0),
    )


def _build(
    bars: list[IndexBar1mRecord] | None = None,
    *,
    state: IndexSessionRecord | None = None,
    session_date: date = SUMMER_DATE,
) -> tuple[float, ...]:
    canonical_bars = bars or _bars(session_date)
    session_state = state or _state(
        canonical_bars,
        session_date=session_date,
    )
    return build_canonical_minute_return_series(session_state, canonical_bars)


def _future_bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "start": decision_ts_utc(SUMMER_DATE),
        "session_date": SUMMER_DATE,
        "open_px": Decimal("900000"),
        "close": Decimal("999999"),
    }
    values.update(overrides)
    return _bar(**values)  # type: ignore[arg-type]


def _pre_open_bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "start": session_open_ts_utc(SUMMER_DATE) - timedelta(minutes=1),
        "session_date": SUMMER_DATE,
        "open_px": Decimal("2"),
        "close": Decimal("1"),
    }
    values.update(overrides)
    return _bar(**values)  # type: ignore[arg-type]


def _other_date_bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "start": _market_timestamp(PREVIOUS_DATE, 15, 59),
        "session_date": PREVIOUS_DATE,
        "open_px": Decimal("9998"),
        "close": Decimal("9999"),
    }
    values.update(overrides)
    return _bar(**values)  # type: ignore[arg-type]


def test_cmr_001_dedicated_integrity_exception() -> None:
    assert issubclass(CanonicalMinuteReturnIntegrityError, RuntimeError)
    assert CanonicalMinuteReturnIntegrityError is not RuntimeError


def test_cmr_002_builder_accepts_exactly_session_state_and_bars() -> None:
    parameters = inspect.signature(
        build_canonical_minute_return_series
    ).parameters
    assert list(parameters) == ["session_state", "bars"]
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in parameters.values()
    )


def test_cmr_003_valid_complete_input_returns_tuple() -> None:
    assert isinstance(_build(), tuple)


def test_cmr_004_tuple_length_is_exactly_240() -> None:
    assert len(_build()) == 240


def test_cmr_005_all_returned_elements_are_float() -> None:
    assert all(isinstance(value, float) for value in _build())


def test_cmr_006_all_returned_values_are_finite() -> None:
    assert all(math.isfinite(value) for value in _build())


def test_cmr_007_reversed_input_produces_identical_tuple() -> None:
    bars = _bars()
    assert _build(list(reversed(bars)), state=_state(bars)) == _build(bars)


def test_cmr_008_shuffled_input_produces_identical_tuple() -> None:
    bars = _bars()
    shuffled = list(bars)
    random.Random(20260822).shuffle(shuffled)
    assert _build(shuffled, state=_state(bars)) == _build(bars)


def test_cmr_009_caller_sequence_is_not_mutated() -> None:
    bars = list(reversed(_bars()))
    before = list(bars)
    _build(bars, state=_state(list(reversed(bars))))
    assert bars == before


def test_cmr_010_noncanonical_session_open_is_rejected() -> None:
    bars = _bars()
    state = _state(
        bars,
        session_open=_market_timestamp(SUMMER_DATE, 9, 31),
    )
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="09:30"):
        _build(bars, state=state)


def test_cmr_011_summer_dst_canonical_grid_is_accepted() -> None:
    bars = _bars(SUMMER_DATE)
    assert len(_build(bars, session_date=SUMMER_DATE)) == 240
    assert bars[0].bar_start_ts_utc.hour == 13


def test_cmr_012_winter_dst_canonical_grid_is_accepted() -> None:
    bars = _bars(WINTER_DATE)
    assert len(_build(bars, session_date=WINTER_DATE)) == 240
    assert bars[0].bar_start_ts_utc.hour == 14


def test_cmr_013_session_close_before_decision_is_rejected() -> None:
    bars = _bars()
    state = _state(
        bars,
        session_close=_market_timestamp(SUMMER_DATE, 13, 29),
    )
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="13:30"):
        _build(bars, state=state)


def test_cmr_014_non_full_session_alone_does_not_reject() -> None:
    bars = _bars()
    state = _state(bars, is_full_session=False)
    assert len(_build(bars, state=state)) == 240


def test_cmr_015_exact_240_bar_grid_passes() -> None:
    bars = _bars()
    assert len(bars) == len(_build(bars)) == 240


def test_cmr_016_missing_open_bar_hard_fails() -> None:
    bars = _bars()
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="240"):
        _build(bars[1:], state=_state(bars))


def test_cmr_017_missing_interior_bar_hard_fails() -> None:
    bars = _bars()
    del bars[111]
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="240"):
        _build(bars, state=_state(_bars()))


def test_cmr_018_missing_decision_bar_hard_fails() -> None:
    bars = _bars()
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="240"):
        _build(bars[:-1], state=_state(bars))


def test_cmr_019_duplicate_required_bar_hard_fails() -> None:
    bars = _bars()
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="duplicate"):
        _build(bars + [bars[100]], state=_state(bars))


def test_cmr_020_fully_available_off_grid_bar_hard_fails() -> None:
    bars = _bars()
    off_grid = _bar(session_open_ts_utc(SUMMER_DATE) + timedelta(seconds=30))
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="off-grid"):
        _build(bars + [off_grid], state=_state(bars))


def test_cmr_021_opening_boundary_straddle_hard_fails() -> None:
    bars = _bars()
    straddle = _bar(session_open_ts_utc(SUMMER_DATE) - timedelta(seconds=30))
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="off-grid"):
        _build(bars + [straddle], state=_state(bars))


def test_cmr_022_pure_pre_open_bar_is_ignored() -> None:
    bars = _bars()
    assert _build(bars + [_pre_open_bar()], state=_state(bars)) == _build(bars)


def test_cmr_023_extreme_price_future_bar_is_irrelevant() -> None:
    bars = _bars()
    future = _future_bar(close=Decimal("999999999999999999999999"))
    assert _build(bars + [future], state=_state(bars)) == _build(bars)


def test_cmr_024_stale_future_bar_is_irrelevant() -> None:
    bars = _bars()
    future = _future_bar(quality_status=QualityStatus.STALE)
    assert _build(bars + [future], state=_state(bars)) == _build(bars)


def test_cmr_025_different_source_future_bar_is_irrelevant() -> None:
    bars = _bars()
    future = _future_bar(source="HOSTILE_FUTURE_PROVIDER")
    assert _build(bars + [future], state=_state(bars)) == _build(bars)


def test_cmr_026_future_duplicate_bars_are_irrelevant() -> None:
    bars = _bars()
    future = _future_bar()
    assert _build(bars + [future, future], state=_state(bars)) == _build(bars)


def test_cmr_027_incomplete_decision_boundary_bar_is_irrelevant() -> None:
    bars = _bars()
    incomplete = _bar(
        decision_ts_utc(SUMMER_DATE) - timedelta(seconds=30),
        open_px=Decimal("900000"),
        close=Decimal("999999"),
        source="HOSTILE_FUTURE_PROVIDER",
        quality_status=QualityStatus.STALE,
    )
    assert _build(bars + [incomplete], state=_state(bars)) == _build(bars)


def test_cmr_028_invalid_quality_pre_open_bar_is_irrelevant() -> None:
    bars = _bars()
    pre_open = _pre_open_bar(quality_status=QualityStatus.STALE)
    assert _build(bars + [pre_open], state=_state(bars)) == _build(bars)


def test_cmr_029_different_source_pre_open_bar_is_irrelevant() -> None:
    bars = _bars()
    pre_open = _pre_open_bar(source="HOSTILE_PREOPEN_PROVIDER")
    assert _build(bars + [pre_open], state=_state(bars)) == _build(bars)


def test_cmr_030_invalid_quality_other_date_bar_is_irrelevant() -> None:
    bars = _bars()
    other = _other_date_bar(quality_status=QualityStatus.STALE)
    assert _build(bars + [other], state=_state(bars)) == _build(bars)


def test_cmr_031_different_source_other_date_bar_is_irrelevant() -> None:
    bars = _bars()
    other = _other_date_bar(source="HOSTILE_HISTORICAL_PROVIDER")
    assert _build(bars + [other], state=_state(bars)) == _build(bars)


def test_cmr_032_nonpositive_other_date_close_is_irrelevant() -> None:
    bars = _bars()
    for close in (Decimal("0"), Decimal("-1")):
        other = _other_date_bar(close=close)
        assert _build(bars + [other], state=_state(bars)) == _build(bars)


def test_cmr_033_required_stale_bar_hard_fails() -> None:
    bars = _bars()
    bars[50] = _replace_bar(bars[50], quality_status=QualityStatus.STALE)
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="VALID"):
        _build(bars, state=_state(_bars()))


def test_cmr_034_required_nonvalid_bar_hard_fails() -> None:
    bars = _bars()
    bars[50] = _replace_bar(bars[50], quality_status=QualityStatus.HALTED)
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="VALID"):
        _build(bars, state=_state(_bars()))


def test_cmr_035_mixed_required_sources_hard_fail() -> None:
    bars = _bars()
    bars[50] = _replace_bar(bars[50], source="OTHER_PROVIDER")
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="same source"):
        _build(bars, state=_state(_bars()))


def test_cmr_036_multiple_raw_files_from_same_source_are_allowed() -> None:
    bars = [
        _replace_bar(bar, raw_file_id=f"raw-{index % 7}")
        for index, bar in enumerate(_bars())
    ]
    assert len(_build(bars)) == 240


def test_cmr_037_first_bar_open_state_mismatch_hard_fails() -> None:
    bars = _bars()
    state = _state(bars)
    bars[0] = _replace_bar(
        bars[0],
        open=bars[0].open + Decimal("1"),
    )
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="SPX open"):
        _build(bars, state=state)


def test_cmr_038_decision_close_state_mismatch_hard_fails() -> None:
    bars = _bars()
    state = _state(bars)
    bars[-1] = _replace_bar(
        bars[-1],
        close=bars[-1].close + Decimal("1"),
    )
    with pytest.raises(
        CanonicalMinuteReturnIntegrityError,
        match="decision price",
    ):
        _build(bars, state=state)


def test_cmr_039_zero_required_close_hard_fails() -> None:
    bars = _bars()
    bars[50] = _replace_bar(bars[50], close=Decimal("0"))
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="positive"):
        _build(bars, state=_state(_bars()))


def test_cmr_040_negative_required_close_hard_fails() -> None:
    bars = _bars()
    bars[50] = _replace_bar(bars[50], close=Decimal("-1"))
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="positive"):
        _build(bars, state=_state(_bars()))


def test_cmr_041_nonpositive_future_close_does_not_fail() -> None:
    bars = _bars()
    for close in (Decimal("0"), Decimal("-1")):
        future = _future_bar(close=close)
        assert _build(bars + [future], state=_state(bars)) == _build(bars)


def test_cmr_042_nonpositive_pre_open_close_does_not_fail() -> None:
    bars = _bars()
    for close in (Decimal("0"), Decimal("-1")):
        pre_open = _pre_open_bar(close=close)
        assert _build(bars + [pre_open], state=_state(bars)) == _build(bars)


def test_cmr_043_first_return_is_first_close_over_session_open() -> None:
    bars = _bars()
    assert bars[0].open != bars[0].close
    assert _build(bars)[0] == pytest.approx(
        math.log(float(bars[0].close) / float(bars[0].open)),
        abs=1e-15,
    )


def test_cmr_044_first_return_is_not_zero_by_convention() -> None:
    bars = _bars()
    assert _build(bars)[0] != 0.0


def test_cmr_045_official_previous_close_is_irrelevant() -> None:
    bars = _bars()
    first_state = _state(bars, previous_close=Decimal("1000"))
    second_state = _state(bars, previous_close=Decimal("9000"))
    assert _build(bars, state=first_state) == _build(bars, state=second_state)


def test_cmr_046_previous_date_final_bar_cannot_change_first_return() -> None:
    bars = _bars()
    other = _other_date_bar(close=Decimal("999999999"))
    assert _build(bars + [other], state=_state(bars))[0] == _build(bars)[0]


def test_cmr_047_second_return_uses_consecutive_closes() -> None:
    bars = _bars()
    assert _build(bars)[1] == pytest.approx(
        math.log(float(bars[1].close) / float(bars[0].close)),
        abs=1e-15,
    )


def test_cmr_048_interior_return_uses_consecutive_closes() -> None:
    bars = _bars()
    index = 123
    assert _build(bars)[index] == pytest.approx(
        math.log(float(bars[index].close) / float(bars[index - 1].close)),
        abs=1e-15,
    )


def test_cmr_049_final_return_ends_at_1330() -> None:
    bars = _bars()
    assert bars[-1].bar_end_ts_utc == decision_ts_utc(SUMMER_DATE)
    assert _build(bars)[-1] == pytest.approx(
        math.log(float(bars[-1].close) / float(bars[-2].close)),
        abs=1e-15,
    )


def test_cmr_050_future_close_cannot_alter_final_return() -> None:
    bars = _bars()
    future = _future_bar(close=Decimal("1"))
    assert _build(bars + [future], state=_state(bars))[-1] == _build(bars)[-1]


def test_cmr_051_flat_prices_produce_240_zero_returns() -> None:
    bars = _bars(closes=[OPEN_PRICE] * 240)
    assert _build(bars) == (0.0,) * 240


def test_cmr_052_series_telescope_matches_open_to_decision_log_return() -> None:
    bars = _bars()
    returns = _build(bars)
    expected = math.log(float(bars[-1].close) / float(bars[0].open))
    assert sum(returns) == pytest.approx(expected, abs=1e-14)


def test_cmr_053_final_30_map_from_1300_through_1330() -> None:
    jump_price = Decimal("6060")
    closes = [OPEN_PRICE] * 210 + [jump_price] * 30
    bars = _bars(closes=closes)
    returns = _build(bars)

    assert bars[209].bar_end_ts_utc == _market_timestamp(SUMMER_DATE, 13, 0)
    assert bars[210].bar_end_ts_utc == _market_timestamp(SUMMER_DATE, 13, 1)
    assert bars[-1].bar_end_ts_utc == _market_timestamp(SUMMER_DATE, 13, 30)
    assert returns[-30] == pytest.approx(
        math.log(float(jump_price) / float(OPEN_PRICE)),
        abs=1e-15,
    )
    assert returns[-29:] == (0.0,) * 29
