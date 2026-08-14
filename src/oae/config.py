import hashlib
import json
import math
from collections.abc import Mapping
from datetime import time
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from oae.enums import SettlementStyle, StrategyType


FROZEN_V0_1_CONFIG_SHA256 = (
    "ece897f1dd038743462322480aec20aba05b219ce7af8b2e4e38f7a013f11044"
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )


class InstrumentConfig(StrictModel):
    signal_underlying: str
    trade_underlying: str
    multiplier: int
    settlement: SettlementStyle


class ModelConfig(StrictModel):
    train_window: int
    min_train: int
    k: int
    bandwidth_neighbor: int
    recency_half_life: int
    min_neff: float
    feature_clip: float


class HealthConfig(StrictModel):
    window: int
    min_distribution_skill: float


class OODConfig(StrictModel):
    percentile: float


class StrategyConfig(StrictModel):
    allowed: tuple[StrategyType, ...]
    spread_width: Decimal
    max_trades_per_day: int
    hold_to_settlement: bool


class CandidateConfig(StrictModel):
    max_moneyness_distance: float


class QuotesConfig(StrictModel):
    max_age_seconds: float
    min_bid_size: int
    min_ask_size: int


class ExecutionConfig(StrictModel):
    tick_size: Decimal
    min_debit: Decimal
    max_debit: Decimal
    max_absolute_friction: Decimal
    max_relative_friction: float
    model: str


class FeesConfig(StrictModel):
    conservative_floor_usd: Decimal


class EdgeConfig(StrictModel):
    min_ev_usd: Decimal
    min_ev_over_max_loss: float
    min_lcb_usd_exclusive: Decimal
    min_lcb_over_max_loss: float
    min_probability_profit: float


class BootstrapConfig(StrictModel):
    draws: int
    base_seed: int


class AmbiguityConfig(StrictModel):
    max_score_difference: float


class FrozenConfig(StrictModel):
    version: str
    timezone: str
    decision_time: time

    instrument: InstrumentConfig
    model: ModelConfig
    health: HealthConfig
    ood: OODConfig
    strategy: StrategyConfig
    candidate: CandidateConfig
    quotes: QuotesConfig
    execution: ExecutionConfig
    fees: FeesConfig
    edge: EdgeConfig
    bootstrap: BootstrapConfig
    ambiguity: AmbiguityConfig


def _canonical_decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("non-finite Decimal values cannot be canonicalized")
    if value.is_zero():
        return "0"

    decimal_tuple = value.as_tuple()
    digits = list(decimal_tuple.digits)
    exponent = decimal_tuple.exponent

    while digits[-1] == 0:
        digits.pop()
        exponent += 1

    digit_text = "".join(str(digit) for digit in digits)
    if exponent >= 0:
        canonical = digit_text + ("0" * exponent)
    else:
        decimal_position = len(digit_text) + exponent
        if decimal_position > 0:
            canonical = (
                digit_text[:decimal_position]
                + "."
                + digit_text[decimal_position:]
            )
        else:
            canonical = "0." + ("0" * -decimal_position) + digit_text

    if decimal_tuple.sign == 1:
        canonical = "-" + canonical
    return canonical


def _normalize_for_config_hash(value: object) -> object:
    if isinstance(value, Mapping):
        normalized_mapping: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("config hash mappings require string keys")
            normalized_mapping[key] = _normalize_for_config_hash(item)
        return normalized_mapping
    if isinstance(value, (list, tuple)):
        return [_normalize_for_config_hash(item) for item in value]
    if isinstance(value, StrEnum):
        return {"$enum": value.value}
    if isinstance(value, time):
        return {"$time": value.isoformat(timespec="microseconds")}
    if isinstance(value, Decimal):
        return {"$decimal": _canonical_decimal_text(value)}
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite float values cannot be canonicalized")
        return {"$float": value.hex()}
    if isinstance(value, str):
        return value
    if value is None:
        return None
    raise TypeError(f"unsupported config hash type: {type(value).__name__}")


def _canonical_config_bytes(config: FrozenConfig) -> bytes:
    normalized = _normalize_for_config_hash(config.model_dump(mode="python"))
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_config_sha256(config: FrozenConfig) -> str:
    return hashlib.sha256(_canonical_config_bytes(config)).hexdigest()


def validate_frozen_v0_1(config: FrozenConfig) -> None:
    actual = compute_config_sha256(config)
    if actual != FROZEN_V0_1_CONFIG_SHA256:
        raise ValueError(
            "frozen OAE v0.1 config hash mismatch: "
            f"expected {FROZEN_V0_1_CONFIG_SHA256}, actual {actual}"
        )


def load_config(path: str | Path) -> FrozenConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("configuration root must be a mapping")
    return FrozenConfig.model_validate(data)
