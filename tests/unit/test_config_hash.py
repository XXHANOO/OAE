import hashlib
from copy import deepcopy
from datetime import time
from decimal import Decimal
from pathlib import Path

import pytest

from oae.config import (
    FROZEN_V0_1_CONFIG_SHA256,
    FrozenConfig,
    _canonical_config_bytes,
    _canonical_decimal_text,
    _normalize_for_config_hash,
    compute_config_sha256,
    load_config,
    validate_frozen_v0_1,
)
from oae.enums import SettlementStyle


CONFIG_PATH = Path("config/oae_v0_1_frozen.yaml")
HASH_PATH = Path("config/oae_v0_1_frozen.sha256")
RAW_YAML_SHA256 = "a8043d2e8959fa8073951406bdef103afb1a45163861db09cdd66a261f3f6fa0"
NORMALIZED_CONFIG_SHA256 = (
    "ece897f1dd038743462322480aec20aba05b219ce7af8b2e4e38f7a013f11044"
)
GOLDEN_CANONICAL_JSON = (
    '{"ambiguity":{"max_score_difference":{"$float":"0x1.47ae147ae147bp-7"}},'
    '"bootstrap":{"base_seed":20260813,"draws":1000},'
    '"candidate":{"max_moneyness_distance":{"$float":"0x1.47ae147ae147bp-8"}},'
    '"decision_time":{"$time":"13:30:00.000000"},'
    '"edge":{"min_ev_over_max_loss":{"$float":"0x1.999999999999ap-4"},'
    '"min_ev_usd":{"$decimal":"5"},'
    '"min_lcb_over_max_loss":{"$float":"0x1.47ae147ae147bp-6"},'
    '"min_lcb_usd_exclusive":{"$decimal":"0"},'
    '"min_probability_profit":{"$float":"0x1.999999999999ap-2"}},'
    '"execution":{"max_absolute_friction":{"$decimal":"0.05"},'
    '"max_debit":{"$decimal":"0.75"},'
    '"max_relative_friction":{"$float":"0x1.0000000000000p-2"},'
    '"min_debit":{"$decimal":"0.15"},'
    '"model":"CONSERVATIVE_NATURAL_ONE_LOT",'
    '"tick_size":{"$decimal":"0.01"}},'
    '"fees":{"conservative_floor_usd":{"$decimal":"3"}},'
    '"health":{"min_distribution_skill":{"$float":"0x1.47ae147ae147bp-6"},'
    '"window":126},'
    '"instrument":{"multiplier":100,"settlement":{"$enum":"PM"},'
    '"signal_underlying":"SPX","trade_underlying":"XSP"},'
    '"model":{"bandwidth_neighbor":40,'
    '"feature_clip":{"$float":"0x1.4000000000000p+2"},"k":80,'
    '"min_neff":{"$float":"0x1.e000000000000p+4"},"min_train":504,'
    '"recency_half_life":252,"train_window":756},'
    '"ood":{"percentile":{"$float":"0x1.fd70a3d70a3d7p-1"}},'
    '"quotes":{"max_age_seconds":{"$float":"0x1.0000000000000p+1"},'
    '"min_ask_size":1,"min_bid_size":1},'
    '"strategy":{"allowed":[{"$enum":"BULL_CALL_DEBIT"},'
    '{"$enum":"BEAR_PUT_DEBIT"}],"hold_to_settlement":true,'
    '"max_trades_per_day":1,"spread_width":{"$decimal":"1"}},'
    '"timezone":"America/New_York","version":"OAE-v0.1.0"}'
)


@pytest.fixture
def canonical_config() -> FrozenConfig:
    return load_config(CONFIG_PATH)


def mutated_config(config: FrozenConfig, *path_and_value: object) -> FrozenConfig:
    *path, value = path_and_value
    data = deepcopy(config.model_dump(mode="python"))
    target = data
    for key in path[:-1]:
        assert isinstance(target, dict)
        target = target[key]
    assert isinstance(target, dict)
    target[path[-1]] = value
    return FrozenConfig.model_validate(data)


def test_hash_001_golden_canonical_bytes(canonical_config: FrozenConfig) -> None:
    canonical_bytes = _canonical_config_bytes(canonical_config)

    assert canonical_bytes.decode("utf-8") == GOLDEN_CANONICAL_JSON
    assert len(canonical_bytes) == 1547
    assert not canonical_bytes.endswith(b"\n")


def test_hash_002_golden_normalized_sha256(canonical_config: FrozenConfig) -> None:
    assert compute_config_sha256(canonical_config) == NORMALIZED_CONFIG_SHA256


def test_hash_003_hash_file_exact_contents() -> None:
    assert HASH_PATH.read_bytes() == (NORMALIZED_CONFIG_SHA256 + "\n").encode()


def test_hash_004_code_constant_agrees_with_hash_file() -> None:
    assert FROZEN_V0_1_CONFIG_SHA256 == HASH_PATH.read_text().removesuffix("\n")


def test_hash_005_canonical_validator_passes(
    canonical_config: FrozenConfig,
) -> None:
    assert validate_frozen_v0_1(canonical_config) is None


def test_hash_006_k_mutation_fails(canonical_config: FrozenConfig) -> None:
    mutated = mutated_config(canonical_config, "model", "k", 81)

    assert compute_config_sha256(mutated) != NORMALIZED_CONFIG_SHA256
    with pytest.raises(
        ValueError,
        match=f"expected {NORMALIZED_CONFIG_SHA256}, actual [0-9a-f]{{64}}",
    ):
        validate_frozen_v0_1(mutated)


def test_hash_007_execution_model_mutation_fails(
    canonical_config: FrozenConfig,
) -> None:
    mutated = mutated_config(canonical_config, "execution", "model", "MIDPOINT")

    assert compute_config_sha256(mutated) != NORMALIZED_CONFIG_SHA256
    with pytest.raises(ValueError):
        validate_frozen_v0_1(mutated)


def test_hash_008_lcb_threshold_mutation_fails(
    canonical_config: FrozenConfig,
) -> None:
    mutated = mutated_config(
        canonical_config,
        "edge",
        "min_lcb_usd_exclusive",
        Decimal("-0.01"),
    )

    assert compute_config_sha256(mutated) != NORMALIZED_CONFIG_SHA256
    with pytest.raises(ValueError):
        validate_frozen_v0_1(mutated)


def test_hash_009_strategy_order_is_identity_significant(
    canonical_config: FrozenConfig,
) -> None:
    mutated = mutated_config(
        canonical_config,
        "strategy",
        "allowed",
        tuple(reversed(canonical_config.strategy.allowed)),
    )

    assert compute_config_sha256(mutated) != NORMALIZED_CONFIG_SHA256
    with pytest.raises(ValueError):
        validate_frozen_v0_1(mutated)


def test_hash_010_decimal_textual_scale_is_identity_neutral(
    canonical_config: FrozenConfig,
) -> None:
    data = deepcopy(canonical_config.model_dump(mode="python"))
    data["fees"]["conservative_floor_usd"] = Decimal("3.000000")
    data["strategy"]["spread_width"] = Decimal("1.0000")
    equivalent = FrozenConfig.model_validate(data)

    assert compute_config_sha256(equivalent) == NORMALIZED_CONFIG_SHA256


def test_hash_011_negative_decimal_zero_canonicalizes_to_zero() -> None:
    assert _canonical_decimal_text(Decimal("-0.00")) == "0"


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (Decimal("0"), "0"),
        (Decimal("-0.00"), "0"),
        (Decimal("1.0"), "1"),
        (Decimal("1.000"), "1"),
        (Decimal("3.00"), "3"),
        (Decimal("0.0100"), "0.01"),
        (Decimal("0.15"), "0.15"),
        (Decimal("1000.00"), "1000"),
        (Decimal("1E+3"), "1000"),
    ),
)
def test_hash_012_decimal_canonical_vectors(
    value: Decimal,
    expected: str,
) -> None:
    assert _canonical_decimal_text(value) == expected


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
def test_hash_013_non_finite_float_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        _normalize_for_config_hash(value)


@pytest.mark.parametrize(
    "value",
    (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")),
)
def test_hash_014_non_finite_decimal_rejected(value: Decimal) -> None:
    with pytest.raises(ValueError):
        _normalize_for_config_hash(value)


def test_hash_015_unsupported_type_rejected() -> None:
    with pytest.raises(TypeError):
        _normalize_for_config_hash(object())


def test_hash_016_mapping_keys_must_be_strings() -> None:
    with pytest.raises(TypeError):
        _normalize_for_config_hash({1: "value"})


@pytest.mark.parametrize("value", (True, False))
def test_hash_017_bool_is_not_encoded_as_int(value: bool) -> None:
    normalized = _normalize_for_config_hash(value)

    assert normalized is value
    assert type(normalized) is bool


def test_hash_018_float_uses_exact_hexadecimal_representation() -> None:
    assert _normalize_for_config_hash(0.25) == {
        "$float": "0x1.0000000000000p-2"
    }


def test_hash_019_enum_tagged_before_string() -> None:
    assert _normalize_for_config_hash(SettlementStyle.PM) == {"$enum": "PM"}


def test_hash_020_time_precision_is_explicit() -> None:
    assert _normalize_for_config_hash(time(13, 30, 0)) == {
        "$time": "13:30:00.000000"
    }
    assert _normalize_for_config_hash(time(13, 30, 0, 1)) == {
        "$time": "13:30:00.000001"
    }


def test_hash_021_mapping_order_does_not_affect_hash(
    canonical_config: FrozenConfig,
) -> None:
    data = canonical_config.model_dump(mode="python")
    reversed_data = dict(reversed(tuple(data.items())))
    equivalent = FrozenConfig.model_validate(reversed_data)

    assert compute_config_sha256(equivalent) == NORMALIZED_CONFIG_SHA256


def test_hash_022_raw_yaml_identity_is_different() -> None:
    raw_hash = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()

    assert raw_hash == RAW_YAML_SHA256
    assert raw_hash != NORMALIZED_CONFIG_SHA256
