# Options Alpha Engine v0.1 — Implementation Specification

**Document ID:** OAE-IMPL-v0.1.0  
**System Version:** OAE-v0.1.0  
**Status:** FROZEN IMPLEMENTATION BASELINE  
**Development Model:** Human + ChatGPT Architecture Review + Codex Implementation  
**Core Principle:** One micro-stage → test → audit log → git commit → push → STOP → review.

This document is the original implementation baseline. Later governance-only corrections may supersede conflicting development-log mechanics through approved `AGENTS.md` and `CHANGE_CONTROL.md`, but they may not alter frozen financial mathematics, market-data semantics, timestamps, execution assumptions, or backtest semantics.

---

# 1. Repository Governance

## 1.1 Canonical Documentation Layout

The repository must converge toward:

```text
options-alpha-engine/
│
├── AGENTS.md
├── README.md
│
├── docs/
│   ├── specs/
│   │   ├── 00_OAE_v0.1_FROZEN_MATH_SPEC.md
│   │   ├── 01_OAE_v0.1_DATA_BACKTEST_SPEC.md
│   │   └── 02_OAE_v0.1_IMPLEMENTATION_SPEC.md
│   ├── CHANGE_CONTROL.md
│   └── devlog/
│       ├── INDEX.md
│       ├── S1.01_bootstrap.md
│       ├── S1.02_frozen_specs.md
│       └── ...
│
├── config/
│   ├── oae_v0_1_frozen.yaml
│   └── oae_v0_1_frozen.sha256
│
├── sql/
│   ├── 001_core.sql
│   ├── 002_research.sql
│   └── 003_audit.sql
│
├── src/
│   └── oae/
│
├── tests/
│
├── data/
│   ├── raw/
│   ├── normalized/
│   └── derived/
│
└── pyproject.toml
```

## 1.2 Frozen Mathematical Specification

The complete OAE v0.1 mathematical definition must be persisted in:

```text
docs/specs/00_OAE_v0.1_FROZEN_MATH_SPEC.md
```

It is canonical and must include:

- XSP 0DTE;
- SPX signal market;
- 13:30 ET decision;
- 1-point debit vertical;
- 11 features;
- 756-session rolling window;
- K = 80;
- bandwidth neighbor = 40;
- 252-session half-life;
- N_eff ≥ 30;
- historical analog distribution;
- OOD gate;
- CRPS;
- health calibration;
- candidate universe;
- D_exec;
- fees;
- payoff;
- EV;
- EV LCB;
- probability of profit;
- Edge thresholds;
- ambiguity rule;
- NO TRADE rules;
- settlement-only exit;
- walk-forward rules;
- acceptance criteria.

Codex must not change frozen model semantics.

A mathematical change requires:

```text
OAE-v0.1 -> OAE-v0.2
```

unless the change is purely formatting and semantically neutral.

---

# 2. Change-Control Protocol

`docs/CHANGE_CONTROL.md` must encode:

```text
FROZEN SPEC
    ↓
Implementation
    ↓
Tests
    ↓
Observed Problem
    ↓
Human Review
    ↓
Decision
    ├── implementation bug -> fix under v0.1
    └── mathematical rule change -> create v0.2
```

An Agent must never silently alter mathematics because a test/backtest result is inconvenient.

Forbidden without explicit approval:

```text
change k because results look bad
change threshold because signals are too few
change feature definition
change strike universe
change execution assumptions
change fee assumptions
change timestamps
change model-health ranges
```

---

# 3. AGENTS.md Contract

Root `AGENTS.md` should remain compact and enforce approximately:

```text
# OAE Agent Contract

Before any work:

1. Read:
   docs/specs/00_OAE_v0.1_FROZEN_MATH_SPEC.md
   docs/specs/01_OAE_v0.1_DATA_BACKTEST_SPEC.md
   docs/specs/02_OAE_v0.1_IMPLEMENTATION_SPEC.md
   docs/CHANGE_CONTROL.md

2. Work on ONE micro-stage only.

3. Do not alter frozen mathematical rules.

4. Do not introduce additional features, models, dependencies,
   optimizations, or refactors unless required by the current stage.

5. Write tests before or together with implementation.

6. Run the exact required tests before completion.

7. After implementation:
   - write the stage development log;
   - commit code;
   - push;
   - commit the audit/report record referencing the code commit;
   - push again.

8. STOP after the current stage.
   Never automatically start the next stage.

9. Report:
   - files changed;
   - tests executed;
   - test results;
   - known limitations;
   - deviations from spec;
   - code commit SHA;
   - audit/report reference.

Any conflict with the frozen specification must stop development
and be escalated for human review.
```

Governance mechanics may later be refined through approved governance amendments, provided no frozen financial/data semantics are changed.

---

# 4. Git Development Protocol

Development branch:

```text
dev/oae-v0.1
```

Do not develop directly on:

```text
main
```

Each micro-stage uses separate implementation and report/audit history.

Baseline pattern:

### Commit A — Implementation

Example:

```text
oae-v0.1 S1.03: add frozen config validation
```

Push immediately.

### Commit B — Stage Report / Audit Record

Example:

```text
docs S1.03: audit frozen config implementation
```

The report records Commit A SHA.

Push immediately.

Conceptual sequence:

```text
implementation
→ test
→ commit A
→ push
→ development log
→ commit B
→ push
→ STOP
```

Do not squash research-stage development history.

At the end of each Sprint:

```text
oae-v0.1-sprint1
oae-v0.1-sprint2
oae-v0.1-sprint3
```

---

# 5. Development Log Contract

One stage = one report.

Example:

```text
docs/devlog/S2.04_nbbo_asof.md
```

Original baseline structure:

```markdown
# Development Log — S2.04

## Stage
S2.04 — NBBO As-Of Selection

## Specification References
- Frozen Math Spec:
- Data/Backtest Spec:
- Implementation Spec:

## Objective
Exact task assigned to the agent.

## Base State
Branch:
Base commit:
Config hash:
Spec hash:

## Changes Made
Detailed description.

## Files Added
-

## Files Modified
-

## Implementation Decisions
-

## Tests Added
-

## Tests Executed
Command:

Result:

## Test Evidence
Passed:
Failed:
Skipped:

## Specification Compliance
[ ] No mathematical rules changed
[ ] No future information introduced
[ ] No unrequested dependencies
[ ] Scope limited to assigned stage

## Deviations
NONE

or:

Detailed deviation requiring review.

## Known Limitations
-

## Risks / Questions for Review
-

## Code Commit
SHA:

## Agent Recommendation for Next Stage
-

## Human / ChatGPT Audit
PENDING
```

The original `INDEX.md` idea included:

```text
Stage
Status
Code SHA
Audit SHA
Review status
```

A later approved governance repair may replace the self-referential Audit-SHA mechanism with a report-path/review-status mechanism. Such a governance repair supersedes only the reporting mechanic, not implementation semantics.

---

# 6. Python Architecture

Target:

```text
Python 3.12
```

Primary dependencies:

```text
pydantic 2.x
duckdb
numpy
scipy
pyarrow
PyYAML
pytest
```

No ML framework.

No pandas requirement in core model code.

No sklearn requirement in v0.1.

Numerical model computation:

```text
numpy.float64
```

Persistent market prices:

```text
Decimal
```

Persistent timestamps:

```text
timezone-aware datetime
```

---

# 7. Pydantic vs Dataclass Policy

Use **Pydantic** at system boundaries:

- configuration;
- database DTOs;
- vendor adapter outputs;
- persisted decisions;
- manifests.

Use immutable Python **dataclasses** internally:

- feature vectors;
- KNN neighbors;
- forecast scenarios;
- strategy candidates;
- computed metrics.

Boundary models use a strict frozen base:

```python
class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )
```

Unexpected fields must fail validation.

---

# 8. Core Enums

```python
from enum import StrEnum


class OptionType(StrEnum):
    CALL = "C"
    PUT = "P"


class SettlementStyle(StrEnum):
    AM = "AM"
    PM = "PM"


class ExerciseStyle(StrEnum):
    EUROPEAN = "EUROPEAN"
    AMERICAN = "AMERICAN"


class StrategyType(StrEnum):
    BULL_CALL_DEBIT = "BULL_CALL_DEBIT"
    BEAR_PUT_DEBIT = "BEAR_PUT_DEBIT"


class DecisionType(StrEnum):
    TRADE = "TRADE"
    NO_TRADE = "NO_TRADE"


class QualityStatus(StrEnum):
    VALID = "VALID"
    STALE = "STALE"
    CROSSED = "CROSSED"
    LOCKED = "LOCKED"
    ZERO_BID = "ZERO_BID"
    ZERO_SIZE = "ZERO_SIZE"
    MISSING = "MISSING"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    DUPLICATE = "DUPLICATE"
    HALTED = "HALTED"
    UNKNOWN = "UNKNOWN"
```

---

# 9. Frozen Configuration Schema

```python
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


class ExecutionConfig(StrictModel):
    tick_size: Decimal
    min_debit: Decimal
    max_debit: Decimal
    max_absolute_friction: Decimal
    max_relative_friction: float


class EdgeConfig(StrictModel):
    min_ev_usd: Decimal
    min_ev_over_max_loss: float
    min_lcb_over_max_loss: float
    min_probability_profit: float


class FrozenConfig(StrictModel):
    version: str
    timezone: str
    decision_time: time
    model: ModelConfig
    health: HealthConfig
    execution: ExecutionConfig
    edge: EdgeConfig
```

A separate function must enforce exact frozen values:

```python
def validate_frozen_v0_1(config: FrozenConfig) -> None:
    ...
```

Normalized config hashing:

```python
def compute_config_sha256(config: FrozenConfig) -> str:
    ...
```

CI invariant:

```text
computed SHA256 == config/oae_v0_1_frozen.sha256
```

---

# 10. Market Data Pydantic Schemas

## IndexBar1m

```python
class IndexBar1mRecord(StrictModel):
    symbol: str
    session_date_et: date
    bar_start_ts_utc: datetime
    bar_end_ts_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    observation_count: int
    source: str
    raw_file_id: str
```

## OptionContract

```python
class OptionContractRecord(StrictModel):
    contract_id: str
    vendor_symbol: str
    product: str
    root_symbol: str
    underlying: str
    option_type: OptionType
    strike: Decimal
    expiration_date: date
    settlement_style: SettlementStyle
    exercise_style: ExerciseStyle
    multiplier: int
    series_type: str | None
```

## NBBO

Raw record parsing must not reject crossed/locked values before the quality engine classifies them.

```python
class OptionQuoteRecord(StrictModel):
    contract_id: str
    quote_ts_utc: datetime
    session_date_et: date
    bid_px: Decimal
    ask_px: Decimal
    bid_size: int
    ask_size: int
    bid_exchange: str | None
    ask_exchange: str | None
    sequence_no: int | None
    source: str
    raw_file_id: str
```

## Settlement

```python
class SettlementRecord(StrictModel):
    product: str
    expiration_date: date
    settlement_style: SettlementStyle
    settlement_value: Decimal
    effective_ts_utc: datetime
    published_ts_utc: datetime | None
    source: str
```

---

# 11. Internal Immutable Dataclasses

```python
@dataclass(frozen=True, slots=True)
class FeatureVector:
    x1: float
    x2: float
    x3: float
    x4: float
    x5: float
    x6: float
    x7: float
    x8: float
    x9: float
    x10: float
    x11: float


@dataclass(frozen=True, slots=True)
class Neighbor:
    session_date: date
    distance: float
    terminal_return: float
    age_sessions: int
    weight: float


@dataclass(frozen=True, slots=True)
class ForecastScenario:
    historical_session: date
    terminal_log_return: float
    weight: float
    projected_settlement: float


@dataclass(frozen=True, slots=True)
class Candidate:
    strategy: StrategyType
    long_contract_id: str
    short_contract_id: str
    long_strike: float
    short_strike: float


@dataclass(frozen=True, slots=True)
class CandidateMetrics:
    d_mid: float
    d_natural: float
    d_exec: float
    friction: float
    fee: float
    expected_payoff: float
    ev: float
    max_loss: float
    max_profit: float
    ev_over_max_loss: float
    ev_lcb: float
    lcb_over_max_loss: float
    probability_profit: float
    robust_score: float
```

---

# 12. Module API — Data Layer

```python
# data/asof.py

def select_asof_quote(
    quotes: Sequence[OptionQuoteRecord],
    decision_ts: datetime,
) -> OptionQuoteRecord | None:
    """Return latest quote where quote_ts <= decision_ts."""


def quote_age_seconds(
    quote_ts: datetime,
    decision_ts: datetime,
) -> float:
    ...


def classify_quote_quality(
    quote: OptionQuoteRecord,
    decision_ts: datetime,
    max_age_seconds: float,
) -> QualityStatus:
    ...
```

Invariant:

```text
quote_ts > decision_ts
```

must never be returned.

---

# 13. Feature Engine API

```python
def compute_price_features(
    bars: Sequence[IndexBar1mRecord],
    previous_close: float,
    decision_ts: datetime,
) -> tuple[float, ...]:
    """Return x1-x8."""


def compute_option_features(
    spx_spot: float,
    same_day_chain: OptionChainSnapshot,
    next_expiry_chain: OptionChainSnapshot,
    decision_ts: datetime,
) -> tuple[float, float, float]:
    """Return x9-x11."""


def compute_feature_vector(
    session: SessionState,
) -> FeatureVector:
    ...
```

Feature calculations should be pure.

Database retrieval occurs before the mathematical function call.

---

# 14. Label API

```python
def compute_terminal_label(
    decision_xsp_reference: float,
    official_xsp_settlement: float,
) -> float:
    return np.log(
        official_xsp_settlement /
        decision_xsp_reference
    )
```

---

# 15. Scaling API

```python
@dataclass(frozen=True)
class RobustScalerState:
    median: np.ndarray
    mad: np.ndarray
    denominator: np.ndarray


def fit_robust_scaler(
    X: np.ndarray,
) -> RobustScalerState:
    ...


def transform_features(
    X: np.ndarray,
    scaler: RobustScalerState,
    clip: float = 5.0,
) -> np.ndarray:
    ...
```

---

# 16. KNN API

```python
def euclidean_distances(
    query: np.ndarray,
    training: np.ndarray,
) -> np.ndarray:
    ...


def nearest_neighbor_indices(
    distances: np.ndarray,
    k: int,
) -> np.ndarray:
    ...


def compute_neighbor_weights(
    distances: np.ndarray,
    ages: np.ndarray,
    bandwidth_neighbor: int,
    recency_half_life: float,
) -> np.ndarray:
    ...


def effective_sample_size(
    weights: np.ndarray,
) -> float:
    return 1.0 / np.sum(weights ** 2)
```

---

# 17. Distribution API

```python
def build_scenarios(
    current_xsp: float,
    terminal_returns: np.ndarray,
    weights: np.ndarray,
    historical_dates: Sequence[date],
) -> tuple[ForecastScenario, ...]:
    ...


def weighted_quantile(
    values: np.ndarray,
    weights: np.ndarray,
    q: float,
) -> float:
    ...
```

---

# 18. CRPS / Health API

```python
def weighted_empirical_crps(
    outcomes: np.ndarray,
    weights: np.ndarray,
    realized: float,
) -> float:
    ...


def distribution_skill(
    model_crps: float,
    baseline_crps: float,
) -> float:
    ...


def quantile_coverage(
    forecasts: Sequence[float],
    realized: Sequence[float],
) -> float:
    ...


def evaluate_model_health(
    history: Sequence[ForecastEvaluation],
    config: FrozenConfig,
) -> ModelHealthResult:
    ...
```

---

# 19. OOD API

```python
def training_d80_distribution(
    standardized_training: np.ndarray,
    k: int = 80,
) -> np.ndarray:
    ...


def compute_ood_threshold(
    d80_values: np.ndarray,
    percentile: float = 0.995,
) -> float:
    ...


def evaluate_ood(
    today_d80: float,
    threshold: float,
) -> bool:
    return today_d80 <= threshold
```

Leave-one-out must be used for training observations.

---

# 20. Candidate Generator API

```python
def generate_xsp_candidates(
    contracts: Sequence[OptionContractRecord],
    xsp_reference_px: float,
    max_moneyness_distance: float,
    spread_width: float = 1.0,
) -> tuple[Candidate, ...]:
    ...
```

The generator may create only:

```text
BULL_CALL_DEBIT
BEAR_PUT_DEBIT
```

---

# 21. Execution Pricing API

```python
def package_mid(
    long_bid: float,
    long_ask: float,
    short_bid: float,
    short_ask: float,
) -> float:
    ...


def natural_debit(
    long_ask: float,
    short_bid: float,
) -> float:
    return long_ask - short_bid


def round_up_to_tick(
    value: float,
    tick: float,
) -> float:
    ...


def executable_debit(
    d_natural: float,
    tick: float = 0.01,
) -> float:
    ...
```

Invariant:

\[
D_{exec}\ge D_{natural}
\]

---

# 22. Payoff API

```python
def bull_call_payoff_points(
    settlement: np.ndarray,
    long_strike: float,
) -> np.ndarray:
    return np.minimum(
        np.maximum(settlement - long_strike, 0.0),
        1.0,
    )


def bear_put_payoff_points(
    settlement: np.ndarray,
    long_strike: float,
) -> np.ndarray:
    return np.minimum(
        np.maximum(long_strike - settlement, 0.0),
        1.0,
    )
```

Invariant:

\[
0\le payoff\le1
\]

---

# 23. EV API

```python
def expected_payoff_points(
    payoff: np.ndarray,
    weights: np.ndarray,
) -> float:
    ...


def expected_value_usd(
    expected_payoff: float,
    debit: float,
    fee: float,
    multiplier: int = 100,
) -> float:
    ...


def probability_of_profit(
    candidate: Candidate,
    settlements: np.ndarray,
    weights: np.ndarray,
    debit: float,
    fee: float,
) -> float:
    ...


def calculate_candidate_metrics(
    candidate: Candidate,
    scenarios: Sequence[ForecastScenario],
    quotes: CandidateQuoteState,
    fee: float,
    config: FrozenConfig,
) -> CandidateMetrics:
    ...
```

---

# 24. Dirichlet LCB API

```python
def candidate_ev_lcb(
    payoff_points: np.ndarray,
    weights: np.ndarray,
    neff: float,
    debit: float,
    fee: float,
    draws: int,
    seed: int,
) -> float:
    ...
```

Frozen production value:

```text
draws = 1000
```

Seed must be deterministic.

---

# 25. Decision Engine API

```python
def passes_edge_gate(
    metrics: CandidateMetrics,
    config: FrozenConfig,
) -> bool:
    ...


def select_best_candidate(
    candidates: Sequence[EvaluatedCandidate],
    ambiguity_threshold: float,
) -> DecisionResult:
    ...
```

`DecisionResult` contains:

```text
TRADE / NO_TRADE
candidate
primary_reason_code
all_reason_codes
```

---

# 26. Backtest API

```python
class WalkForwardBacktestEngine:

    def run_session(
        self,
        session_date: date,
    ) -> SessionResult:
        ...

    def run(
        self,
        start_date: date,
        end_date: date,
    ) -> BacktestResult:
        ...
```

`run_session()` is the fundamental integration boundary.

A full replay must be equivalent to sequential session execution.

---

# 27. DuckDB Schema Strategy

Use four schemas:

```sql
CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS research;
CREATE SCHEMA IF NOT EXISTS audit;
```

---

# 28. Core DuckDB DDL

## raw_file_manifest

```sql
CREATE TABLE meta.raw_file_manifest (
    raw_file_id VARCHAR PRIMARY KEY,
    source VARCHAR NOT NULL,
    source_file_name VARCHAR NOT NULL,
    ingested_at_utc TIMESTAMPTZ NOT NULL,
    sha256 VARCHAR NOT NULL,
    schema_version VARCHAR NOT NULL,
    min_event_ts TIMESTAMPTZ,
    max_event_ts TIMESTAMPTZ,
    row_count BIGINT NOT NULL
);
```

## trading_sessions

```sql
CREATE TABLE core.trading_sessions (
    session_date_et DATE PRIMARY KEY,
    session_seq INTEGER NOT NULL,
    open_ts_utc TIMESTAMPTZ NOT NULL,
    regular_close_ts_utc TIMESTAMPTZ NOT NULL,
    is_trading_day BOOLEAN NOT NULL,
    is_full_session BOOLEAN NOT NULL,
    is_half_day BOOLEAN NOT NULL,
    xsp_0dte_exists BOOLEAN NOT NULL
);
```

## index_bars_1m

```sql
CREATE TABLE core.index_bars_1m (
    symbol VARCHAR NOT NULL,
    session_date_et DATE NOT NULL,
    bar_start_ts_utc TIMESTAMPTZ NOT NULL,
    bar_end_ts_utc TIMESTAMPTZ NOT NULL,
    open DECIMAL(18,6) NOT NULL,
    high DECIMAL(18,6) NOT NULL,
    low DECIMAL(18,6) NOT NULL,
    close DECIMAL(18,6) NOT NULL,
    observation_count INTEGER NOT NULL,
    source VARCHAR NOT NULL,
    raw_file_id VARCHAR NOT NULL,

    PRIMARY KEY(symbol, bar_end_ts_utc)
);
```

## option_contracts

```sql
CREATE TABLE core.option_contracts (
    contract_id VARCHAR PRIMARY KEY,
    vendor_symbol VARCHAR NOT NULL,
    product VARCHAR NOT NULL,
    root_symbol VARCHAR NOT NULL,
    underlying VARCHAR NOT NULL,
    option_type VARCHAR NOT NULL CHECK(option_type IN ('C','P')),
    strike DECIMAL(18,4) NOT NULL,
    expiration_date DATE NOT NULL,
    settlement_style VARCHAR NOT NULL CHECK(settlement_style IN ('AM','PM')),
    exercise_style VARCHAR NOT NULL,
    multiplier INTEGER NOT NULL,
    series_type VARCHAR
);
```

## option_nbbo

```sql
CREATE TABLE core.option_nbbo (
    contract_id VARCHAR NOT NULL,
    quote_ts_utc TIMESTAMPTZ NOT NULL,
    session_date_et DATE NOT NULL,
    bid_px DECIMAL(18,6) NOT NULL,
    ask_px DECIMAL(18,6) NOT NULL,
    bid_size INTEGER NOT NULL,
    ask_size INTEGER NOT NULL,
    bid_exchange VARCHAR,
    ask_exchange VARCHAR,
    sequence_no BIGINT,
    source VARCHAR NOT NULL,
    raw_file_id VARCHAR NOT NULL
);
```

## option_settlements

```sql
CREATE TABLE core.option_settlements (
    product VARCHAR NOT NULL,
    expiration_date DATE NOT NULL,
    settlement_style VARCHAR NOT NULL,
    settlement_value DECIMAL(18,6) NOT NULL,
    effective_ts_utc TIMESTAMPTZ NOT NULL,
    published_ts_utc TIMESTAMPTZ,
    source VARCHAR NOT NULL,

    PRIMARY KEY(product, expiration_date, settlement_style)
);
```

---

# 29. Research DDL

## feature_snapshots

```sql
CREATE TABLE research.feature_snapshots (
    session_date_et DATE PRIMARY KEY,
    feature_version VARCHAR NOT NULL,
    decision_ts_utc TIMESTAMPTZ NOT NULL,

    x1 DOUBLE NOT NULL,
    x2 DOUBLE NOT NULL,
    x3 DOUBLE NOT NULL,
    x4 DOUBLE NOT NULL,
    x5 DOUBLE NOT NULL,
    x6 DOUBLE NOT NULL,
    x7 DOUBLE NOT NULL,
    x8 DOUBLE NOT NULL,
    x9 DOUBLE NOT NULL,
    x10 DOUBLE NOT NULL,
    x11 DOUBLE NOT NULL,

    feature_valid BOOLEAN NOT NULL,
    invalid_reason VARCHAR
);
```

## model_samples

```sql
CREATE TABLE research.model_samples (
    session_date_et DATE PRIMARY KEY,
    decision_spx_px DOUBLE NOT NULL,
    decision_xsp_reference_px DOUBLE NOT NULL,
    settlement_xsp DOUBLE,
    terminal_log_return DOUBLE,
    label_available_from TIMESTAMPTZ
);
```

## forecast_runs

```sql
CREATE TABLE research.forecast_runs (
    forecast_id VARCHAR PRIMARY KEY,
    session_date_et DATE NOT NULL,
    model_version VARCHAR NOT NULL,

    n_train INTEGER NOT NULL,
    neff DOUBLE,
    d40 DOUBLE,
    d80_today DOUBLE,
    ood_threshold DOUBLE,

    q10 DOUBLE,
    q25 DOUBLE,
    q50 DOUBLE,
    q75 DOUBLE,
    q90 DOUBLE,

    distribution_skill DOUBLE,

    ood_pass BOOLEAN,
    health_pass BOOLEAN,

    config_sha256 VARCHAR NOT NULL,
    data_snapshot_sha256 VARCHAR,
    code_commit VARCHAR
);
```

## forecast_scenarios

```sql
CREATE TABLE research.forecast_scenarios (
    forecast_id VARCHAR NOT NULL,
    scenario_rank INTEGER NOT NULL,
    historical_session DATE NOT NULL,
    terminal_log_return DOUBLE NOT NULL,
    scenario_weight DOUBLE NOT NULL,
    projected_xsp_settlement DOUBLE NOT NULL,

    PRIMARY KEY(forecast_id, scenario_rank)
);
```

## forecast_neighbors

```sql
CREATE TABLE research.forecast_neighbors (
    forecast_id VARCHAR NOT NULL,
    neighbor_rank INTEGER NOT NULL,
    neighbor_session_date DATE NOT NULL,
    distance DOUBLE NOT NULL,
    terminal_return DOUBLE NOT NULL,
    age_sessions INTEGER NOT NULL,
    normalized_weight DOUBLE NOT NULL,

    PRIMARY KEY(forecast_id, neighbor_rank)
);
```

## option_candidates

```sql
CREATE TABLE research.option_candidates (
    candidate_id VARCHAR PRIMARY KEY,
    forecast_id VARCHAR NOT NULL,
    strategy_type VARCHAR NOT NULL,

    long_contract_id VARCHAR NOT NULL,
    short_contract_id VARCHAR NOT NULL,

    long_strike DOUBLE NOT NULL,
    short_strike DOUBLE NOT NULL,

    d_mid DOUBLE,
    d_natural DOUBLE,
    d_exec DOUBLE,
    spread_friction DOUBLE,

    fee DOUBLE,
    max_loss DOUBLE,
    max_profit DOUBLE,

    expected_payoff DOUBLE,
    ev DOUBLE,
    ev_over_max_loss DOUBLE,
    ev_lcb DOUBLE,
    lcb_over_max_loss DOUBLE,
    probability_profit DOUBLE,
    robust_score DOUBLE,

    liquidity_pass BOOLEAN,
    edge_pass BOOLEAN
);
```

## daily_decisions

```sql
CREATE TABLE research.daily_decisions (
    decision_id VARCHAR PRIMARY KEY,
    session_date_et DATE NOT NULL,
    decision_ts_utc TIMESTAMPTZ NOT NULL,

    model_version VARCHAR NOT NULL,
    forecast_id VARCHAR,

    decision VARCHAR NOT NULL
        CHECK(decision IN ('TRADE','NO_TRADE')),

    best_candidate_id VARCHAR,
    primary_reason_code VARCHAR NOT NULL,

    expected_ev DOUBLE,
    expected_ev_lcb DOUBLE,
    max_loss DOUBLE,
    robust_score DOUBLE,

    run_id VARCHAR NOT NULL
);
```

## trade_results

```sql
CREATE TABLE research.trade_results (
    decision_id VARCHAR PRIMARY KEY,
    settlement_value DOUBLE NOT NULL,
    gross_payoff DOUBLE NOT NULL,
    entry_cost DOUBLE NOT NULL,
    fee_total DOUBLE NOT NULL,
    net_pnl DOUBLE NOT NULL,
    return_on_max_loss DOUBLE NOT NULL,
    won BOOLEAN NOT NULL
);
```

---

# 30. Audit DDL

```sql
CREATE TABLE audit.backtest_runs (
    run_id VARCHAR PRIMARY KEY,

    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,

    model_version VARCHAR NOT NULL,
    feature_version VARCHAR NOT NULL,
    execution_version VARCHAR NOT NULL,

    git_commit VARCHAR NOT NULL,
    config_sha256 VARCHAR NOT NULL,
    data_snapshot_sha256 VARCHAR NOT NULL,

    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    random_seed BIGINT NOT NULL,

    status VARCHAR NOT NULL
);
```

---

# 31. Unit-Test Contract

Tests are specification enforcement.

## TIME-001

```text
decision = 13:30:00.000
quote = 13:29:59.999
```

Expected: accepted.

## TIME-002

```text
quote = 13:30:00.001
```

Expected: rejected.

## TIME-003

```text
bar = 13:30-13:31
```

Expected: never used.

## QUOTE-001

```text
age = 2.000 seconds
```

Expected: VALID.

## QUOTE-002

```text
age = 2.001 seconds
```

Expected: STALE.

## QUOTE-003

```text
ask < bid
```

Expected: CROSSED.

## FEATURE-001

Hand-computed fixture verifies x1–x4.

## FEATURE-002

Hand-computed minute-return fixture verifies x5–x8.

## FEATURE-003

Synthetic option chain verifies ATM tie chooses lower strike.

## FEATURE-004

Synthetic option chains verify x9–x11.

## SCALE-001

Median and MAD match hand calculation.

## SCALE-002

Transformed values clip exactly to ±5.

## KNN-001

Neighbor ordering matches known synthetic distances.

## KNN-002

Exactly 80 neighbors in production config.

## KNN-003

\[
\sum w_i=1
\]

with tolerance:

\[
10^{-12}
\]

## KNN-004

\[
1\le N_{eff}\le80
\]

## DIST-001

\[
X^*=X_t e^Y
\]

## OOD-001

Leave-one-out excludes the observation itself.

## CRPS-001

Known empirical distribution matches hand-computed CRPS.

## STRATEGY-001

Only the two frozen verticals are generated.

## STRATEGY-002

Spread width exactly:

\[
1.0
\]

## EXEC-001

\[
D_{natural}=Ask_L-Bid_S
\]

## EXEC-002

\[
D_{exec}\ge D_{natural}
\]

## EXEC-003

D_exec follows the 0.01 net-tick rule.

## PAYOFF-001

Bull spread:

\[
0\le\pi\le1
\]

## PAYOFF-002

Bear spread:

\[
0\le\pi\le1
\]

## EV-001

Known synthetic scenarios produce exact EV.

## EV-002

MaxLoss identity verified.

## EV-003

MaxProfit identity verified.

## LCB-001

Same session + same seed yields identical LCB.

## EDGE-001

Every threshold boundary is independently tested.

## DECISION-001

Score difference:

```text
0.0099
```

Expected:

```text
NO_TRADE_AMBIGUOUS
```

## DECISION-002

Difference:

```text
0.0100
```

must follow the strict frozen inequality.

## LEAK-001

Current settlement injected before decision → hard failure.

## LEAK-002

Future label injected into training → hard failure.

## LEAK-003

Future quote injected → hard failure.

## DET-001

Identical fixture run twice → identical decision output hash.

---

# 32. Test Directory

```text
tests/
├── unit/
│   ├── test_config.py
│   ├── test_time.py
│   ├── test_quotes.py
│   ├── test_features_price.py
│   ├── test_features_options.py
│   ├── test_scaler.py
│   ├── test_knn.py
│   ├── test_distribution.py
│   ├── test_ood.py
│   ├── test_crps.py
│   ├── test_candidates.py
│   ├── test_execution.py
│   ├── test_payoff.py
│   ├── test_ev.py
│   └── test_decision.py
│
├── leakage/
│   ├── test_future_quotes.py
│   ├── test_future_bars.py
│   ├── test_future_labels.py
│   └── test_future_settlement.py
│
├── integration/
│   ├── test_single_session.py
│   └── test_walkforward_small.py
│
└── regression/
    └── test_golden_run.py
```

---

# 33. Micro-Stage Rule

A micro-stage should normally modify approximately:

```text
1–3 implementation files
+
1–2 test files
+
1 devlog
```

If the Agent estimates that a stage needs broad repository-wide changes:

```text
STOP
```

and request decomposition.

Do not assign:

> Implement the backtest system.

Instead assign:

> Implement one pure function plus tests.

---

# 34. Sprint 1 — Governance + Skeleton

Goal:

\[
\boxed{\text{Create a trustworthy empty system}}
\]

No market calculations yet.

## S1.01 — Repository Bootstrap

Only:

```text
README.md
AGENTS.md
docs/
src/oae/__init__.py
tests/
.gitignore
```

Acceptance:

```text
python imports oae
pytest starts successfully
```

STOP.

## S1.02 — Frozen Specification Files

Create:

```text
00_FROZEN_MATH_SPEC.md
01_DATA_BACKTEST_SPEC.md
02_IMPLEMENTATION_SPEC.md
CHANGE_CONTROL.md
```

No model code.

Audit against approved source material.

STOP.

## S1.03 — Python Project Configuration

Create:

```text
pyproject.toml
```

Install minimal dependencies.

Run:

```text
python -m pytest
```

No model code.

STOP.

## S1.04 — Frozen YAML Config

Create:

```text
config/oae_v0_1_frozen.yaml
```

and Pydantic config schema.

Tests:

```text
extra field rejected
missing field rejected
wrong type rejected
```

STOP.

## S1.05 — Config Hash Protection

Implement:

```python
compute_config_sha256()
validate_frozen_v0_1()
```

Create:

```text
oae_v0_1_frozen.sha256
```

Test mutation causes failure.

STOP.

## S1.06 — Domain Enums

Implement enums only.

Tests verify frozen values.

STOP.

## S1.07 — DuckDB Connection

Implement:

```python
open_database(path)
```

No schema yet.

Test temporary DB open/create/close.

STOP.

## S1.08 — Core SQL Migration

Implement:

```text
001_core.sql
```

Test all core tables exist.

STOP.

## S1.09 — Research SQL Migration

Implement:

```text
002_research.sql
```

Test tables.

STOP.

## S1.10 — Audit SQL Migration

Implement:

```text
003_audit.sql
```

STOP.

## S1.11 — Timestamp Utilities

Implement timezone-aware utilities only.

Tests:

```text
DST
ET -> UTC
UTC -> ET
decision timestamp
```

STOP.

## S1.12 — Sprint 1 Regression Check

Run entire test suite.

Generate:

```text
docs/devlog/SPRINT1_AUDIT.md
```

Tag:

```text
oae-v0.1-sprint1
```

No Sprint 2 until Human + ChatGPT review.

---

# 35. Sprint 2 — Point-in-Time Data + Features

Goal:

\[
\boxed{\text{Build correct historical state at 13:30}}
\]

## S2.01
Implement `IndexBar1mRecord`.
STOP.

## S2.02
Implement `OptionContractRecord`.
STOP.

## S2.03
Implement `OptionQuoteRecord`.
STOP.

## S2.04
Implement quote-quality classification.
STOP.

## S2.05
Implement `select_asof_quote()`.
Special leakage review.
STOP.

## S2.06
Implement trading-session schema/API.
STOP.

## S2.07
Implement session SPX state:

```text
previous close
open
decision price
high
low
```

STOP.

## S2.08
Implement minute returns.
STOP.

## S2.09
Implement x1–x4.
STOP.

## S2.10
Implement x5–x8.
STOP.

## S2.11
Implement option-chain snapshot structure.
STOP.

## S2.12
Implement ATM-strike selector.
STOP.

## S2.13
Implement x9.
STOP.

## S2.14
Implement x10.
STOP.

## S2.15
Implement x11.
STOP.

## S2.16
Implement official settlement record.
STOP.

## S2.17
Implement terminal label.
STOP.

## S2.18
Implement label-availability rule.
STOP.

## S2.19
Implement complete leakage-test suite.
STOP.

## S2.20
Synthetic single-session feature test.

Input:

```text
synthetic bars
synthetic chains
synthetic settlement
```

Output:

```text
FeatureVector
terminal label
```

STOP.

## S2.21 — Sprint 2 Audit

Full tests.

Tag:

```text
oae-v0.1-sprint2
```

Human + ChatGPT review required before Sprint 3.

---

# 36. Sprint 3 — Model + Strategy + Walk-Forward

Goal:

\[
\boxed{\text{Reach deterministic end-to-end baseline}}
\]

## S3.01
Robust median/MAD scaler.
STOP.

## S3.02
Feature clipping.
STOP.

## S3.03
Euclidean distance.
STOP.

## S3.04
Nearest-neighbor ordering.
STOP.

## S3.05
Kernel similarity weight.
STOP.

## S3.06
Recency weight.
STOP.

## S3.07
Final normalized weight.
STOP.

## S3.08
N_eff.
STOP.

## S3.09
Projected settlement scenarios.
STOP.

## S3.10
Weighted quantiles.
STOP.

## S3.11
Leave-one-out d80.
STOP.

## S3.12
OOD threshold.
STOP.

## S3.13
Weighted CRPS.
STOP.

## S3.14
Unconditional baseline CRPS.
STOP.

## S3.15
Distribution skill.
STOP.

## S3.16
Quantile calibration.
STOP.

## S3.17
Model Health Gate.
STOP.

## S3.18
XSP candidate generation.
STOP.

## S3.19
Quote liquidity gate.
STOP.

## S3.20
Natural price.
STOP.

## S3.21
Executable debit rounding.
STOP.

## S3.22
Bull spread payoff.
STOP.

## S3.23
Bear spread payoff.
STOP.

## S3.24
Expected payoff.
STOP.

## S3.25
EV + MaxLoss + MaxProfit.
STOP.

## S3.26
Probability of Profit.
STOP.

## S3.27
Deterministic Dirichlet sampler.
STOP.

## S3.28
EV LCB.
STOP.

## S3.29
Edge Gate.
STOP.

## S3.30
RobustScore ranking.
STOP.

## S3.31
Call/Put ambiguity rule.
STOP.

## S3.32
NO TRADE reason-code priority.
STOP.

## S3.33
Simulated fill.
STOP.

## S3.34
Settlement P&L.
STOP.

## S3.35
One-session end-to-end engine.
STOP.

## S3.36
Two-session anti-leakage walk-forward.
STOP.

## S3.37
Ten-session synthetic walk-forward.
STOP.

## S3.38
Golden deterministic regression run.

Run twice.

Require identical output hash.

STOP.

## S3.39
Backtest manifest.
STOP.

## S3.40
Backtest CLI.

Example:

```text
oae backtest \
  --start 2024-01-01 \
  --end 2026-01-01 \
  --config config/oae_v0_1_frozen.yaml
```

STOP.

## S3.41 — Sprint 3 Audit

Full test suite.

Generate:

```text
SPRINT3_AUDIT.md
```

Tag:

```text
oae-v0.1-sprint3
```

At this point the engine exists.

Historical-data validation starts afterward.

---

# 37. Agent Completion Report

Every Agent turn ends with a concise completion status such as:

```text
STAGE: Sx.xx
STATUS: COMPLETE / BLOCKED

FILES CHANGED:
-

TESTS RUN:
-

RESULT:
X passed
Y failed
Z skipped

SPEC DEVIATIONS:
NONE

CODE COMMIT:
<sha>

AUDIT/REPORT:
<reference>

PUSH:
SUCCESS / FAILED

KNOWN LIMITATIONS:
-

NEXT PROPOSED STAGE:
Sx.xx

STOPPING FOR HUMAN AUDIT.
```

No automatic continuation.

---

# 38. Human + ChatGPT + Codex Collaboration Loop

\[
\boxed{
ChatGPT\ Architecture
\rightarrow
Codex\ Implementation
\rightarrow
Tests
\rightarrow
DevLog
\rightarrow
Git
\rightarrow
ChatGPT/Human\ Audit
\rightarrow
Next\ MicroStage
}
\]

Codex owns:

```text
implementation
tests
local verification
documentation of changes
```

Human + ChatGPT own:

```text
architecture
spec interpretation
audit
model integrity
scope control
approval of next stage
```

Codex cannot alter the frozen strategy.

---

# 39. Review Severity Levels

### P0 — Mathematical Integrity

Examples:

```text
wrong EV
future data leak
wrong payoff
wrong settlement
```

Immediate stop.

### P1 — Data Integrity

Examples:

```text
wrong timestamp
bad NBBO
bad session
```

Must fix before continuation.

### P2 — Implementation Correctness

Examples:

```text
wrong validation
missing edge case
```

Fix before Sprint progression.

### P3 — Maintainability / Governance

Examples:

```text
naming
duplication
documentation
report mechanics
```

May be scheduled if non-blocking.

### P4 — Optimization

Examples:

```text
performance
vectorization
caching
```

Do not optimize early unless required.

Priority:

\[
P0>P1>P2>P3>P4
\]

---

# 40. Definition of Done

A stage is not complete merely because code exists.

All applicable conditions must hold:

```text
[ ] assigned scope implemented
[ ] unit tests added where applicable
[ ] existing tests still pass
[ ] no frozen spec changes
[ ] no unexplained dependency additions
[ ] no look-ahead possibility introduced
[ ] stage report written
[ ] implementation committed
[ ] implementation pushed
[ ] report/audit committed
[ ] report/audit pushed
[ ] agent stopped
```

Only after Human + ChatGPT audit may the next stage begin.

---

# 41. Original First Codex Task

```text
Implement OAE v0.1 micro-stage S1.01 only.

Read AGENTS.md and the available specification documents first.

Scope:
- initialize the repository skeleton;
- create README.md;
- create AGENTS.md;
- create docs/specs/, docs/devlog/, config/, sql/, src/oae/, tests/, data/;
- create src/oae/__init__.py;
- create .gitignore.

Do NOT:
- implement financial mathematics;
- create database schemas;
- create feature logic;
- create model logic;
- add unnecessary dependencies;
- start S1.02.

Verification:
- Python must successfully import `oae`;
- pytest command must start successfully.

After implementation:
1. run verification;
2. commit and push implementation;
3. write docs/devlog/S1.01_bootstrap.md;
4. commit and push the audit log;
5. report both commit SHAs;
6. STOP.

Do not begin another stage.
```

---

# END OF IMPLEMENTATION SPECIFICATION
