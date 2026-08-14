from datetime import time
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from oae.config import (
    AmbiguityConfig,
    BootstrapConfig,
    CandidateConfig,
    EdgeConfig,
    ExecutionConfig,
    FeesConfig,
    FrozenConfig,
    HealthConfig,
    InstrumentConfig,
    ModelConfig,
    OODConfig,
    QuotesConfig,
    StrategyConfig,
    load_config,
)
from oae.enums import SettlementStyle, StrategyType


CONFIG_PATH = Path("config/oae_v0_1_frozen.yaml")

TOP_LEVEL_FIELDS = (
    "version",
    "timezone",
    "decision_time",
    "instrument",
    "model",
    "health",
    "ood",
    "strategy",
    "candidate",
    "quotes",
    "execution",
    "fees",
    "edge",
    "bootstrap",
    "ambiguity",
)

CONFIG_MODEL_TYPES = (
    InstrumentConfig,
    ModelConfig,
    HealthConfig,
    OODConfig,
    StrategyConfig,
    CandidateConfig,
    QuotesConfig,
    ExecutionConfig,
    FeesConfig,
    EdgeConfig,
    BootstrapConfig,
    AmbiguityConfig,
    FrozenConfig,
)

EXPECTED_CANONICAL_CONFIG = {
    "version": "OAE-v0.1.0",
    "timezone": "America/New_York",
    "decision_time": time(13, 30, 0),
    "instrument": {
        "signal_underlying": "SPX",
        "trade_underlying": "XSP",
        "multiplier": 100,
        "settlement": SettlementStyle.PM,
    },
    "model": {
        "train_window": 756,
        "min_train": 504,
        "k": 80,
        "bandwidth_neighbor": 40,
        "recency_half_life": 252,
        "min_neff": 30.0,
        "feature_clip": 5.0,
    },
    "health": {
        "window": 126,
        "min_distribution_skill": 0.02,
    },
    "ood": {
        "percentile": 0.995,
    },
    "strategy": {
        "allowed": (
            StrategyType.BULL_CALL_DEBIT,
            StrategyType.BEAR_PUT_DEBIT,
        ),
        "spread_width": Decimal("1.0"),
        "max_trades_per_day": 1,
        "hold_to_settlement": True,
    },
    "candidate": {
        "max_moneyness_distance": 0.005,
    },
    "quotes": {
        "max_age_seconds": 2.0,
        "min_bid_size": 1,
        "min_ask_size": 1,
    },
    "execution": {
        "tick_size": Decimal("0.01"),
        "min_debit": Decimal("0.15"),
        "max_debit": Decimal("0.75"),
        "max_absolute_friction": Decimal("0.05"),
        "max_relative_friction": 0.25,
        "model": "CONSERVATIVE_NATURAL_ONE_LOT",
    },
    "fees": {
        "conservative_floor_usd": Decimal("3.00"),
    },
    "edge": {
        "min_ev_usd": Decimal("5.00"),
        "min_ev_over_max_loss": 0.10,
        "min_lcb_usd_exclusive": Decimal("0.00"),
        "min_lcb_over_max_loss": 0.02,
        "min_probability_profit": 0.40,
    },
    "bootstrap": {
        "draws": 1000,
        "base_seed": 20260813,
    },
    "ambiguity": {
        "max_score_difference": 0.01,
    },
}


@pytest.fixture
def config() -> FrozenConfig:
    return load_config(CONFIG_PATH)


def load_yaml_mapping() -> dict[str, object]:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_config_001_canonical_yaml_loads(config: FrozenConfig) -> None:
    assert isinstance(config, FrozenConfig)


def test_config_002_schema_is_complete_and_required() -> None:
    assert tuple(FrozenConfig.model_fields) == TOP_LEVEL_FIELDS
    for model_type in CONFIG_MODEL_TYPES:
        assert all(field.is_required() for field in model_type.model_fields.values())


def test_config_003_every_canonical_value_matches(config: FrozenConfig) -> None:
    assert config.model_dump(mode="python") == EXPECTED_CANONICAL_CONFIG


def test_config_004_extra_top_level_field_is_rejected() -> None:
    data = load_yaml_mapping()
    data["unexpected"] = True

    with pytest.raises(ValidationError):
        FrozenConfig.model_validate(data)


def test_config_005_extra_nested_field_is_rejected() -> None:
    data = load_yaml_mapping()
    data["model"]["unexpected"] = True

    with pytest.raises(ValidationError):
        FrozenConfig.model_validate(data)


def test_config_006_missing_top_level_section_is_rejected() -> None:
    data = load_yaml_mapping()
    del data["instrument"]

    with pytest.raises(ValidationError):
        FrozenConfig.model_validate(data)


def test_config_007_missing_nested_field_is_rejected() -> None:
    data = load_yaml_mapping()
    del data["model"]["k"]

    with pytest.raises(ValidationError):
        FrozenConfig.model_validate(data)


def test_config_008_clearly_invalid_type_is_rejected() -> None:
    data = load_yaml_mapping()
    data["model"]["k"] = "not-an-integer"

    with pytest.raises(ValidationError):
        FrozenConfig.model_validate(data)


def test_config_009_frozen_config_is_immutable(config: FrozenConfig) -> None:
    with pytest.raises(ValidationError):
        config.version = "changed"


def test_config_010_nested_models_are_immutable(config: FrozenConfig) -> None:
    with pytest.raises(ValidationError):
        config.model.k = 81


def test_config_011_decision_time_parses(config: FrozenConfig) -> None:
    assert config.decision_time == time(13, 30, 0)


def test_config_012_settlement_style_parses(config: FrozenConfig) -> None:
    assert config.instrument.settlement is SettlementStyle.PM


def test_config_013_allowed_strategies_parse_as_tuple(config: FrozenConfig) -> None:
    assert config.strategy.allowed == (
        StrategyType.BULL_CALL_DEBIT,
        StrategyType.BEAR_PUT_DEBIT,
    )
    assert isinstance(config.strategy.allowed, tuple)


def test_config_014_financial_fields_use_decimal(config: FrozenConfig) -> None:
    decimal_values = (
        config.execution.tick_size,
        config.execution.min_debit,
        config.execution.max_debit,
        config.execution.max_absolute_friction,
        config.fees.conservative_floor_usd,
        config.edge.min_ev_usd,
        config.edge.min_lcb_usd_exclusive,
    )
    assert all(isinstance(value, Decimal) for value in decimal_values)


def test_config_015_execution_model_is_frozen(config: FrozenConfig) -> None:
    assert config.execution.model == "CONSERVATIVE_NATURAL_ONE_LOT"


def test_config_016_lcb_threshold_is_numerically_zero(config: FrozenConfig) -> None:
    assert config.edge.min_lcb_usd_exclusive == Decimal("0.00")


def test_config_017_non_mapping_yaml_root_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "non_mapping.yaml"
    path.write_text("- not\n- a mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="root must be a mapping"):
        load_config(path)
