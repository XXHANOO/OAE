# OAE v0.1 — Implementation Errata

**Document ID:** OAE-IMPL-ERRATA-v0.1.0
**System Version:** OAE-v0.1.0
**Status:** CANONICAL / APPROVED IMPLEMENTATION ERRATA
**Approved Stage:** S1.03B

## 1. Purpose and Narrow Authority

This document resolves implementation incompleteness where the frozen
Data/Backtest Specification already requires information that is omitted from
examples in the Implementation Specification.

This errata:

- does not alter frozen financial, model, or data semantics;
- does not replace the original Implementation Specification;
- supersedes the original Implementation Specification only for the exact
  discrepancies enumerated in this document;
- leaves the original canonical hierarchy in force for every unlisted matter;
- requires Human + ChatGPT review for any newly discovered conflict that is not
  explicitly resolved here.

No numerical value, financial formula, feature, timestamp rule, trading rule,
execution price, fee, Edge threshold, No-Trade rule, or predictive input is
changed or introduced by this errata.

## 2. Errata A — Frozen Configuration Completeness

### 2.1 Authoritative Resolution

Data/Backtest Specification section 76 is authoritative for the complete set
of frozen YAML keys and values.

Implementation Specification section 9 remains authoritative for the
architectural pattern:

- `StrictModel`;
- nested Pydantic configuration models;
- `extra="forbid"`;
- `frozen=True`;
- `validate_frozen_v0_1(...)`;
- full configuration hashing.

The `FrozenConfig` field coverage shown in Implementation Specification section
9 is incomplete. S1.04 must model every field present in the canonical YAML.

The authoritative top-level `FrozenConfig` structure is:

- `version`
- `timezone`
- `decision_time`
- `instrument`
- `model`
- `health`
- `ood`
- `strategy`
- `candidate`
- `quotes`
- `execution`
- `fees`
- `edge`
- `bootstrap`
- `ambiguity`

No top-level section from Data/Backtest Specification section 76 may be
omitted.

### 2.2 Required Nested Configuration Contract

The authoritative implementation schema is:

#### InstrumentConfig

- `signal_underlying: str`
- `trade_underlying: str`
- `multiplier: int`
- `settlement: SettlementStyle`

#### ModelConfig

- `train_window: int`
- `min_train: int`
- `k: int`
- `bandwidth_neighbor: int`
- `recency_half_life: int`
- `min_neff: float`
- `feature_clip: float`

#### HealthConfig

- `window: int`
- `min_distribution_skill: float`

#### OODConfig

- `percentile: float`

#### StrategyConfig

- `allowed`: tuple/list of `StrategyType` values
- `spread_width: Decimal`
- `max_trades_per_day: int`
- `hold_to_settlement: bool`

#### CandidateConfig

- `max_moneyness_distance: float`

#### QuotesConfig

- `max_age_seconds: float`
- `min_bid_size: int`
- `min_ask_size: int`

#### ExecutionConfig

- `tick_size: Decimal`
- `min_debit: Decimal`
- `max_debit: Decimal`
- `max_absolute_friction: Decimal`
- `max_relative_friction: float`
- `model: str`

#### FeesConfig

- `conservative_floor_usd: Decimal`

#### EdgeConfig

- `min_ev_usd: Decimal`
- `min_ev_over_max_loss: float`
- `min_lcb_usd_exclusive: Decimal`
- `min_lcb_over_max_loss: float`
- `min_probability_profit: float`

#### BootstrapConfig

- `draws: int`
- `base_seed: int`

#### AmbiguityConfig

- `max_score_difference: float`

#### FrozenConfig

- `version: str`
- `timezone: str`
- `decision_time: time`
- `instrument: InstrumentConfig`
- `model: ModelConfig`
- `health: HealthConfig`
- `ood: OODConfig`
- `strategy: StrategyConfig`
- `candidate: CandidateConfig`
- `quotes: QuotesConfig`
- `execution: ExecutionConfig`
- `fees: FeesConfig`
- `edge: EdgeConfig`
- `bootstrap: BootstrapConfig`
- `ambiguity: AmbiguityConfig`

### 2.3 Value Authority and Full-Configuration Validation

This document defines structure and type completeness only. It does not
duplicate or redefine frozen numerical values as a new independent source of
truth.

The actual frozen values remain exactly those in Data/Backtest Specification
section 76, including:

- `version = OAE-v0.1.0`
- `timezone = America/New_York`
- `decision_time = 13:30:00`

and every other canonical section-76 value.

`validate_frozen_v0_1(...)` must ultimately validate the entire complete
configuration, not only the subset originally shown in Implementation
Specification section 9.

`compute_config_sha256(...)` must ultimately cover the complete canonical
configuration. Exact normalized-hash serialization remains assigned to S1.05;
it is not implemented or newly specified in S1.03B beyond the requirement for
full-configuration coverage.

### 2.4 Important Omissions That Must Not Be Lost

1. `execution.model`

   The frozen value remains:

   ```text
   CONSERVATIVE_NATURAL_ONE_LOT
   ```

2. `edge.min_lcb_usd_exclusive`

   The frozen value remains:

   ```text
   0.00
   ```

   This encodes the already-frozen condition:

   ```text
   EV_LCB > 0
   ```

   The threshold is exclusive and must not be converted to `EV_LCB >= 0`.

## 3. Errata B — Raw/Core Market-Data Field Completeness

### 3.1 Field-Completeness Precedence

For the specific raw/core market-data schemas listed below, Data/Backtest
Specification field requirements determine field completeness and data
semantics. The Implementation Specification determines:

- canonical Python class names;
- canonical DuckDB table names;
- existing compatible field types;
- `StrictModel` behavior;
- implementation architecture.

Where an Implementation Specification example omits a field required by the
Data/Backtest Specification, that field must be added during the relevant
implementation stage. Existing fields must not be removed.

### 3.2 Errata B1 — Index Bar

Implementation Specification sections 10 and 28 omit `quality_status`.

Required future Pydantic field in `IndexBar1mRecord`:

```python
quality_status: QualityStatus
```

Required future DuckDB field in `core.index_bars_1m`:

```sql
quality_status VARCHAR NOT NULL
```

All existing `IndexBar1mRecord` and `core.index_bars_1m` fields remain
unchanged.

### 3.3 Errata B2 — Option Contract

Implementation Specification sections 10 and 28 omit:

- `expiration_ts_utc`
- `first_seen_date`
- `last_seen_date`
- `source`

Required future Pydantic fields in `OptionContractRecord`:

```python
expiration_ts_utc: datetime
first_seen_date: date
last_seen_date: date
source: str
```

Required future DuckDB fields in `core.option_contracts`:

```sql
expiration_ts_utc TIMESTAMPTZ NOT NULL
first_seen_date DATE NOT NULL
last_seen_date DATE NOT NULL
source VARCHAR NOT NULL
```

All existing fields remain unchanged. `series_type` remains nullable as already
specified.

### 3.4 Errata B3 — Option NBBO

Implementation Specification sections 10 and 28 omit `quote_condition`.

Required future Pydantic field in `OptionQuoteRecord`:

```python
quote_condition: str | None
```

Required future DuckDB field in `core.option_nbbo`:

```sql
quote_condition VARCHAR
```

This is a raw vendor condition field. Its absence or null value does not
authorize relaxing any frozen quote-quality or freshness rule. All existing
fields remain unchanged.

### 3.5 Errata B4 — Option Settlement

Implementation Specification sections 10 and 28 omit `raw_file_id`.

Required future Pydantic field in `SettlementRecord`:

```python
raw_file_id: str
```

Required future DuckDB field in `core.option_settlements`:

```sql
raw_file_id VARCHAR NOT NULL
```

All existing fields remain unchanged. `published_ts_utc` remains nullable as
originally specified.

## 4. No Broad Precedence Rule

S1.03B does not establish a rule that “Data Spec always overrides
Implementation Spec.” It resolves only the exact discrepancies enumerated in
this errata.

For any other future conflict:

```text
STOP.
Do not infer precedence.
Escalate to Human + ChatGPT.
```

## 5. Version and Implementation Boundary

This is an OAE v0.1 consistency repair. It restores implementation
completeness against requirements already frozen in the canonical
Data/Backtest Specification and does not create OAE v0.2.

S1.03B creates no Pydantic class, DuckDB table, SQL migration, YAML
configuration, dependency, test, or application/model implementation. Future
stages must implement the enumerated contracts without changing their frozen
semantics.

# END OF IMPLEMENTATION ERRATA
