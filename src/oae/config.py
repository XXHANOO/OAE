from collections.abc import Mapping
from datetime import time
from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from oae.enums import SettlementStyle, StrategyType


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


def load_config(path: str | Path) -> FrozenConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("configuration root must be a mapping")
    return FrozenConfig.model_validate(data)
