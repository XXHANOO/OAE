from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import date, datetime, timedelta, timezone
from typing import get_args
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from oae.data.calendar import (
    CalendarIntegrityError,
    SessionCalendarGate,
    build_session_calendar_gate,
    validate_trading_session_sequence,
)
from oae.schemas.calendar import MacroEventRecord, TradingSessionRecord


UTC = timezone.utc
ET = ZoneInfo("America/New_York")
SESSION_DATE = date(2026, 7, 15)


def _session(**overrides: object) -> TradingSessionRecord:
    session_date = overrides.get("session_date_et", SESSION_DATE)
    assert isinstance(session_date, date)
    values: dict[str, object] = {
        "session_date_et": session_date,
        "session_seq": 100,
        "open_ts_utc": datetime.combine(session_date, datetime.min.time(), tzinfo=ET).replace(hour=9, minute=30).astimezone(UTC),
        "regular_close_ts_utc": datetime.combine(session_date, datetime.min.time(), tzinfo=ET).replace(hour=16).astimezone(UTC),
        "is_trading_day": True,
        "is_full_session": True,
        "is_half_day": False,
        "xsp_0dte_exists": True,
    }
    values.update(overrides)
    return TradingSessionRecord.model_validate(values)


def _event(**overrides: object) -> MacroEventRecord:
    event_date = overrides.get("event_date_et", SESSION_DATE)
    assert isinstance(event_date, date)
    values: dict[str, object] = {
        "event_id": "event-1",
        "event_date_et": event_date,
        "event_start_ts_utc": datetime.combine(event_date, datetime.min.time(), tzinfo=ET).replace(hour=14).astimezone(UTC),
        "event_end_ts_utc": datetime.combine(event_date, datetime.min.time(), tzinfo=ET).replace(hour=14, minute=1).astimezone(UTC),
        "event_type": "FOMC_DECISION",
        "event_name": "FOMC",
        "source": "TEST",
        "verified": True,
    }
    values.update(overrides)
    return MacroEventRecord.model_validate(values)


def test_cal_001_to_003_session_shape_is_frozen_and_strict() -> None:
    assert list(TradingSessionRecord.model_fields) == [
        "session_date_et", "session_seq", "open_ts_utc", "regular_close_ts_utc",
        "is_trading_day", "is_full_session", "is_half_day", "xsp_0dte_exists",
    ]
    record = _session()
    with pytest.raises(ValidationError):
        TradingSessionRecord.model_validate({**record.model_dump(), "extra": 1})
    with pytest.raises(ValidationError):
        record.session_seq = 1  # type: ignore[misc]


def test_cal_004_to_005_strict_integer_and_booleans() -> None:
    with pytest.raises(ValidationError):
        _session(session_seq=True)
    with pytest.raises(ValidationError):
        _session(session_seq="100")
    for field in ("is_trading_day", "is_full_session", "is_half_day", "xsp_0dte_exists"):
        with pytest.raises(ValidationError):
            _session(**{field: 1})
        with pytest.raises(ValidationError):
            _session(**{field: "true"})


def test_cal_006_to_011_session_timestamps_are_aware_utc_and_same_et_date() -> None:
    record = _session(
        open_ts_utc=datetime(2026, 7, 15, 9, 30, tzinfo=ET),
        regular_close_ts_utc=datetime(2026, 7, 15, 16, 0, tzinfo=ET),
    )
    assert record.open_ts_utc == datetime(2026, 7, 15, 13, 30, tzinfo=UTC)
    assert record.regular_close_ts_utc == datetime(2026, 7, 15, 20, 0, tzinfo=UTC)
    for field in ("open_ts_utc", "regular_close_ts_utc"):
        with pytest.raises(ValidationError):
            _session(**{field: datetime(2026, 7, 15, 13, 30)})
    with pytest.raises(ValidationError):
        _session(regular_close_ts_utc=datetime(2026, 7, 15, 13, 29, tzinfo=UTC))
    with pytest.raises(ValidationError):
        _session(open_ts_utc=datetime(2026, 7, 14, 13, 30, tzinfo=UTC))
    with pytest.raises(ValidationError):
        _session(regular_close_ts_utc=datetime(2026, 7, 16, 20, 0, tzinfo=UTC))


def test_cal_012_to_015_session_flags() -> None:
    with pytest.raises(ValidationError):
        _session(is_half_day=True)
    with pytest.raises(ValidationError):
        _session(is_trading_day=False, is_full_session=True)
    with pytest.raises(ValidationError):
        _session(is_trading_day=False, is_full_session=False, is_half_day=True)
    assert _session(is_full_session=False, is_half_day=False).is_trading_day


def test_cal_016_to_021_macro_shape_and_literal_type() -> None:
    assert list(MacroEventRecord.model_fields) == [
        "event_id", "event_date_et", "event_start_ts_utc", "event_end_ts_utc",
        "event_type", "event_name", "source", "verified",
    ]
    assert is_dataclass(_session.__annotations__.get("return", object)) is False
    record = _event(event_type="FOMC_PRESS_CONFERENCE")
    assert record.event_type == "FOMC_PRESS_CONFERENCE"
    with pytest.raises(ValidationError):
        _event(event_type="OTHER")
    with pytest.raises(ValidationError):
        _event(event_type="fomc_decision")
    with pytest.raises(ValidationError):
        MacroEventRecord.model_validate({**record.model_dump(), "extra": 1})
    with pytest.raises(ValidationError):
        record.event_name = "changed"  # type: ignore[misc]


def test_cal_022_to_028_macro_timestamps_and_dates() -> None:
    record = _event(
        event_start_ts_utc=datetime(2026, 7, 15, 14, 0, tzinfo=ET),
        event_end_ts_utc=datetime(2026, 7, 15, 14, 1, tzinfo=ET),
    )
    assert record.event_start_ts_utc == datetime(2026, 7, 15, 18, 0, tzinfo=UTC)
    for field in ("event_start_ts_utc", "event_end_ts_utc"):
        with pytest.raises(ValidationError):
            _event(**{field: datetime(2026, 7, 15, 18, 0)})
    with pytest.raises(ValidationError):
        _event(event_start_ts_utc=datetime(2026, 7, 15, 18, 1, tzinfo=UTC), event_end_ts_utc=datetime(2026, 7, 15, 18, 0, tzinfo=UTC))
    point = _event(event_end_ts_utc=datetime(2026, 7, 15, 18, 0, tzinfo=UTC))
    assert point.event_start_ts_utc == point.event_end_ts_utc
    with pytest.raises(ValidationError):
        _event(event_start_ts_utc=datetime(2026, 7, 14, 18, 0, tzinfo=UTC))
    with pytest.raises(ValidationError):
        _event(event_end_ts_utc=datetime(2026, 7, 16, 18, 0, tzinfo=UTC))


@pytest.mark.parametrize("field", ["event_id", "event_name", "source"])
def test_cal_029_to_031_empty_strings_rejected_without_normalization(field: str) -> None:
    with pytest.raises(ValidationError):
        _event(**{field: ""})
    assert getattr(_event(**{field: " value "}), field) == " value "


def test_cal_032_verified_is_strict_and_cal_033_strings_preserve_case() -> None:
    with pytest.raises(ValidationError):
        _event(verified=1)
    with pytest.raises(ValidationError):
        _event(verified="true")
    assert _event(event_name=" Fomc ").event_name == " Fomc "


def test_cal_034_to_041_sequence_validation() -> None:
    first = _session(session_date_et=date(2026, 7, 13), session_seq=100)
    second = _session(session_date_et=date(2026, 7, 14), session_seq=102)
    assert validate_trading_session_sequence([second, first]) is None
    original = [second, first]
    before = list(original)
    validate_trading_session_sequence(original)
    assert original == before
    with pytest.raises(CalendarIntegrityError):
        validate_trading_session_sequence([first, _session(session_date_et=first.session_date_et, session_seq=101)])
    with pytest.raises(CalendarIntegrityError):
        validate_trading_session_sequence([first, _session(session_date_et=date(2026, 7, 14), session_seq=100)])
    nontrading = _session(session_date_et=date(2026, 7, 14), session_seq=100, is_trading_day=False, is_full_session=False)
    validate_trading_session_sequence([first, nontrading])


def test_cal_042_to_051_decision_and_full_session_gate() -> None:
    summer = build_session_calendar_gate(_session(), [])
    assert summer.decision_ts_utc == datetime(2026, 7, 15, 17, 30, tzinfo=UTC)
    winter = build_session_calendar_gate(_session(session_date_et=date(2026, 1, 15), open_ts_utc=datetime(2026, 1, 15, 14, 30, tzinfo=UTC), regular_close_ts_utc=datetime(2026, 1, 15, 21, 0, tzinfo=UTC)), [])
    assert winter.decision_ts_utc == datetime(2026, 1, 15, 18, 30, tzinfo=UTC)
    assert summer.full_session_eligible and summer.calendar_gate_pass
    assert not build_session_calendar_gate(_session(is_half_day=True, is_full_session=False), []).full_session_eligible
    assert not build_session_calendar_gate(_session(is_trading_day=False, is_full_session=False), []).full_session_eligible
    unusual = build_session_calendar_gate(_session(is_full_session=False, is_half_day=False, xsp_0dte_exists=False), [])
    assert not unusual.full_session_eligible and not unusual.calendar_gate_pass
    no_xsp = build_session_calendar_gate(_session(xsp_0dte_exists=False), [])
    assert no_xsp.full_session_eligible and no_xsp.calendar_gate_pass


def test_cal_052_to_057_standard_fomc_and_date_filtering() -> None:
    session = _session()
    assert not build_session_calendar_gate(session, []).fomc_afternoon_blocked
    point = _event(event_start_ts_utc=datetime(2026, 7, 15, 18, 0, tzinfo=UTC), event_end_ts_utc=datetime(2026, 7, 15, 18, 0, tzinfo=UTC))
    press = _event(event_id="event-2", event_type="FOMC_PRESS_CONFERENCE", event_start_ts_utc=datetime(2026, 7, 15, 19, 0, tzinfo=UTC), event_end_ts_utc=datetime(2026, 7, 15, 19, 30, tzinfo=UTC))
    assert build_session_calendar_gate(session, [point]).fomc_afternoon_blocked
    assert build_session_calendar_gate(session, [press]).fomc_afternoon_blocked
    other = _event(event_date_et=date(2026, 7, 16))
    assert not build_session_calendar_gate(session, [other]).fomc_afternoon_blocked
    assert build_session_calendar_gate(session, [point, press]).fomc_afternoon_blocked
    assert build_session_calendar_gate(session, [press, point]).fomc_afternoon_blocked


@pytest.mark.parametrize(
    ("start", "end", "blocked"),
    [
        ("12:00", "13:30", False), ("13:30", "14:00", True),
        ("13:00", "14:00", True), ("15:00", "16:00", True),
        ("16:00", "17:00", False), ("17:00", "18:00", False),
        ("12:00", "13:00", False),
    ],
)
def test_cal_058_to_064_positive_duration_edges(start: str, end: str, blocked: bool) -> None:
    def ts(value: str) -> datetime:
        hour, minute = map(int, value.split(":"))
        return datetime(2026, 7, 15, hour, minute, tzinfo=ET).astimezone(UTC)
    event = _event(event_start_ts_utc=ts(start), event_end_ts_utc=ts(end))
    assert build_session_calendar_gate(_session(), [event]).fomc_afternoon_blocked is blocked


@pytest.mark.parametrize(("hour", "minute", "second", "microsecond", "blocked"), [(13, 30, 0, 0, True), (16, 0, 0, 0, False), (15, 59, 59, 999999, True)])
def test_cal_065_to_067_point_edges(hour: int, minute: int, second: int, microsecond: int, blocked: bool) -> None:
    point = datetime(2026, 7, 15, hour, minute, second, microsecond, tzinfo=ET).astimezone(UTC)
    event = _event(event_start_ts_utc=point, event_end_ts_utc=point)
    assert build_session_calendar_gate(_session(), [event]).fomc_afternoon_blocked is blocked


def test_cal_068_to_073_event_integrity_and_input_order() -> None:
    with pytest.raises(CalendarIntegrityError):
        build_session_calendar_gate(_session(), [_event(verified=False)])
    with pytest.raises(CalendarIntegrityError):
        build_session_calendar_gate(_session(), [_event(verified=False, event_start_ts_utc=datetime(2026, 7, 15, 10, 0, tzinfo=UTC), event_end_ts_utc=datetime(2026, 7, 15, 10, 1, tzinfo=UTC))])
    duplicate = _event()
    with pytest.raises(CalendarIntegrityError):
        build_session_calendar_gate(_session(), [duplicate, duplicate])
    distinct = [_event(event_id="a"), _event(event_id="b", event_start_ts_utc=datetime(2026, 7, 15, 17, 0, tzinfo=UTC), event_end_ts_utc=datetime(2026, 7, 15, 17, 1, tzinfo=UTC))]
    assert build_session_calendar_gate(_session(), distinct).fomc_afternoon_blocked == build_session_calendar_gate(_session(), list(reversed(distinct))).fomc_afternoon_blocked


def test_cal_074_to_084_composition_and_scope() -> None:
    session = _session()
    clean = build_session_calendar_gate(session, [])
    blocked = build_session_calendar_gate(session, [_event()])
    half = build_session_calendar_gate(_session(is_full_session=False, is_half_day=True), [])
    closed = build_session_calendar_gate(_session(is_trading_day=False, is_full_session=False), [])
    assert clean.calendar_gate_pass is True
    assert blocked.calendar_gate_pass is False
    assert half.calendar_gate_pass is False
    assert closed.calendar_gate_pass is False
    assert is_dataclass(clean) and SessionCalendarGate.__dataclass_params__.frozen
    assert [field.name for field in fields(clean)] == ["session", "decision_ts_utc", "full_session_eligible", "fomc_afternoon_blocked", "calendar_gate_pass"]
    with pytest.raises(FrozenInstanceError):
        clean.calendar_gate_pass = False  # type: ignore[misc]
    assert clean.session is session
    assert not any(name in SessionCalendarGate.__annotations__ for name in ("no_trade_reason", "decision_type", "feature_valid", "label_valid", "model_valid", "xsp_available"))


def test_s206r_cal_009_equal_open_and_close_rejected() -> None:
    same = datetime(2026, 7, 15, 13, 30, tzinfo=UTC)

    with pytest.raises(ValidationError):
        _session(open_ts_utc=same, regular_close_ts_utc=same)


def test_s206r_cal_038_decreasing_session_sequence_rejected() -> None:
    earlier = _session(session_date_et=date(2026, 7, 14), session_seq=100)
    later = _session(session_date_et=date(2026, 7, 15), session_seq=99)

    with pytest.raises(CalendarIntegrityError):
        validate_trading_session_sequence([earlier, later])


def test_s206r_cal_056_any_overlapping_event_blocks() -> None:
    non_overlapping = _event(
        event_id="before-window",
        event_start_ts_utc=datetime(2026, 7, 15, 12, 0, tzinfo=ET),
        event_end_ts_utc=datetime(2026, 7, 15, 13, 0, tzinfo=ET),
    )
    overlapping = _event(
        event_id="inside-window",
        event_start_ts_utc=datetime(2026, 7, 15, 14, 0, tzinfo=ET),
        event_end_ts_utc=datetime(2026, 7, 15, 14, 1, tzinfo=ET),
    )
    session = _session()

    assert build_session_calendar_gate(
        session, [non_overlapping, overlapping]
    ).fomc_afternoon_blocked is True
    assert build_session_calendar_gate(
        session, [overlapping, non_overlapping]
    ).fomc_afternoon_blocked is True


def test_s206r_cal_070_unverified_other_date_event_is_irrelevant() -> None:
    other_date_unverified = _event(
        event_date_et=date(2026, 7, 16),
        verified=False,
    )

    gate = build_session_calendar_gate(_session(), [other_date_unverified])

    assert gate.fomc_afternoon_blocked is False
    assert gate.calendar_gate_pass is True


def test_s206r_cal_079_session_calendar_gate_uses_slots() -> None:
    gate = build_session_calendar_gate(_session(), [])

    assert hasattr(gate, "__dict__") is False
    assert SessionCalendarGate.__slots__ == (
        "session",
        "decision_ts_utc",
        "full_session_eligible",
        "fomc_afternoon_blocked",
        "calendar_gate_pass",
    )
