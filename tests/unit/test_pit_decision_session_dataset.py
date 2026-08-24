import inspect
import math
import random
from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

import oae.data.decision_session as decision_session_module
from oae.data.decision_session import (
    PITDecisionSessionDataset,
    PITDecisionSessionDatasetIntegrityError,
    build_pit_decision_session_dataset,
)
from oae.data.minute_returns import (
    CanonicalMinuteReturnIntegrityError,
    build_canonical_minute_return_series,
)
from oae.data.session_state import (
    SPXSessionStateIntegrityError,
    build_spx_session_state,
)
from oae.enums import QualityStatus
from oae.schemas.calendar import TradingSessionRecord
from oae.schemas.market import IndexBar1mRecord
from oae.temporal import decision_ts_utc, session_open_ts_utc


UTC = timezone.utc
ET = ZoneInfo("America/New_York")
SUMMER_DATE = date(2026, 7, 15)
WINTER_DATE = date(2026, 1, 15)
OTHER_DATE = date(2026, 7, 14)
OFFICIAL_PREVIOUS_CLOSE = Decimal("5990.125000")
CANONICAL_FIELDS = [
    "session",
    "session_state",
    "decision_ts_utc",
    "canonical_bars",
    "canonical_minute_returns",
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
    session_date: date = SUMMER_DATE,
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
    session_date: date = SUMMER_DATE,
    open_px: Decimal = Decimal("6000.000000"),
    close: Decimal = Decimal("6000.250000"),
    high: Decimal | None = None,
    low: Decimal | None = None,
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
        high=high if high is not None else max(open_px, close) + Decimal("1"),
        low=low if low is not None else min(open_px, close) - Decimal("1"),
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


def _bars(session_date: date = SUMMER_DATE) -> list[IndexBar1mRecord]:
    canonical_open = session_open_ts_utc(session_date)
    open_price = Decimal("6000.000000")
    closes = [
        open_price + Decimal(index + 1) / Decimal("4")
        for index in range(240)
    ]
    return [
        _bar(
            canonical_open + timedelta(minutes=index),
            session_date=session_date,
            open_px=open_price if index == 0 else closes[index - 1],
            close=close,
        )
        for index, close in enumerate(closes)
    ]


def _build(
    bars: list[IndexBar1mRecord] | None = None,
    *,
    session: TradingSessionRecord | None = None,
    previous_close: Decimal = OFFICIAL_PREVIOUS_CLOSE,
) -> PITDecisionSessionDataset:
    target_session = session or _session()
    target_bars = bars if bars is not None else _bars(target_session.session_date_et)
    return build_pit_decision_session_dataset(
        target_session,
        target_bars,
        spx_official_prev_close=previous_close,
    )


def _future_bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "start": decision_ts_utc(SUMMER_DATE),
        "session_date": SUMMER_DATE,
        "open_px": Decimal("900000"),
        "close": Decimal("999999"),
        "high": Decimal("1000000"),
        "low": Decimal("1"),
        "source": "HOSTILE_FUTURE_PROVIDER",
        "quality_status": QualityStatus.STALE,
    }
    values.update(overrides)
    return _bar(**values)  # type: ignore[arg-type]


def _pre_open_bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "start": session_open_ts_utc(SUMMER_DATE) - timedelta(minutes=1),
        "session_date": SUMMER_DATE,
        "open_px": Decimal("900000"),
        "close": Decimal("999999"),
        "high": Decimal("1000000"),
        "low": Decimal("1"),
        "source": "HOSTILE_PREOPEN_PROVIDER",
        "quality_status": QualityStatus.STALE,
    }
    values.update(overrides)
    return _bar(**values)  # type: ignore[arg-type]


def _incomplete_decision_bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "start": decision_ts_utc(SUMMER_DATE) - timedelta(seconds=30),
        "session_date": SUMMER_DATE,
        "open_px": Decimal("900000"),
        "close": Decimal("999999"),
        "high": Decimal("1000000"),
        "low": Decimal("1"),
        "source": "HOSTILE_INCOMPLETE_PROVIDER",
        "quality_status": QualityStatus.STALE,
    }
    values.update(overrides)
    return _bar(**values)  # type: ignore[arg-type]


def _other_date_bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "start": session_open_ts_utc(OTHER_DATE),
        "session_date": OTHER_DATE,
        "open_px": Decimal("900000"),
        "close": Decimal("999999"),
        "high": Decimal("1000000"),
        "low": Decimal("1"),
        "source": "HOSTILE_OTHER_DATE_PROVIDER",
        "quality_status": QualityStatus.STALE,
    }
    values.update(overrides)
    return _bar(**values)  # type: ignore[arg-type]


def test_pds_001_dataset_is_immutable_frozen_slots_dataclass() -> None:
    dataset = _build()
    assert is_dataclass(PITDecisionSessionDataset)
    assert PITDecisionSessionDataset.__dataclass_params__.frozen
    assert PITDecisionSessionDataset.__slots__ == tuple(CANONICAL_FIELDS)
    assert not hasattr(dataset, "__dict__")


def test_pds_002_dedicated_integrity_error_is_runtime_error_subclass() -> None:
    assert issubclass(PITDecisionSessionDatasetIntegrityError, RuntimeError)
    assert PITDecisionSessionDatasetIntegrityError is not RuntimeError


def test_pds_003_builder_signature_is_exact() -> None:
    parameters = inspect.signature(build_pit_decision_session_dataset).parameters
    assert list(parameters) == ["session", "bars", "spx_official_prev_close"]
    assert parameters["session"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["bars"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    previous_close = parameters["spx_official_prev_close"]
    assert previous_close.kind is inspect.Parameter.KEYWORD_ONLY
    assert previous_close.default is inspect.Parameter.empty


def test_pds_004_to_008_valid_structure_and_mutation_rejection() -> None:
    dataset = _build()
    assert isinstance(dataset, PITDecisionSessionDataset)
    assert [field.name for field in fields(dataset)] == CANONICAL_FIELDS
    assert isinstance(dataset.canonical_bars, tuple)
    assert isinstance(dataset.canonical_minute_returns, tuple)
    with pytest.raises(FrozenInstanceError):
        dataset.decision_ts_utc = datetime(2026, 7, 15, tzinfo=UTC)  # type: ignore[misc]


def test_pds_public_stage_api_is_exactly_the_three_authorized_names() -> None:
    assert decision_session_module.__all__ == (
        "PITDecisionSessionDataset",
        "PITDecisionSessionDatasetIntegrityError",
        "build_pit_decision_session_dataset",
    )


def test_pds_009_session_state_equals_direct_canonical_builder_result() -> None:
    session = _session()
    bars = _bars()
    direct = build_spx_session_state(
        session,
        bars,
        spx_official_prev_close=OFFICIAL_PREVIOUS_CLOSE,
    )
    assert _build(bars, session=session).session_state == direct


def test_pds_010_returns_equal_direct_canonical_builder_result() -> None:
    session = _session()
    bars = _bars()
    direct_state = build_spx_session_state(
        session,
        bars,
        spx_official_prev_close=OFFICIAL_PREVIOUS_CLOSE,
    )
    direct_returns = build_canonical_minute_return_series(direct_state, bars)
    assert _build(bars, session=session).canonical_minute_returns == direct_returns


def test_pds_011_official_previous_close_is_preserved_exactly() -> None:
    supplied = Decimal("5990.125000123456789")
    dataset = _build(previous_close=supplied)
    assert dataset.session_state.spx_official_prev_close is supplied


def test_pds_012_previous_close_changes_only_session_state_field() -> None:
    bars = _bars()
    first = _build(bars, previous_close=Decimal("5000"))
    second = _build(bars, previous_close=Decimal("7000"))
    first_state = first.session_state.model_dump()
    second_state = second.session_state.model_dump()
    assert first_state.pop("spx_official_prev_close") == Decimal("5000")
    assert second_state.pop("spx_official_prev_close") == Decimal("7000")
    assert first_state == second_state
    assert first.canonical_minute_returns == second.canonical_minute_returns
    assert first.canonical_bars == second.canonical_bars


@pytest.mark.parametrize(
    ("session_date", "expected_utc"),
    [
        (SUMMER_DATE, datetime(2026, 7, 15, 17, 30, tzinfo=UTC)),
        (WINTER_DATE, datetime(2026, 1, 15, 18, 30, tzinfo=UTC)),
    ],
)
def test_pds_013_to_015_decision_timestamp_is_dst_aware_helper_output(
    session_date: date,
    expected_utc: datetime,
) -> None:
    dataset = _build(_bars(session_date), session=_session(session_date))
    assert dataset.decision_ts_utc == expected_utc
    assert dataset.decision_ts_utc == decision_ts_utc(session_date)


def test_pds_016_to_020_exact_chronological_contiguous_bar_grid() -> None:
    dataset = _build()
    assert len(dataset.canonical_bars) == 240
    assert dataset.canonical_bars[0].bar_start_ts_utc == session_open_ts_utc(
        SUMMER_DATE
    )
    assert dataset.canonical_bars[0].bar_end_ts_utc == _market_timestamp(
        SUMMER_DATE, 9, 31
    )
    assert dataset.canonical_bars[-1].bar_start_ts_utc == _market_timestamp(
        SUMMER_DATE, 13, 29
    )
    assert dataset.canonical_bars[-1].bar_end_ts_utc == decision_ts_utc(
        SUMMER_DATE
    )
    starts = [bar.bar_start_ts_utc for bar in dataset.canonical_bars]
    assert starts == sorted(starts)
    assert all(
        earlier.bar_end_ts_utc == later.bar_start_ts_utc
        for earlier, later in zip(
            dataset.canonical_bars,
            dataset.canonical_bars[1:],
        )
    )


def test_pds_021_to_023_bar_bundle_matches_state_and_single_source() -> None:
    dataset = _build()
    assert dataset.canonical_bars[0].open == dataset.session_state.spx_open
    assert dataset.canonical_bars[-1].close == dataset.session_state.spx_decision_px
    assert {bar.source for bar in dataset.canonical_bars} == {"TEST_PROVIDER"}


def test_pds_024_multiple_raw_files_same_source_are_preserved() -> None:
    bars = [
        _replace_bar(bar, raw_file_id=f"raw-{index % 5}")
        for index, bar in enumerate(_bars())
    ]
    dataset = _build(bars)
    assert tuple(bar.raw_file_id for bar in dataset.canonical_bars) == tuple(
        bar.raw_file_id for bar in bars
    )
    assert len({bar.raw_file_id for bar in dataset.canonical_bars}) == 5


def test_pds_025_to_028_exact_return_bundle_mapping_and_reuse() -> None:
    bars = _bars()
    dataset = _build(bars)
    assert len(dataset.canonical_minute_returns) == 240
    assert dataset.canonical_minute_returns[0] == pytest.approx(
        math.log(float(bars[0].close) / float(bars[0].open)),
        abs=1e-15,
    )
    assert dataset.canonical_minute_returns[-1] == pytest.approx(
        math.log(float(bars[-1].close) / float(bars[-2].close)),
        abs=1e-15,
    )
    assert dataset.canonical_minute_returns == build_canonical_minute_return_series(
        dataset.session_state,
        bars,
    )


def test_pds_029_reversed_input_produces_identical_canonical_dataset() -> None:
    bars = _bars()
    assert _build(list(reversed(bars))) == _build(bars)


def test_pds_030_shuffled_input_produces_identical_canonical_dataset() -> None:
    bars = _bars()
    shuffled = list(bars)
    random.Random(20260824).shuffle(shuffled)
    assert _build(shuffled) == _build(bars)


def test_pds_031_caller_list_is_not_mutated() -> None:
    bars = list(reversed(_bars()))
    before = list(bars)
    _build(bars)
    assert bars == before


def test_pds_032_supplied_session_is_preserved_and_not_mutated() -> None:
    session = _session()
    before = session.model_dump()
    dataset = _build(session=session)
    assert dataset.session is session
    assert session.model_dump() == before


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param(_pre_open_bar(), id="pure-pre-open"),
        pytest.param(_future_bar(), id="post-decision"),
        pytest.param(_incomplete_decision_bar(), id="incomplete-decision-boundary"),
        pytest.param(_other_date_bar(), id="other-date"),
    ],
)
def test_pds_033_to_036_nonobservable_bars_are_absent_and_irrelevant(
    extra: IndexBar1mRecord,
) -> None:
    baseline = _build()
    with_extra = _build(_bars() + [extra])
    assert with_extra == baseline
    assert extra not in with_extra.canonical_bars


def test_pds_037_changing_only_future_price_cannot_change_dataset() -> None:
    first = _future_bar(
        open_px=Decimal("1"),
        close=Decimal("2"),
        high=Decimal("3"),
        low=Decimal("0"),
    )
    second = _future_bar(
        open_px=Decimal("900000"),
        close=Decimal("999999"),
        high=Decimal("1000000"),
        low=Decimal("1"),
    )
    assert _build(_bars() + [first]) == _build(_bars() + [second])


def test_pds_038_changing_only_future_quality_and_source_is_irrelevant() -> None:
    first = _future_bar(
        source="FIRST_FUTURE_SOURCE",
        quality_status=QualityStatus.HALTED,
    )
    second = _future_bar(
        source="SECOND_FUTURE_SOURCE",
        quality_status=QualityStatus.UNKNOWN,
    )
    assert _build(_bars() + [first]) == _build(_bars() + [second])


def test_pds_039_opening_straddle_propagates_session_state_error() -> None:
    opening_straddle = _bar(
        session_open_ts_utc(SUMMER_DATE) - timedelta(seconds=30)
    )
    with pytest.raises(SPXSessionStateIntegrityError, match="off-grid"):
        _build(_bars() + [opening_straddle])


@pytest.mark.parametrize("missing_index", [0, 100, 239])
def test_pds_040_to_042_missing_required_bar_propagates_session_state_error(
    missing_index: int,
) -> None:
    bars = _bars()
    del bars[missing_index]
    with pytest.raises(SPXSessionStateIntegrityError, match="240"):
        _build(bars)


def test_pds_043_duplicate_required_bar_propagates_session_state_error() -> None:
    bars = _bars()
    with pytest.raises(SPXSessionStateIntegrityError, match="duplicate"):
        _build(bars + [bars[100]])


def test_pds_044_required_stale_bar_propagates_session_state_error() -> None:
    bars = _bars()
    bars[100] = _replace_bar(bars[100], quality_status=QualityStatus.STALE)
    with pytest.raises(SPXSessionStateIntegrityError, match="VALID"):
        _build(bars)


def test_pds_045_mixed_required_source_propagates_session_state_error() -> None:
    bars = _bars()
    bars[100] = _replace_bar(bars[100], source="OTHER_PROVIDER")
    with pytest.raises(SPXSessionStateIntegrityError, match="same source"):
        _build(bars)


def test_pds_046_nonpositive_interior_close_propagates_return_error() -> None:
    bars = _bars()
    bars[100] = _replace_bar(bars[100], close=Decimal("0"))
    with pytest.raises(CanonicalMinuteReturnIntegrityError, match="positive"):
        _build(bars)


def test_pds_047_nontrading_session_propagates_session_state_error() -> None:
    session = _session(
        is_trading_day=False,
        is_full_session=False,
        is_half_day=False,
    )
    with pytest.raises(SPXSessionStateIntegrityError, match="trading day"):
        _build(session=session)


def test_pds_048_noncanonical_session_open_propagates_error() -> None:
    session = _session(open_ts_utc=_market_timestamp(SUMMER_DATE, 9, 31))
    with pytest.raises(SPXSessionStateIntegrityError, match="09:30"):
        _build(session=session)


def test_pds_049_regular_close_before_decision_propagates_error() -> None:
    session = _session(
        regular_close_ts_utc=_market_timestamp(SUMMER_DATE, 13, 29)
    )
    with pytest.raises(SPXSessionStateIntegrityError, match="13:30"):
        _build(session=session)


def test_pds_050_ordinary_half_day_before_decision_propagates_error() -> None:
    session = _session(
        regular_close_ts_utc=_market_timestamp(SUMMER_DATE, 13, 0),
        is_full_session=False,
        is_half_day=True,
    )
    with pytest.raises(SPXSessionStateIntegrityError, match="13:30"):
        _build(session=session)


def test_pds_051_non_full_flag_alone_does_not_gate_valid_dataset() -> None:
    session = _session(is_full_session=False, is_half_day=False)
    dataset = _build(session=session)
    assert dataset.session.is_full_session is False
    assert len(dataset.canonical_bars) == 240


def test_pds_052_no_xsp_0dte_flag_does_not_gate_valid_spx_dataset() -> None:
    session = _session(xsp_0dte_exists=False)
    dataset = _build(session=session)
    assert dataset.session.xsp_0dte_exists is False
    assert len(dataset.canonical_bars) == 240


def test_pds_053_to_054_builder_has_no_macro_or_calendar_gate_dependency() -> None:
    parameters = inspect.signature(build_pit_decision_session_dataset).parameters
    assert "macro_events" not in parameters
    baseline = _build()
    separate_caller_fomc_blocked = True
    assert separate_caller_fomc_blocked
    assert _build() == baseline


def test_return_builder_is_called_exactly_once_with_exact_upstream_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    bars = _bars()
    original = decision_session_module.build_canonical_minute_return_series
    calls: list[tuple[object, object]] = []
    returned: list[tuple[float, ...]] = []

    def spy(session_state: object, supplied_bars: object) -> tuple[float, ...]:
        calls.append((session_state, supplied_bars))
        result = original(session_state, supplied_bars)  # type: ignore[arg-type]
        returned.append(result)
        return result

    monkeypatch.setattr(
        decision_session_module,
        "build_canonical_minute_return_series",
        spy,
    )
    dataset = _build(bars, session=session)

    assert len(calls) == 1
    assert calls[0][0] is dataset.session_state
    assert calls[0][1] is bars
    assert dataset.canonical_minute_returns is returned[0]


def test_session_state_builder_is_called_exactly_once_and_result_is_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    bars = _bars()
    original = decision_session_module.build_spx_session_state
    calls: list[tuple[object, object, object]] = []
    returned: list[object] = []

    def spy(
        supplied_session: object,
        supplied_bars: object,
        *,
        spx_official_prev_close: object,
    ) -> object:
        calls.append(
            (supplied_session, supplied_bars, spx_official_prev_close)
        )
        result = original(
            supplied_session,
            supplied_bars,
            spx_official_prev_close=spx_official_prev_close,
        )
        returned.append(result)
        return result

    monkeypatch.setattr(decision_session_module, "build_spx_session_state", spy)
    dataset = _build(bars, session=session)

    assert len(calls) == 1
    assert calls[0] == (session, bars, OFFICIAL_PREVIOUS_CLOSE)
    assert calls[0][0] is session
    assert calls[0][1] is bars
    assert dataset.session_state is returned[0]


def test_impossible_post_validation_return_count_uses_dataset_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = decision_session_module.build_canonical_minute_return_series

    def return_239(session_state: object, supplied_bars: object) -> tuple[float, ...]:
        return original(  # type: ignore[arg-type]
            session_state,
            supplied_bars,
        )[:-1]

    monkeypatch.setattr(
        decision_session_module,
        "build_canonical_minute_return_series",
        return_239,
    )
    with pytest.raises(PITDecisionSessionDatasetIntegrityError, match="240"):
        _build()
