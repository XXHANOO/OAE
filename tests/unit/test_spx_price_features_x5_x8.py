import inspect
import math
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

import oae.features as features_module
from oae.data.decision_session import (
    PITDecisionSessionDataset,
    build_pit_decision_session_dataset,
)
from oae.enums import QualityStatus
from oae.features import (
    SPXPriceFeatureIntegrityError,
    compute_spx_price_features_x5_x8,
)
from oae.schemas.calendar import TradingSessionRecord
from oae.schemas.market import IndexBar1mRecord
from oae.temporal import session_open_ts_utc


ET = ZoneInfo("America/New_York")
SESSION_DATE = date(2026, 7, 15)
OPEN_PRICE = Decimal("100.000000")
OFFICIAL_PREVIOUS_CLOSE = Decimal("99.000000")
EPSILON = 1e-8


def _market_timestamp(hour: int, minute: int) -> datetime:
    return datetime(
        SESSION_DATE.year,
        SESSION_DATE.month,
        SESSION_DATE.day,
        hour,
        minute,
        tzinfo=ET,
    )


def _session() -> TradingSessionRecord:
    return TradingSessionRecord(
        session_date_et=SESSION_DATE,
        session_seq=300,
        open_ts_utc=_market_timestamp(9, 30),
        regular_close_ts_utc=_market_timestamp(16, 0),
        is_trading_day=True,
        is_full_session=True,
        is_half_day=False,
        xsp_0dte_exists=True,
    )


def _bars(
    *,
    open_price: Decimal = OPEN_PRICE,
    closes: list[Decimal] | None = None,
    high_pad: Decimal = Decimal("1.000000"),
    low_pad: Decimal = Decimal("1.000000"),
) -> list[IndexBar1mRecord]:
    path = closes or [
        open_price + Decimal(index + 1) / Decimal("100")
        for index in range(240)
    ]
    assert len(path) == 240
    canonical_open = session_open_ts_utc(SESSION_DATE)
    records: list[IndexBar1mRecord] = []
    for index, close in enumerate(path):
        open_px = open_price if index == 0 else path[index - 1]
        records.append(
            IndexBar1mRecord(
                symbol="SPX",
                session_date_et=SESSION_DATE,
                bar_start_ts_utc=canonical_open + timedelta(minutes=index),
                bar_end_ts_utc=canonical_open + timedelta(minutes=index + 1),
                open=open_px,
                high=max(open_px, close) + high_pad,
                low=min(open_px, close) - low_pad,
                close=close,
                observation_count=10,
                source="TEST_PROVIDER",
                raw_file_id="raw-s210",
                quality_status=QualityStatus.VALID,
            )
        )
    return records


def _build(
    bars: list[IndexBar1mRecord] | None = None,
    *,
    previous_close: Decimal = OFFICIAL_PREVIOUS_CLOSE,
) -> PITDecisionSessionDataset:
    return build_pit_decision_session_dataset(
        _session(),
        bars or _bars(),
        spx_official_prev_close=previous_close,
    )


def _features(
    dataset: PITDecisionSessionDataset | None = None,
) -> tuple[float, float, float, float]:
    return compute_spx_price_features_x5_x8(dataset or _build())


def _expected(dataset: PITDecisionSessionDataset) -> tuple[float, ...]:
    returns = dataset.canonical_minute_returns
    state = dataset.session_state
    return (
        math.sqrt(math.fsum(value * value for value in returns[-30:])),
        math.sqrt(math.fsum(value * value for value in returns)),
        (
            float(state.spx_decision_px)
            - float(state.intraday_low_to_t0)
        )
        / (
            float(state.intraday_high_to_t0)
            - float(state.intraday_low_to_t0)
            + EPSILON
        ),
        abs(
            math.log(
                float(state.spx_decision_px) / float(state.spx_open)
            )
        )
        / (math.fsum(abs(value) for value in returns) + EPSILON),
    )


def test_px58_001_to_008_public_api_output_and_error_contract_are_exact() -> None:
    parameters = inspect.signature(
        compute_spx_price_features_x5_x8
    ).parameters
    assert list(parameters) == ["dataset"]
    assert parameters["dataset"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["dataset"].default is inspect.Parameter.empty
    assert features_module.__all__ == (
        "SPXPriceFeatureIntegrityError",
        "compute_spx_price_features_x1_x4",
        "compute_spx_price_features_x5_x8",
    )
    assert issubclass(SPXPriceFeatureIntegrityError, RuntimeError)
    assert not any(
        "x5_x8" in name and "Error" in name
        for name in features_module.__all__
    )

    result = _features()
    assert isinstance(result, tuple)
    assert len(result) == 4
    assert all(type(value) is float for value in result)
    assert all(math.isfinite(value) for value in result)
    assert result == pytest.approx(_expected(_build()), abs=1e-15)
    assert result[1] >= result[0] - 1e-15


def test_px58_009_to_019_x5_uses_exact_final_30_boundary_window() -> None:
    closes = (
        [Decimal("100")] * 209
        + [Decimal("150"), Decimal("90")]
        + [Decimal("90")] * 28
        + [Decimal("108")]
    )
    dataset = _build(_bars(closes=closes))
    returns = dataset.canonical_minute_returns
    x5, _, _, _ = _features(dataset)
    expected = math.sqrt(math.fsum(value * value for value in returns[-30:]))
    final_29 = math.sqrt(math.fsum(value * value for value in returns[-29:]))
    final_31 = math.sqrt(math.fsum(value * value for value in returns[-31:]))
    from_209 = math.sqrt(math.fsum(value * value for value in returns[209:]))
    rms = expected / math.sqrt(30.0)
    mean = math.fsum(returns[-30:]) / 30.0
    standard_deviation = math.sqrt(
        math.fsum((value - mean) ** 2 for value in returns[-30:]) / 30.0
    )

    assert dataset.canonical_bars[209].bar_end_ts_utc == _market_timestamp(13, 0)
    assert dataset.canonical_bars[210].bar_end_ts_utc == _market_timestamp(13, 1)
    assert dataset.canonical_bars[239].bar_end_ts_utc == _market_timestamp(13, 30)
    assert returns[209] != 0.0
    assert returns[210] != 0.0
    assert returns[239] != 0.0
    assert x5 == pytest.approx(expected, abs=1e-15)
    assert not math.isclose(x5, final_29, abs_tol=1e-12)
    assert not math.isclose(x5, final_31, abs_tol=1e-12)
    assert not math.isclose(x5, from_209, abs_tol=1e-12)
    assert not math.isclose(x5, rms, abs_tol=1e-12)
    assert not math.isclose(x5, standard_deviation, abs_tol=1e-12)
    assert not math.isclose(x5, expected * math.sqrt(252.0), abs_tol=1e-12)


def test_px58_019_pre_1300_returns_cannot_affect_x5() -> None:
    dataset = _build()
    baseline = _features(dataset)
    returns = list(dataset.canonical_minute_returns)
    returns[0] = 0.75
    returns[209] = -0.50
    mutated = _features(replace(dataset, canonical_minute_returns=tuple(returns)))
    assert mutated[0] == baseline[0]
    assert mutated[1] != baseline[1]
    assert mutated[3] != baseline[3]


def test_px58_020_to_026_x6_and_x8_include_first_open_to_close_return() -> None:
    dataset = _build(
        _bars(
            open_price=Decimal("100"),
            closes=[Decimal("125")] * 240,
            high_pad=Decimal("0"),
            low_pad=Decimal("0"),
        )
    )
    returns = dataset.canonical_minute_returns
    x5, x6, _, x8 = _features(dataset)
    numerator = abs(math.log(125.0 / 100.0))

    assert returns[0] == pytest.approx(math.log(1.25), abs=1e-15)
    assert returns[1:] == (0.0,) * 239
    assert x5 == 0.0
    assert x6 == pytest.approx(abs(returns[0]), abs=1e-15)
    assert x6 != 0.0
    assert x6 > x5
    assert x6 != pytest.approx(x6 * math.sqrt(252.0), abs=1e-12)
    assert x8 == pytest.approx(numerator / (abs(returns[0]) + EPSILON), abs=1e-15)
    assert not math.isclose(x8, numerator / EPSILON, abs_tol=1e-12)


def test_px58_027_to_033_x7_uses_exact_epsilon_and_allows_zero_range() -> None:
    tiny_range = _build(
        _bars(
            closes=[Decimal("100")] * 239 + [Decimal("100.000001")],
            high_pad=Decimal("0"),
            low_pad=Decimal("0"),
        )
    )
    expected = 1e-6 / (1e-6 + EPSILON)
    x7 = _features(tiny_range)[2]
    assert x7 == pytest.approx(expected, abs=1e-9)
    assert x7 < 1.0
    assert x7 != 1.0

    flat = _build(
        _bars(
            closes=[OPEN_PRICE] * 240,
            high_pad=Decimal("0"),
            low_pad=Decimal("0"),
        )
    )
    assert flat.session_state.intraday_high_to_t0 == OPEN_PRICE
    assert flat.session_state.intraday_low_to_t0 == OPEN_PRICE
    assert _features(flat)[2] == 0.0


def test_px58_029_to_034_x7_follows_replaced_session_state_range() -> None:
    dataset = _build()
    baseline = _features(dataset)
    decision = dataset.session_state.spx_decision_px
    replacement_state = dataset.session_state.model_copy(
        update={
            "intraday_high_to_t0": decision + Decimal("8"),
            "intraday_low_to_t0": decision - Decimal("2"),
        }
    )
    mutated = _features(replace(dataset, session_state=replacement_state))
    expected = 2.0 / (10.0 + EPSILON)
    assert mutated[2] == pytest.approx(expected, abs=1e-15)
    assert mutated[2] != baseline[2]
    assert mutated[:2] == baseline[:2]
    assert mutated[3] == baseline[3]


def test_px58_035_high_low_only_bar_mutation_changes_only_x7() -> None:
    baseline_bars = _bars(
        closes=[OPEN_PRICE] * 240,
        high_pad=Decimal("1"),
        low_pad=Decimal("1"),
    )
    baseline_dataset = _build(baseline_bars)
    baseline = _features(baseline_dataset)
    mutated_bars = list(baseline_bars)
    values = mutated_bars[100].model_dump()
    values.update(high=Decimal("104"), low=Decimal("98"))
    mutated_bars[100] = IndexBar1mRecord.model_validate(values)
    mutated_dataset = _build(mutated_bars)
    mutated = _features(mutated_dataset)

    assert mutated_dataset.canonical_minute_returns == (
        baseline_dataset.canonical_minute_returns
    )
    assert mutated[2] != baseline[2]
    assert mutated[:2] == baseline[:2]
    assert mutated[3] == baseline[3]


def test_px58_036_to_038_x8_uses_absolute_log_numerator_for_down_session() -> None:
    dataset = _build(
        _bars(
            open_price=Decimal("100"),
            closes=[Decimal("90")] * 240,
            high_pad=Decimal("0"),
            low_pad=Decimal("0"),
        )
    )
    returns = dataset.canonical_minute_returns
    _, _, _, x8 = _features(dataset)
    signed_numerator = math.log(90.0 / 100.0)
    expected = abs(signed_numerator) / (
        math.fsum(abs(value) for value in returns) + EPSILON
    )
    assert signed_numerator < 0.0
    assert x8 > 0.0
    assert x8 == pytest.approx(expected, abs=1e-15)


def test_px58_039_to_043_x8_uses_all_session_total_variation() -> None:
    closes = [
        Decimal("110") if index % 2 == 0 else Decimal("90")
        for index in range(239)
    ] + [Decimal("102")]
    dataset = _build(_bars(closes=closes))
    returns = dataset.canonical_minute_returns
    x8 = _features(dataset)[3]
    numerator = abs(math.log(102.0 / 100.0))
    expected = numerator / (
        math.fsum(abs(value) for value in returns) + EPSILON
    )
    signed_sum_mutant = numerator / (abs(math.fsum(returns)) + EPSILON)
    rv_mutant = numerator / (
        math.sqrt(math.fsum(value * value for value in returns)) + EPSILON
    )

    assert math.fsum(abs(value) for value in returns) > abs(math.fsum(returns))
    assert x8 == pytest.approx(expected, abs=1e-15)
    assert not math.isclose(x8, signed_sum_mutant, abs_tol=1e-12)
    assert not math.isclose(x8, rv_mutant, abs_tol=1e-12)


def test_px58_041_x8_includes_early_variation_before_1300() -> None:
    early = [
        Decimal("110") if index % 2 == 0 else Decimal("90")
        for index in range(209)
    ]
    dataset = _build(
        _bars(closes=early + [Decimal("105")] * 31)
    )
    returns = dataset.canonical_minute_returns
    x8 = _features(dataset)[3]
    numerator = abs(math.log(105.0 / 100.0))
    all_session = numerator / (
        math.fsum(abs(value) for value in returns) + EPSILON
    )
    final_30_mutant = numerator / (
        math.fsum(abs(value) for value in returns[-30:]) + EPSILON
    )
    assert returns[-30:] == (0.0,) * 30
    assert x8 == pytest.approx(all_session, abs=1e-15)
    assert not math.isclose(x8, final_30_mutant, abs_tol=1e-12)


def test_px58_044_to_045_x8_exact_epsilon_and_no_clamping() -> None:
    monotonic = _build()
    x8 = _features(monotonic)[3]
    assert x8 == pytest.approx(_expected(monotonic)[3], abs=1e-15)
    assert x8 < 1.0

    zero_returns = replace(
        monotonic,
        canonical_minute_returns=(0.0,) * 240,
    )
    unclamped = _features(zero_returns)[3]
    assert unclamped == pytest.approx(
        abs(
            math.log(
                float(monotonic.session_state.spx_decision_px)
                / float(monotonic.session_state.spx_open)
            )
        )
        / EPSILON,
        abs=1e-9,
    )
    assert unclamped > 1.0


def test_px58_046_official_previous_close_is_irrelevant() -> None:
    bars = _bars()
    first = _features(_build(bars, previous_close=Decimal("80")))
    second = _features(_build(bars, previous_close=Decimal("120")))
    assert first == second


def test_px58_047_to_048_replacement_return_tuple_is_authoritative() -> None:
    dataset = _build()
    baseline = _features(dataset)
    returns = [0.0] * 240
    returns[0] = 0.30
    returns[209] = 0.40
    returns[210] = 0.50
    returns[239] = -0.12
    replaced = replace(dataset, canonical_minute_returns=tuple(returns))
    result = _features(replaced)
    state = dataset.session_state
    expected = (
        math.sqrt(math.fsum((0.50**2, (-0.12) ** 2))),
        math.sqrt(math.fsum((0.30**2, 0.40**2, 0.50**2, (-0.12) ** 2))),
        baseline[2],
        abs(
            math.log(
                float(state.spx_decision_px) / float(state.spx_open)
            )
        )
        / (math.fsum((0.30, 0.40, 0.50, 0.12)) + EPSILON),
    )
    assert result == pytest.approx(expected, abs=1e-15)
    assert result[2] == baseline[2]
    assert all(result[index] != baseline[index] for index in (0, 1, 3))


def test_px58_049_canonical_bar_prices_cannot_change_x5_x8() -> None:
    dataset = _build()
    baseline = _features(dataset)
    hostile_bars = tuple(
        bar.model_copy(
            update={
                "open": Decimal("700"),
                "high": Decimal("900"),
                "low": Decimal("600"),
                "close": Decimal("800"),
            }
        )
        for bar in dataset.canonical_bars
    )
    mutated = replace(dataset, canonical_bars=hostile_bars)
    assert _features(mutated) == baseline


def test_px58_050_x5_x8_does_not_call_x1_x4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> tuple[float, ...]:
        raise AssertionError("x1-x4 must not be called")

    monkeypatch.setattr(
        features_module,
        "compute_spx_price_features_x1_x4",
        forbidden,
    )
    assert _features() == pytest.approx(_expected(_build()), abs=1e-15)


def test_px58_051_wrong_dataset_type_fails_closed() -> None:
    with pytest.raises(SPXPriceFeatureIntegrityError, match="dataset"):
        compute_spx_price_features_x5_x8(object())  # type: ignore[arg-type]


def test_px58_052_noncanonical_decision_timestamp_fails_closed() -> None:
    dataset = _build()
    malformed = replace(
        dataset,
        decision_ts_utc=dataset.decision_ts_utc + timedelta(seconds=1),
    )
    with pytest.raises(SPXPriceFeatureIntegrityError, match="decision"):
        _features(malformed)


def test_px58_053_returns_must_be_tuple() -> None:
    dataset = _build()
    malformed = replace(
        dataset,
        canonical_minute_returns=list(dataset.canonical_minute_returns),  # type: ignore[arg-type]
    )
    with pytest.raises(SPXPriceFeatureIntegrityError, match="tuple"):
        _features(malformed)


def test_px58_054_239_returns_fail_closed() -> None:
    dataset = _build()
    malformed = replace(
        dataset,
        canonical_minute_returns=dataset.canonical_minute_returns[:-1],
    )
    with pytest.raises(SPXPriceFeatureIntegrityError, match="240"):
        _features(malformed)


def test_px58_055_non_float_return_fails_closed() -> None:
    dataset = _build()
    returns = list(dataset.canonical_minute_returns)
    returns[100] = 0  # type: ignore[list-item]
    with pytest.raises(SPXPriceFeatureIntegrityError, match="Python float"):
        _features(replace(dataset, canonical_minute_returns=tuple(returns)))


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_px58_056_to_058_nonfinite_return_fails_closed(value: float) -> None:
    dataset = _build()
    returns = list(dataset.canonical_minute_returns)
    returns[100] = value
    with pytest.raises(SPXPriceFeatureIntegrityError, match="finite"):
        _features(replace(dataset, canonical_minute_returns=tuple(returns)))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("spx_open", Decimal("0")),
        ("spx_decision_px", Decimal("-1")),
        ("intraday_high_to_t0", Decimal("NaN")),
        ("intraday_low_to_t0", Decimal("Infinity")),
    ],
)
def test_px58_059_to_061_invalid_state_price_fails_closed(
    field: str,
    value: Decimal,
) -> None:
    dataset = _build()
    state = dataset.session_state.model_copy(update={field: value})
    with pytest.raises(SPXPriceFeatureIntegrityError, match="finite|positive"):
        _features(replace(dataset, session_state=state))


def test_px58_062_high_below_low_fails_closed() -> None:
    dataset = _build()
    state = dataset.session_state.model_copy(
        update={
            "intraday_high_to_t0": Decimal("99"),
            "intraday_low_to_t0": Decimal("100"),
        }
    )
    with pytest.raises(SPXPriceFeatureIntegrityError, match="high"):
        _features(replace(dataset, session_state=state))


@pytest.mark.parametrize("decision", [Decimal("98"), Decimal("110")])
def test_px58_063_decision_outside_range_fails_closed(
    decision: Decimal,
) -> None:
    dataset = _build()
    state = dataset.session_state.model_copy(
        update={
            "spx_decision_px": decision,
            "intraday_high_to_t0": Decimal("105"),
            "intraday_low_to_t0": Decimal("99"),
        }
    )
    with pytest.raises(SPXPriceFeatureIntegrityError, match="range"):
        _features(replace(dataset, session_state=state))


def test_px58_064_overflowing_squared_reduction_fails_closed() -> None:
    dataset = _build()
    returns = (1e308,) + (0.0,) * 239
    with pytest.raises(SPXPriceFeatureIntegrityError, match="reductions"):
        _features(replace(dataset, canonical_minute_returns=returns))


def test_compute_x5_x8_is_pure_and_does_not_mutate_dataset() -> None:
    dataset = _build()
    before = dataset
    _features(dataset)
    assert dataset == before
