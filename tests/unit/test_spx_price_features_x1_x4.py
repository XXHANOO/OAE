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
    compute_spx_price_features_x1_x4,
)
from oae.schemas.calendar import TradingSessionRecord
from oae.schemas.market import IndexBar1mRecord
from oae.temporal import decision_ts_utc, session_open_ts_utc


ET = ZoneInfo("America/New_York")
SESSION_DATE = date(2026, 7, 15)
OFFICIAL_PREVIOUS_CLOSE = Decimal("96.750000")
OPEN_PRICE = Decimal("101.250000")
DECISION_PRICE = Decimal("114.875000")


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
        session_seq=200,
        open_ts_utc=_market_timestamp(9, 30),
        regular_close_ts_utc=_market_timestamp(16, 0),
        is_trading_day=True,
        is_full_session=True,
        is_half_day=False,
        xsp_0dte_exists=True,
    )


def _bar(
    start: datetime,
    *,
    open_px: Decimal,
    close: Decimal,
) -> IndexBar1mRecord:
    return IndexBar1mRecord(
        symbol="SPX",
        session_date_et=SESSION_DATE,
        bar_start_ts_utc=start,
        bar_end_ts_utc=start + timedelta(minutes=1),
        open=open_px,
        high=max(open_px, close) + Decimal("0.750000"),
        low=min(open_px, close) - Decimal("0.750000"),
        close=close,
        observation_count=12,
        source="TEST_PROVIDER",
        raw_file_id="raw-s209",
        quality_status=QualityStatus.VALID,
    )


def _replace_bar(
    bar: IndexBar1mRecord,
    *,
    open_px: Decimal | None = None,
    close: Decimal | None = None,
) -> IndexBar1mRecord:
    replacement_open = bar.open if open_px is None else open_px
    replacement_close = bar.close if close is None else close
    values = bar.model_dump()
    values.update(open=replacement_open, close=replacement_close)
    if max(replacement_open, replacement_close) > bar.high:
        values["high"] = max(replacement_open, replacement_close) + Decimal(
            "0.750000"
        )
    if min(replacement_open, replacement_close) < bar.low:
        values["low"] = min(replacement_open, replacement_close) - Decimal(
            "0.750000"
        )
    return IndexBar1mRecord.model_validate(values)


def _bars() -> list[IndexBar1mRecord]:
    deltas = (
        Decimal("0.370000"),
        Decimal("-0.220000"),
        Decimal("0.110000"),
        Decimal("0.440000"),
        Decimal("-0.310000"),
    )
    closes: list[Decimal] = []
    price = OPEN_PRICE
    for index in range(240):
        price += deltas[index % len(deltas)]
        closes.append(price)

    closes[208] = Decimal("105.125000")  # 12:59 close
    closes[209] = Decimal("109.875000")  # 13:00 close
    closes[210] = Decimal("103.625000")  # 13:01 close
    closes[233] = Decimal("111.125000")  # 13:24 close
    closes[234] = Decimal("107.375000")  # 13:25 close
    closes[235] = Decimal("112.625000")  # 13:26 close
    closes[239] = DECISION_PRICE  # 13:30 close

    canonical_open = session_open_ts_utc(SESSION_DATE)
    records: list[IndexBar1mRecord] = []
    for index, close in enumerate(closes):
        open_px = OPEN_PRICE if index == 0 else closes[index - 1]
        if index == 209:
            open_px = Decimal("106.875000")
        elif index == 234:
            open_px = Decimal("109.250000")
        records.append(
            _bar(
                canonical_open + timedelta(minutes=index),
                open_px=open_px,
                close=close,
            )
        )
    return records


def _assert_only_bar_field_changed(
    original: IndexBar1mRecord,
    mutated: IndexBar1mRecord,
    field_name: str,
) -> None:
    original_values = original.model_dump()
    mutated_values = mutated.model_dump()
    assert original_values.pop(field_name) != mutated_values.pop(field_name)
    assert mutated_values == original_values


def _build(
    bars: list[IndexBar1mRecord] | None = None,
    *,
    previous_close: Decimal = OFFICIAL_PREVIOUS_CLOSE,
) -> PITDecisionSessionDataset:
    return build_pit_decision_session_dataset(
        _session(),
        bars if bars is not None else _bars(),
        spx_official_prev_close=previous_close,
    )


def _features(
    dataset: PITDecisionSessionDataset | None = None,
) -> tuple[float, float, float, float]:
    return compute_spx_price_features_x1_x4(dataset or _build())


def test_pfx_001_integrity_error_is_dedicated_runtime_error() -> None:
    assert issubclass(SPXPriceFeatureIntegrityError, RuntimeError)
    assert SPXPriceFeatureIntegrityError is not RuntimeError


def test_pfx_002_to_003_public_api_and_signature_are_exact() -> None:
    parameters = inspect.signature(
        compute_spx_price_features_x1_x4
    ).parameters
    assert list(parameters) == ["dataset"]
    assert parameters["dataset"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["dataset"].default is inspect.Parameter.empty
    assert features_module.__all__ == (
        "SPXPriceFeatureIntegrityError",
        "compute_spx_price_features_x1_x4",
    )


def test_pfx_004_to_007_output_contract_is_exact() -> None:
    result = _features()
    assert isinstance(result, tuple)
    assert len(result) == 4
    assert all(isinstance(value, float) for value in result)
    assert all(math.isfinite(value) for value in result)


def test_pfx_008_to_011_x1_uses_log_open_over_official_close() -> None:
    dataset = _build()
    x1, _, _, _ = _features(dataset)
    expected = math.log(
        float(dataset.session_state.spx_open)
        / float(dataset.session_state.spx_official_prev_close)
    )
    wrong_decision_numerator = math.log(
        float(dataset.session_state.spx_decision_px)
        / float(dataset.session_state.spx_official_prev_close)
    )
    wrong_simple_return = (
        float(dataset.session_state.spx_open)
        / float(dataset.session_state.spx_official_prev_close)
        - 1.0
    )

    assert x1 == pytest.approx(expected, abs=1e-15)
    assert not math.isclose(x1, wrong_decision_numerator, abs_tol=1e-12)
    assert not math.isclose(x1, wrong_simple_return, abs_tol=1e-12)
    assert x1 > 0.0


def test_pfx_009_and_013_previous_close_changes_only_x1() -> None:
    first = _features(_build(previous_close=Decimal("92.125000")))
    second = _features(_build(previous_close=Decimal("99.625000")))
    assert first[0] != second[0]
    assert first[1:] == second[1:]


def test_pfx_012_to_015_x2_uses_log_decision_over_open() -> None:
    dataset = _build()
    _, x2, _, _ = _features(dataset)
    expected = math.log(
        float(dataset.session_state.spx_decision_px)
        / float(dataset.session_state.spx_open)
    )
    wrong_previous_close = math.log(
        float(dataset.session_state.spx_decision_px)
        / float(dataset.session_state.spx_official_prev_close)
    )
    wrong_simple_return = (
        float(dataset.session_state.spx_decision_px)
        / float(dataset.session_state.spx_open)
        - 1.0
    )

    assert x2 == pytest.approx(expected, abs=1e-15)
    assert not math.isclose(x2, wrong_previous_close, abs_tol=1e-12)
    assert not math.isclose(x2, wrong_simple_return, abs_tol=1e-12)
    assert x2 == pytest.approx(
        sum(dataset.canonical_minute_returns),
        abs=1e-14,
    )


def test_pfx_016_to_019_x3_uses_exact_1325_close_anchor() -> None:
    dataset = _build()
    bars = dataset.canonical_bars
    _, _, x3, _ = _features(dataset)
    expected = math.log(float(bars[-1].close) / float(bars[234].close))
    wrong_1324 = math.log(float(bars[-1].close) / float(bars[233].close))
    wrong_1326 = math.log(float(bars[-1].close) / float(bars[235].close))

    assert bars[233].bar_end_ts_utc == _market_timestamp(13, 24)
    assert bars[234].bar_end_ts_utc == _market_timestamp(13, 25)
    assert bars[235].bar_end_ts_utc == _market_timestamp(13, 26)
    assert bars[234] is bars[-6]
    assert len({bars[index].close for index in (233, 234, 235)}) == 3
    assert x3 == pytest.approx(expected, abs=1e-15)
    assert not math.isclose(x3, wrong_1324, abs_tol=1e-12)
    assert not math.isclose(x3, wrong_1326, abs_tol=1e-12)
    assert x3 == pytest.approx(
        sum(dataset.canonical_minute_returns[-5:]),
        abs=1e-14,
    )


def test_pfx_020_changing_only_1325_close_changes_only_x3() -> None:
    baseline = _features()
    bars = _bars()
    original = bars[234]
    bars[234] = _replace_bar(original, close=Decimal("108.000000"))
    _assert_only_bar_field_changed(original, bars[234], "close")
    mutated = _features(_build(bars))
    assert mutated[2] != baseline[2]
    assert mutated[:2] == baseline[:2]
    assert mutated[3] == baseline[3]


def test_pfx_021_1325_anchor_open_is_irrelevant() -> None:
    baseline_dataset = _build()
    baseline = _features(baseline_dataset)
    bars = _bars()
    assert bars[234].open != bars[233].close
    assert bars[234].open != bars[234].close
    original = bars[234]
    bars[234] = _replace_bar(original, open_px=Decimal("108.750000"))
    _assert_only_bar_field_changed(original, bars[234], "open")
    mutated_dataset = _build(bars)

    assert mutated_dataset.canonical_bars[234].open != bars[234].close
    assert _features(mutated_dataset) == baseline


def test_pfx_022_to_025_x4_uses_exact_1300_close_anchor() -> None:
    dataset = _build()
    bars = dataset.canonical_bars
    _, _, _, x4 = _features(dataset)
    expected = math.log(float(bars[-1].close) / float(bars[209].close))
    wrong_1259 = math.log(float(bars[-1].close) / float(bars[208].close))
    wrong_1301 = math.log(float(bars[-1].close) / float(bars[210].close))

    assert bars[208].bar_end_ts_utc == _market_timestamp(12, 59)
    assert bars[209].bar_end_ts_utc == _market_timestamp(13, 0)
    assert bars[210].bar_end_ts_utc == _market_timestamp(13, 1)
    assert bars[209] is bars[-31]
    assert len({bars[index].close for index in (208, 209, 210)}) == 3
    assert x4 == pytest.approx(expected, abs=1e-15)
    assert not math.isclose(x4, wrong_1259, abs_tol=1e-12)
    assert not math.isclose(x4, wrong_1301, abs_tol=1e-12)
    assert x4 == pytest.approx(
        sum(dataset.canonical_minute_returns[-30:]),
        abs=1e-14,
    )


def test_pfx_026_changing_only_1300_close_changes_only_x4() -> None:
    baseline = _features()
    bars = _bars()
    original = bars[209]
    bars[209] = _replace_bar(original, close=Decimal("108.375000"))
    _assert_only_bar_field_changed(original, bars[209], "close")
    mutated = _features(_build(bars))
    assert mutated[3] != baseline[3]
    assert mutated[:3] == baseline[:3]


def test_pfx_027_1300_anchor_open_is_irrelevant() -> None:
    baseline_dataset = _build()
    baseline = _features(baseline_dataset)
    bars = _bars()
    assert bars[209].open != bars[208].close
    assert bars[209].open != bars[209].close
    original = bars[209]
    bars[209] = _replace_bar(original, open_px=Decimal("108.250000"))
    _assert_only_bar_field_changed(original, bars[209], "open")
    mutated_dataset = _build(bars)

    assert mutated_dataset.canonical_bars[209].open != bars[209].close
    assert _features(mutated_dataset) == baseline


def test_pfx_028_changing_current_open_changes_x1_and_x2_only() -> None:
    baseline_dataset = _build()
    baseline = _features(baseline_dataset)
    bars = _bars()
    original = bars[0]
    bars[0] = _replace_bar(original, open_px=Decimal("100.750000"))
    _assert_only_bar_field_changed(original, bars[0], "open")
    mutated_dataset = _build(bars)
    mutated = _features(mutated_dataset)

    assert mutated[0] == pytest.approx(
        math.log(100.75 / float(OFFICIAL_PREVIOUS_CLOSE)),
        abs=1e-15,
    )
    assert mutated[1] == pytest.approx(
        math.log(float(DECISION_PRICE) / 100.75),
        abs=1e-15,
    )
    assert mutated[:2] != baseline[:2]
    assert mutated[2:] == baseline[2:]


def test_pfx_029_changing_decision_close_changes_x2_x3_x4_only() -> None:
    baseline = _features()
    bars = _bars()
    original = bars[-1]
    bars[-1] = _replace_bar(original, close=Decimal("116.625000"))
    _assert_only_bar_field_changed(original, bars[-1], "close")
    mutated = _features(_build(bars))
    assert mutated[0] == baseline[0]
    assert all(mutated[index] != baseline[index] for index in (1, 2, 3))


def test_pfx_030_hostile_return_tuple_cannot_change_features() -> None:
    dataset = _build()
    baseline = _features(dataset)
    hostile = tuple((index - 120) * 987.654321 for index in range(240))
    replaced_dataset = replace(dataset, canonical_minute_returns=hostile)
    assert _features(replaced_dataset) == baseline


def test_pfx_031_single_return_mutation_cannot_change_features() -> None:
    dataset = _build()
    baseline = _features(dataset)
    returns = list(dataset.canonical_minute_returns)
    returns[137] = 1_000_000.125
    replaced_dataset = replace(
        dataset,
        canonical_minute_returns=tuple(returns),
    )
    assert _features(replaced_dataset) == baseline


def test_pfx_032_noncanonical_decision_timestamp_fails_closed() -> None:
    dataset = _build()
    malformed = replace(
        dataset,
        decision_ts_utc=dataset.decision_ts_utc + timedelta(seconds=1),
    )
    with pytest.raises(SPXPriceFeatureIntegrityError, match="decision"):
        _features(malformed)


def test_pfx_033_239_canonical_bars_fail_closed() -> None:
    dataset = _build()
    malformed = replace(dataset, canonical_bars=dataset.canonical_bars[:-1])
    with pytest.raises(SPXPriceFeatureIntegrityError, match="240"):
        _features(malformed)


def test_pfx_034_239_canonical_returns_fail_closed() -> None:
    dataset = _build()
    malformed = replace(
        dataset,
        canonical_minute_returns=dataset.canonical_minute_returns[:-1],
    )
    with pytest.raises(SPXPriceFeatureIntegrityError, match="240"):
        _features(malformed)


def test_pfx_035_missing_1325_anchor_fails_closed() -> None:
    dataset = _build()
    bars = list(dataset.canonical_bars)
    bars[234] = bars[233]
    malformed = replace(dataset, canonical_bars=tuple(bars))
    with pytest.raises(SPXPriceFeatureIntegrityError, match="13:25"):
        _features(malformed)


def test_pfx_036_missing_1300_anchor_fails_closed() -> None:
    dataset = _build()
    bars = list(dataset.canonical_bars)
    bars[209] = bars[208]
    malformed = replace(dataset, canonical_bars=tuple(bars))
    with pytest.raises(SPXPriceFeatureIntegrityError, match="13:00"):
        _features(malformed)


def test_pfx_037_first_bar_open_state_mismatch_fails_closed() -> None:
    dataset = _build()
    bars = list(dataset.canonical_bars)
    bars[0] = _replace_bar(bars[0], open_px=bars[0].open + Decimal("1"))
    malformed = replace(dataset, canonical_bars=tuple(bars))
    with pytest.raises(SPXPriceFeatureIntegrityError, match="first-bar open"):
        _features(malformed)


def test_pfx_038_final_bar_close_state_mismatch_fails_closed() -> None:
    dataset = _build()
    bars = list(dataset.canonical_bars)
    bars[-1] = _replace_bar(bars[-1], close=bars[-1].close + Decimal("1"))
    malformed = replace(dataset, canonical_bars=tuple(bars))
    with pytest.raises(SPXPriceFeatureIntegrityError, match="final-bar close"):
        _features(malformed)


def test_pfx_039_nonpositive_required_price_fails_closed() -> None:
    dataset = _build()
    malformed_state = dataset.session_state.model_copy(
        update={"spx_official_prev_close": Decimal("0")}
    )
    malformed = replace(dataset, session_state=malformed_state)
    with pytest.raises(SPXPriceFeatureIntegrityError, match="positive"):
        _features(malformed)


def test_pfx_040_nonfinite_required_price_fails_closed() -> None:
    dataset = _build()
    bars = list(dataset.canonical_bars)
    bars[234] = bars[234].model_copy(update={"close": Decimal("NaN")})
    malformed = replace(dataset, canonical_bars=tuple(bars))
    with pytest.raises(SPXPriceFeatureIntegrityError, match="finite"):
        _features(malformed)


def test_nonfinite_computed_price_ratio_fails_closed() -> None:
    dataset = _build()
    malformed_state = dataset.session_state.model_copy(
        update={
            "spx_official_prev_close": Decimal("1e-308"),
            "spx_open": Decimal("1e308"),
        }
    )
    bars = list(dataset.canonical_bars)
    bars[0] = bars[0].model_copy(update={"open": Decimal("1e308")})
    malformed = replace(
        dataset,
        session_state=malformed_state,
        canonical_bars=tuple(bars),
    )
    with pytest.raises(SPXPriceFeatureIntegrityError, match="ratio"):
        _features(malformed)


def test_pfx_041_to_045_no_scope_leak_or_alternate_input_boundary() -> None:
    public_names = features_module.__all__
    parameters = inspect.signature(
        compute_spx_price_features_x1_x4
    ).parameters
    assert not any(
        f"x{index}" in name
        for index in range(5, 12)
        for name in public_names
    )
    assert list(parameters) == ["dataset"]
    assert "bars" not in parameters
    assert "previous_close" not in parameters
    assert "decision_ts" not in parameters
    assert all(
        forbidden not in parameters
        for forbidden in ("option_chain", "config", "database")
    )


def test_feature_function_does_not_mutate_canonical_dataset() -> None:
    dataset = _build()
    before = dataset
    _features(dataset)
    assert dataset == before
    assert dataset.decision_ts_utc == decision_ts_utc(SESSION_DATE)
