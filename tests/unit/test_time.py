from datetime import date, datetime, time, timedelta, timezone, tzinfo
from pathlib import Path

import pytest

import oae.temporal as temporal
from oae.config import FrozenConfig, load_config
from oae.temporal import (
    DECISION_TIME_ET,
    MARKET_TIMEZONE,
    MARKET_TIMEZONE_NAME,
    PM_REFERENCE_TIME_ET,
    SESSION_OPEN_TIME_ET,
    UTC,
    age_seconds,
    bar_is_usable_asof,
    decision_ts_et,
    decision_ts_utc,
    in_half_open_interval,
    is_available_asof,
    is_fresh_asof,
    pm_reference_ts_et,
    pm_reference_ts_utc,
    session_date_et_from_timestamp,
    session_open_ts_et,
    session_open_ts_utc,
    to_market_time,
    to_utc,
)


CONFIG_PATH = Path("config/oae_v0_1_frozen.yaml")
TEST_SESSION_DATE = date(2026, 7, 15)


@pytest.fixture
def frozen_config() -> FrozenConfig:
    return load_config(CONFIG_PATH)


def test_time_000_frozen_config_alignment(frozen_config: FrozenConfig) -> None:
    assert frozen_config.timezone == MARKET_TIMEZONE_NAME
    assert frozen_config.decision_time == DECISION_TIME_ET
    assert frozen_config.quotes.max_age_seconds == 2.0


def test_canonical_temporal_constants() -> None:
    assert MARKET_TIMEZONE_NAME == "America/New_York"
    assert MARKET_TIMEZONE.key == MARKET_TIMEZONE_NAME
    assert UTC is timezone.utc
    assert SESSION_OPEN_TIME_ET == time(9, 30, 0)
    assert DECISION_TIME_ET == time(13, 30, 0)
    assert PM_REFERENCE_TIME_ET == time(16, 0, 0)


def test_time_001_pre_decision_event_is_available() -> None:
    decision = decision_ts_et(TEST_SESSION_DATE)
    event = decision - timedelta(milliseconds=1)

    assert is_available_asof(event, decision) is True


def test_time_001b_exact_decision_event_is_available() -> None:
    decision = decision_ts_et(TEST_SESSION_DATE)

    assert is_available_asof(decision, decision) is True


def test_time_002_future_event_is_unavailable() -> None:
    decision = decision_ts_et(TEST_SESSION_DATE)
    event = decision + timedelta(milliseconds=1)

    assert is_available_asof(event, decision) is False


def test_time_003_future_bar_is_rejected() -> None:
    decision = decision_ts_et(TEST_SESSION_DATE)

    assert bar_is_usable_asof(
        decision,
        decision + timedelta(minutes=1),
        decision,
    ) is False


def test_time_004_decision_bar_is_accepted() -> None:
    decision = decision_ts_et(TEST_SESSION_DATE)

    assert bar_is_usable_asof(
        decision - timedelta(minutes=1),
        decision,
        decision,
    ) is True


def test_bar_primitive_does_not_require_one_minute_duration() -> None:
    decision = decision_ts_et(TEST_SESSION_DATE)

    assert bar_is_usable_asof(
        decision - timedelta(minutes=5),
        decision,
        decision,
    ) is True


def test_time_005_half_open_start_is_included() -> None:
    start = decision_ts_et(TEST_SESSION_DATE)
    end = start + timedelta(minutes=1)

    assert in_half_open_interval(start, start, end) is True


def test_time_006_half_open_end_is_excluded() -> None:
    start = decision_ts_et(TEST_SESSION_DATE)
    end = start + timedelta(minutes=1)

    assert in_half_open_interval(end, start, end) is False


@pytest.mark.parametrize("end_delta", (timedelta(0), timedelta(seconds=-1)))
def test_time_007_malformed_half_open_interval_fails(
    end_delta: timedelta,
) -> None:
    start = decision_ts_et(TEST_SESSION_DATE)

    with pytest.raises(ValueError, match="earlier"):
        in_half_open_interval(start, start, start + end_delta)


@pytest.mark.parametrize("end_delta", (timedelta(0), timedelta(seconds=-1)))
def test_time_007_malformed_bar_interval_fails(
    end_delta: timedelta,
) -> None:
    start = decision_ts_et(TEST_SESSION_DATE)

    with pytest.raises(ValueError, match="earlier"):
        bar_is_usable_asof(start, start + end_delta, start)


def test_dst_001_winter_decision_conversion() -> None:
    assert decision_ts_utc(date(2026, 1, 15)) == datetime(
        2026, 1, 15, 18, 30, tzinfo=UTC
    )


def test_dst_002_summer_decision_conversion() -> None:
    assert decision_ts_utc(date(2026, 7, 15)) == datetime(
        2026, 7, 15, 17, 30, tzinfo=UTC
    )


def test_dst_003_post_spring_transition_decision() -> None:
    assert decision_ts_utc(date(2026, 3, 9)) == datetime(
        2026, 3, 9, 17, 30, tzinfo=UTC
    )


def test_dst_004_post_fall_transition_decision() -> None:
    assert decision_ts_utc(date(2026, 11, 2)) == datetime(
        2026, 11, 2, 18, 30, tzinfo=UTC
    )


def test_dst_005_spring_forward_uses_actual_elapsed_time() -> None:
    event = datetime(2026, 3, 8, 1, 30, tzinfo=MARKET_TIMEZONE)
    asof = datetime(2026, 3, 8, 3, 30, tzinfo=MARKET_TIMEZONE)

    assert age_seconds(event, asof) == 3600.0


def test_dst_006_fall_back_uses_actual_elapsed_time() -> None:
    event = datetime(2026, 11, 1, 0, 30, tzinfo=MARKET_TIMEZONE)
    asof = datetime(2026, 11, 1, 2, 30, tzinfo=MARKET_TIMEZONE)

    assert age_seconds(event, asof) == 10800.0


@pytest.mark.parametrize(
    ("session_date", "expected_utc"),
    (
        (
            date(2026, 1, 15),
            datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        ),
        (
            date(2026, 7, 15),
            datetime(2026, 7, 15, 13, 30, tzinfo=UTC),
        ),
    ),
)
def test_dst_007_market_open_winter_and_summer(
    session_date: date,
    expected_utc: datetime,
) -> None:
    local = session_open_ts_et(session_date)

    assert local.timetz().replace(tzinfo=None) == SESSION_OPEN_TIME_ET
    assert local.tzinfo is MARKET_TIMEZONE
    assert session_open_ts_utc(session_date) == expected_utc


@pytest.mark.parametrize(
    ("expiration_date", "expected_utc"),
    (
        (
            date(2026, 1, 15),
            datetime(2026, 1, 15, 21, 0, tzinfo=UTC),
        ),
        (
            date(2026, 7, 15),
            datetime(2026, 7, 15, 20, 0, tzinfo=UTC),
        ),
    ),
)
def test_dst_008_pm_reference_winter_and_summer(
    expiration_date: date,
    expected_utc: datetime,
) -> None:
    local = pm_reference_ts_et(expiration_date)

    assert local.timetz().replace(tzinfo=None) == PM_REFERENCE_TIME_ET
    assert local.tzinfo is MARKET_TIMEZONE
    assert pm_reference_ts_utc(expiration_date) == expected_utc


def test_pm_reference_api_is_not_named_as_settlement_time() -> None:
    assert not any(name.startswith("settlement_ts") for name in temporal.__all__)


def test_date_001_session_date_is_derived_after_market_conversion() -> None:
    timestamp = datetime(2026, 7, 15, 0, 30, tzinfo=UTC)

    assert session_date_et_from_timestamp(timestamp) == date(2026, 7, 14)


def test_date_002_utc_market_round_trip_preserves_instant() -> None:
    timestamp = datetime(2026, 7, 15, 17, 30, 0, 123456, tzinfo=UTC)

    market_timestamp = to_market_time(timestamp)

    assert market_timestamp.tzinfo is MARKET_TIMEZONE
    assert to_utc(market_timestamp) == timestamp
    assert to_utc(market_timestamp).tzinfo is UTC


@pytest.mark.parametrize(
    ("age_milliseconds", "expected"),
    ((1999, True), (2000, True), (2001, False)),
)
def test_quote_time_freshness_boundaries(
    frozen_config: FrozenConfig,
    age_milliseconds: int,
    expected: bool,
) -> None:
    asof = decision_ts_et(TEST_SESSION_DATE)
    event = asof - timedelta(milliseconds=age_milliseconds)

    assert is_fresh_asof(
        event,
        asof,
        frozen_config.quotes.max_age_seconds,
    ) is expected


def test_quote_time_004_future_timestamp_is_never_fresh() -> None:
    asof = decision_ts_et(TEST_SESSION_DATE)
    event = asof + timedelta(milliseconds=1)

    assert age_seconds(event, asof) == -0.001
    assert is_fresh_asof(event, asof, 2.0) is False


@pytest.mark.parametrize("age_milliseconds", (1999, 2000, 2001))
def test_quote_time_005_exact_age_diagnostics(
    age_milliseconds: int,
) -> None:
    asof = decision_ts_et(TEST_SESSION_DATE)
    event = asof - timedelta(milliseconds=age_milliseconds)

    assert age_seconds(event, asof) == pytest.approx(
        age_milliseconds / 1000
    )


@pytest.mark.parametrize(
    "operation",
    (
        pytest.param(lambda value: to_utc(value), id="to-utc"),
        pytest.param(lambda value: to_market_time(value), id="to-market"),
        pytest.param(
            lambda value: session_date_et_from_timestamp(value),
            id="session-date",
        ),
    ),
)
def test_aware_001_naive_timestamp_is_rejected(operation) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        operation(datetime(2026, 7, 15, 13, 30))


@pytest.mark.parametrize(
    "operation",
    (
        pytest.param(
            lambda naive, aware: is_available_asof(naive, aware),
            id="available-naive-event",
        ),
        pytest.param(
            lambda naive, aware: is_available_asof(aware, naive),
            id="available-naive-asof",
        ),
        pytest.param(
            lambda naive, aware: age_seconds(naive, aware),
            id="age-naive-event",
        ),
        pytest.param(
            lambda naive, aware: age_seconds(aware, naive),
            id="age-naive-asof",
        ),
        pytest.param(
            lambda naive, aware: is_fresh_asof(naive, aware, 2.0),
            id="fresh-naive-event",
        ),
        pytest.param(
            lambda naive, aware: is_fresh_asof(aware, naive, 2.0),
            id="fresh-naive-asof",
        ),
        pytest.param(
            lambda naive, aware: in_half_open_interval(
                naive, aware, aware + timedelta(seconds=1)
            ),
            id="interval-naive-event",
        ),
        pytest.param(
            lambda naive, aware: in_half_open_interval(
                aware, naive, aware + timedelta(seconds=1)
            ),
            id="interval-naive-start",
        ),
        pytest.param(
            lambda naive, aware: in_half_open_interval(aware, aware, naive),
            id="interval-naive-end",
        ),
        pytest.param(
            lambda naive, aware: bar_is_usable_asof(
                naive, aware + timedelta(seconds=1), aware
            ),
            id="bar-naive-start",
        ),
        pytest.param(
            lambda naive, aware: bar_is_usable_asof(aware, naive, aware),
            id="bar-naive-end",
        ),
        pytest.param(
            lambda naive, aware: bar_is_usable_asof(
                aware, aware + timedelta(seconds=1), naive
            ),
            id="bar-naive-asof",
        ),
    ),
)
def test_aware_002_naive_comparison_input_is_rejected(operation) -> None:
    naive = datetime(2026, 7, 15, 13, 30)
    aware = decision_ts_et(TEST_SESSION_DATE)

    with pytest.raises(ValueError, match="timezone-aware"):
        operation(naive, aware)


class _NoneOffsetTimezone(tzinfo):
    def utcoffset(self, value: datetime | None) -> None:
        return None

    def dst(self, value: datetime | None) -> None:
        return None

    def tzname(self, value: datetime | None) -> str:
        return "NONE"


def test_aware_datetime_with_none_utc_offset_is_rejected() -> None:
    timestamp = datetime(2026, 7, 15, 13, 30, tzinfo=_NoneOffsetTimezone())

    with pytest.raises(ValueError, match="timezone-aware"):
        to_utc(timestamp)


@pytest.mark.parametrize(
    "max_age_seconds",
    (-1.0, float("nan"), float("inf"), float("-inf")),
)
def test_age_001_invalid_freshness_limit_is_rejected(
    max_age_seconds: float,
) -> None:
    timestamp = decision_ts_et(TEST_SESSION_DATE)

    with pytest.raises(ValueError, match="finite and non-negative"):
        is_fresh_asof(timestamp, timestamp, max_age_seconds)


def test_tz_001_mixed_aware_timezones_compare_by_instant() -> None:
    utc_timestamp = datetime(2026, 7, 15, 17, 30, tzinfo=UTC)
    market_timestamp = datetime(
        2026, 7, 15, 13, 30, tzinfo=MARKET_TIMEZONE
    )

    assert is_available_asof(utc_timestamp, market_timestamp) is True
    assert is_available_asof(market_timestamp, utc_timestamp) is True
    assert age_seconds(utc_timestamp, market_timestamp) == 0.0
