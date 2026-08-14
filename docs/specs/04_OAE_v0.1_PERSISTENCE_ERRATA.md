# OAE v0.1 — Persistence Contract Errata

**Document ID:** OAE-PERSIST-ERRATA-v0.1.0
**System Version:** OAE-v0.1.0
**Status:** CANONICAL / APPROVED PERSISTENCE ERRATA
**Approved Stage:** S1.08A

## 1. Purpose and Narrow Authority

This document resolves persistence-representation inconsistencies among the
Frozen Mathematical Specification, Data/Backtest Specification, original
Implementation Specification, and the S1.03B Implementation Errata.

This erratum has narrow authority only over the persistence discrepancies
explicitly enumerated in this document. It resolves physical schema
ownership, table names, field names, missing persistence fields, persistent
SQL types, nullability, primary keys, representation aliases, and stage
ownership.

It does not alter:

- financial mathematics or feature definitions;
- model class or parameters;
- trading universe or strategies;
- decision time;
- market-data or point-in-time semantics;
- execution pricing or fee formulas;
- risk, health, OOD, or Edge thresholds;
- No-Trade rules;
- acceptance criteria; or
- walk-forward semantics.

This is an OAE v0.1 consistency repair, not OAE v0.2.

This document does not create a general Data-Spec-over-Implementation-Spec
precedence rule. For every future conflict not explicitly resolved here:

```text
STOP.
Escalate to Human + ChatGPT.
```

## 2. Authority Principle

The authority structure remains:

1. The Frozen Mathematical Specification governs financial and model
   semantics.
2. The Data/Backtest Specification governs market-data, point-in-time,
   execution, replay, and required persistence semantics.
3. The S1.03B Implementation Errata has narrow authority only over its
   existing Errata A and B1–B4 repairs.
4. This Persistence Errata has narrow authority only over the persistence
   representation conflicts explicitly resolved below.
5. The Implementation Specification governs all remaining architecture not
   explicitly superseded.

No conflict between the S1.03B Implementation Errata and this Persistence
Errata is intended. If one is discovered, implementation must stop and the
conflict must be escalated to Human + ChatGPT.

## 3. Persistence-Layer Ownership

### 3.1 Meta Layer

```text
meta.raw_file_manifest
```

Its existing contract remains unchanged.

### 3.2 Core Data Layer

```text
core.trading_sessions
core.index_bars_1m
core.index_sessions
core.option_contracts
core.option_nbbo
core.option_settlements
core.macro_events
core.fee_schedules
core.decision_option_snapshots
```

### 3.3 Research Layer

```text
research.feature_snapshots
research.model_samples
research.model_scaler_snapshots
research.forecast_runs
research.forecast_scenarios
research.forecast_neighbors
research.forecast_evaluations
research.option_candidates
research.daily_decisions
research.simulated_orders
research.simulated_fills
research.trade_results
```

### 3.4 Audit Layer

```text
audit.backtest_runs
audit.backtest_metrics
```

### 3.5 Dataset Snapshot Component Manifest

The dataset snapshot component manifest is not a required DuckDB table in
v0.1. It is an immutable external manifest artifact whose canonical digest is
stored as `data_snapshot_sha256`.

Exact deterministic manifest serialization and hashing belong to a future
dedicated lineage/snapshot stage before formal backtesting.

## 4. Core Additions — S1.08B Ownership

S1.08B owns adding exactly the following four tables to the corrected core
migration and its tests.

### 4.1 `core.index_sessions`

The Data-Spec logical entity `index_sessions` maps to the physical table:

```text
core.index_sessions
```

Canonical columns:

```sql
session_date_et DATE PRIMARY KEY,
spx_official_prev_close DECIMAL(18,6) NOT NULL,
spx_open DECIMAL(18,6) NOT NULL,
spx_decision_px DECIMAL(18,6) NOT NULL,
intraday_high_to_t0 DECIMAL(18,6) NOT NULL,
intraday_low_to_t0 DECIMAL(18,6) NOT NULL,
is_full_session BOOLEAN NOT NULL,
session_open_ts_utc TIMESTAMPTZ NOT NULL,
session_close_ts_utc TIMESTAMPTZ NOT NULL
```

Logical-to-physical aliases:

```text
session_open_ts  -> session_open_ts_utc
session_close_ts -> session_close_ts_utc
```

No additional field is authorized.

### 4.2 `core.macro_events`

Canonical columns:

```sql
event_id VARCHAR PRIMARY KEY,
event_date_et DATE NOT NULL,
event_start_ts_utc TIMESTAMPTZ NOT NULL,
event_end_ts_utc TIMESTAMPTZ NOT NULL,
event_type VARCHAR NOT NULL,
event_name VARCHAR NOT NULL,
source VARCHAR NOT NULL,
verified BOOLEAN NOT NULL
```

Canonical recognized `event_type` values remain:

```text
FOMC_DECISION
FOMC_PRESS_CONFERENCE
```

DDL may enforce exactly these values with a `CHECK` constraint.

### 4.3 `core.fee_schedules`

Canonical columns:

```sql
effective_from DATE NOT NULL,
effective_to DATE,
broker VARCHAR NOT NULL,
product VARCHAR NOT NULL,
per_contract_fee DECIMAL(18,6) NOT NULL,
exchange_fee DECIMAL(18,6) NOT NULL,
regulatory_fee DECIMAL(18,6) NOT NULL,
settlement_fee DECIMAL(18,6) NOT NULL,
source VARCHAR NOT NULL
```

No primary key is frozen for v0.1. No primary key may be invented.
`effective_to` remains nullable.

### 4.4 `core.decision_option_snapshots`

Logical-to-physical aliases:

```text
session_date -> session_date_et
decision_ts  -> decision_ts_utc
quote_ts     -> quote_ts_utc
bid          -> bid_px
ask          -> ask_px
```

Canonical columns:

```sql
session_date_et DATE NOT NULL,
decision_ts_utc TIMESTAMPTZ NOT NULL,
contract_id VARCHAR NOT NULL,
quote_ts_utc TIMESTAMPTZ NOT NULL,
quote_age_ms BIGINT NOT NULL,
bid_px DECIMAL(18,6) NOT NULL,
ask_px DECIMAL(18,6) NOT NULL,
bid_size INTEGER NOT NULL,
ask_size INTEGER NOT NULL,
quote_valid BOOLEAN NOT NULL,
source_quote_id VARCHAR NOT NULL,
PRIMARY KEY(session_date_et, contract_id)
```

No foreign key is authorized.

## 5. Physical Naming Rule

Where the Data/Backtest Specification and Implementation Specification clearly
refer to the same frozen quantity but use different persistence names, prefer
the existing Implementation physical name when it loses no semantics.

Every approved mapping is stated explicitly in this document. These mappings
change only physical persistence representation; they do not rename or
redefine mathematical variables.

## 6. Feature Snapshot Resolution

The physical columns remain:

```text
x1
x2
x3
x4
x5
x6
x7
x8
x9
x10
x11
```

They are frozen aliases for:

```text
x1  = x1_overnight_gap
x2  = x2_open_to_now
x3  = x3_momentum_5m
x4  = x4_momentum_30m
x5  = x5_rv_30m
x6  = x6_rv_intraday
x7  = x7_range_position
x8  = x8_trend_efficiency
x9  = x9_atm_straddle_move
x10 = x10_downside_skew
x11 = x11_term_structure
```

The existing `research.feature_snapshots` physical DDL remains the
architecture baseline. No mathematical feature changes.

## 7. Model Sample Resolution

The physical table remains:

```text
research.model_samples
```

Existing fields remain. Persistent market/reference price fields become:

```sql
decision_spx_px DECIMAL(18,6) NOT NULL,
decision_xsp_reference_px DECIMAL(18,6) NOT NULL,
settlement_xsp DECIMAL(18,6)
```

`terminal_log_return` remains `DOUBLE`.

`label_available_from` remains nullable `TIMESTAMPTZ`.

Add:

```sql
label_valid BOOLEAN NOT NULL
```

This field implements the frozen training-eligibility rule.

## 8. Scaler Snapshot Resolution

Add:

```text
research.model_scaler_snapshots
```

Canonical columns:

```sql
session_date_et DATE NOT NULL,
feature_name VARCHAR NOT NULL,
median DOUBLE NOT NULL,
mad DOUBLE NOT NULL,
scale_denominator DOUBLE NOT NULL,
PRIMARY KEY(session_date_et, feature_name)
```

Data-Spec `session_date` maps to `session_date_et`.

## 9. Neighbor Resolution

The Data-Spec logical entity `model_neighbors` maps to the Implementation
physical table:

```text
research.forecast_neighbors
```

Do not create both tables.

Canonical columns:

```sql
forecast_id VARCHAR NOT NULL,
neighbor_rank INTEGER NOT NULL,
neighbor_session_date DATE NOT NULL,
distance DOUBLE NOT NULL,
terminal_return DOUBLE NOT NULL,
similarity_weight_raw DOUBLE NOT NULL,
recency_weight DOUBLE NOT NULL,
combined_weight_raw DOUBLE NOT NULL,
normalized_weight DOUBLE NOT NULL,
age_sessions INTEGER NOT NULL,
PRIMARY KEY(forecast_id, neighbor_rank)
```

Data-Spec `terminal_return_y` maps to `terminal_return`. No weight field may be
omitted.

## 10. Forecast Run Resolution

The physical table remains:

```text
research.forecast_runs
```

Existing Implementation fields remain unless superseded here.

Add:

```sql
k INTEGER NOT NULL,
created_ts TIMESTAMPTZ NOT NULL
```

Use the physical field:

```text
data_snapshot_sha256
```

Do not create `data_snapshot_hash`. The Data-Spec logical
`data_snapshot_hash` is an alias for the canonical SHA-256 identity
`data_snapshot_sha256`.

Keep:

```sql
config_sha256 VARCHAR NOT NULL,
data_snapshot_sha256 VARCHAR,
code_commit VARCHAR
```

Formal-run non-null requirements for the latter two fields belong to later
backtest/run validation, not this research DDL.

The existing nullable semantics remain unchanged for:

```text
neff
d40
d80_today
ood_threshold
q10
q25
q50
q75
q90
distribution_skill
ood_pass
health_pass
```

unless a later explicit stage requires stronger application invariants.

## 11. Forecast Scenario Resolution

`research.forecast_scenarios` has no conflict. Implementation Specification
section 29 remains authoritative.

## 12. Forecast Health Evaluation Resolution

Add:

```text
research.forecast_evaluations
```

Canonical columns:

```sql
forecast_id VARCHAR PRIMARY KEY,
realized_y DOUBLE NOT NULL,
evaluated_ts_utc TIMESTAMPTZ NOT NULL
```

The original point-in-time quantiles `q10`, `q50`, and `q90` remain stored in
`research.forecast_runs`. A forecast evaluation joins `realized_y` to the
original persisted forecast.

This satisfies the Data-Spec requirement to preserve `q10`, `q50`, `q90`, and
`realized_y` for historical point-in-time health evaluation.

Do not create separate mutable historical coverage fields. Q10/Q50/Q90
coverage is calculated from immutable point-in-time forecast values and
`realized_y`. Old forecasts must not be retrospectively rebuilt.

## 13. Option Candidate Resolution

The physical table remains:

```text
research.option_candidates
```

Keep the Implementation physical names:

```text
ev_over_max_loss
lcb_over_max_loss
probability_profit
```

They map to the Data-Spec logical names:

```text
ev_over_maxloss
lcb_over_maxloss
prob_profit
```

Add:

```sql
session_date_et DATE NOT NULL,
long_bid DECIMAL(18,6),
long_ask DECIMAL(18,6),
short_bid DECIMAL(18,6),
short_ask DECIMAL(18,6),
long_quote_ts_utc TIMESTAMPTZ,
short_quote_ts_utc TIMESTAMPTZ,
candidate_valid BOOLEAN NOT NULL,
gate_ev BOOLEAN,
gate_ev_ratio BOOLEAN,
gate_lcb BOOLEAN,
gate_lcb_ratio BOOLEAN,
gate_pop BOOLEAN,
fee_source VARCHAR
```

Data-Spec `session_date`, `long_quote_ts`, and `short_quote_ts` map to
`session_date_et`, `long_quote_ts_utc`, and `short_quote_ts_utc`.

Keep `forecast_id VARCHAR NOT NULL`. Although Data section 51 did not list it,
it is canonical research lineage.

Persistent exact-price fields become:

```sql
long_strike DECIMAL(18,4) NOT NULL,
short_strike DECIMAL(18,4) NOT NULL,
d_mid DECIMAL(18,6),
d_natural DECIMAL(18,6),
d_exec DECIMAL(18,6),
spread_friction DECIMAL(18,6),
fee DECIMAL(18,6),
max_loss DECIMAL(18,6),
max_profit DECIMAL(18,6)
```

Model/statistical fields remain `DOUBLE`:

```text
expected_payoff
ev
ev_over_max_loss
ev_lcb
lcb_over_max_loss
probability_profit
robust_score
```

Quote/economic fields may remain nullable when candidate evidence is
incomplete. No midpoint-fill semantic is introduced.

## 14. Fee Source Resolution

Canonical `fee_source` values are:

```text
ACTUAL
CONSERVATIVE_FLOOR
```

Candidate fee provenance is stored in
`research.option_candidates.fee_source`. Fill fee provenance is stored in
`research.simulated_fills.fee_source`.

No fee formula changes.

## 15. Daily Decision Resolution

The physical table remains:

```text
research.daily_decisions
```

Physical-to-logical mappings:

```text
session_date_et    -> session_date
decision_ts_utc    -> decision_ts
expected_ev        -> ev
expected_ev_lcb    -> ev_lcb
data_snapshot_sha256 -> data_version
```

The left-hand names above are the canonical physical columns. No separate
`data_version` column is created.

Existing fields remain. Add:

```sql
data_snapshot_sha256 VARCHAR NOT NULL,
model_status VARCHAR NOT NULL,
n_train INTEGER,
neff DOUBLE,
ood_pass BOOLEAN,
health_pass BOOLEAN,
skill_pass BOOLEAN,
expected_payoff DOUBLE,
probability_profit DOUBLE,
max_profit DECIMAL(18,6),
created_at TIMESTAMPTZ NOT NULL
```

Keep:

```text
forecast_id nullable
best_candidate_id nullable
expected_ev DOUBLE nullable
expected_ev_lcb DOUBLE nullable
max_loss DOUBLE or compatible existing metric storage, nullable
robust_score DOUBLE nullable
```

`decision` remains `TRADE` or `NO_TRADE` with the existing check.

## 16. Decision ET Timestamp Resolution

Do not add a duplicate DuckDB `decision_ts_et` column.

Canonical persisted DuckDB identity is:

```text
decision_ts_utc
+
session_date_et
+
frozen timezone America/New_York
```

`decision_ts_et` is a deterministic derived representation at application and
report boundaries. This resolution changes no decision-time or DST semantic.

## 17. Simulated Order Resolution

Add:

```text
research.simulated_orders
```

Canonical columns:

```sql
order_id VARCHAR PRIMARY KEY,
decision_id VARCHAR NOT NULL,
strategy VARCHAR NOT NULL,
quantity INTEGER NOT NULL,
submit_ts_utc TIMESTAMPTZ NOT NULL,
order_type VARCHAR NOT NULL,
limit_price DECIMAL(18,6) NOT NULL,
expected_fill_price DECIMAL(18,6) NOT NULL,
execution_model VARCHAR NOT NULL,
status VARCHAR NOT NULL
```

Data-Spec `submit_ts` maps to `submit_ts_utc`. No additional execution
behavior is introduced.

## 18. Simulated Fill Resolution

Add:

```text
research.simulated_fills
```

Canonical columns:

```sql
fill_id VARCHAR PRIMARY KEY,
order_id VARCHAR NOT NULL,
fill_ts_utc TIMESTAMPTZ NOT NULL,
fill_price DECIMAL(18,6) NOT NULL,
quantity INTEGER NOT NULL,
fee DECIMAL(18,6) NOT NULL,
fee_source VARCHAR NOT NULL,
fill_model VARCHAR NOT NULL
```

Data-Spec `fill_ts` maps to `fill_ts_utc`. Data section 54 `fill_type` and Data
section 70 `fill_model` resolve to the single physical field `fill_model`.
Do not create a second `fill_type` column.

The frozen v0.1 `fill_model` value is:

```text
SIMULATED_NATURAL
```

This does not change `CONSERVATIVE_NATURAL_ONE_LOT`, which remains the
execution model.

## 19. Trade Result Resolution

The physical table remains:

```text
research.trade_results
```

Add:

```sql
session_date_et DATE NOT NULL,
expected_ev DOUBLE NOT NULL,
expected_ev_lcb DOUBLE NOT NULL,
settled BOOLEAN NOT NULL
```

Persistent exact economic fields become:

```sql
settlement_value DECIMAL(18,6),
gross_payoff DECIMAL(18,6),
entry_cost DECIMAL(18,6) NOT NULL,
fee_total DECIMAL(18,6) NOT NULL,
net_pnl DECIMAL(18,6)
```

`return_on_max_loss` remains `DOUBLE`. `won` may be nullable until settled.
Settlement/P&L fields may be nullable when `settled = false`.

Data-Spec `forecast_error` is an undefined diagnostic placeholder. No formula
for it exists in the Frozen Mathematical Specification. It must not be
invented in v0.1 and is explicitly deferred and omitted from the v0.1
physical DDL until a future version or approved semantic definition exists.

Do not silently define it as settlement minus median, settlement minus
expected value, P&L minus EV, or any other interpretation.

## 20. Persistent Numeric Type Policy

The Implementation Specification section 6 versus section 29 type conflict is
resolved as follows.

Use `DECIMAL` for persisted exact market, execution, and economic quantities
where cent, tick, or quoted-value fidelity matters, including:

```text
market/reference prices
official settlement values
option strikes
bid/ask
D_mid
D_natural
D_exec
spread friction
limit/fill prices
fees
deterministic cash payoff/cost/P&L fields
```

Use `DOUBLE` for:

```text
features
terminal log return
distances
weights
quantiles
Neff
OOD metrics
distribution skill
probabilities
expected payoff
model EV
EV LCB
ratios
robust score
calibration/statistical metrics
```

Model computation remains float64. No mathematical formula changes.

## 21. Audit Backtest Run Resolution

The physical table remains:

```text
audit.backtest_runs
```

Add:

```sql
python_environment_hash VARCHAR NOT NULL
```

The status domain is frozen as:

```text
SUCCESS
FAILED
```

S1.10 shall enforce:

```sql
CHECK(status IN ('SUCCESS','FAILED'))
```

All other Implementation Specification section 30 fields remain.

## 22. Backtest Metrics Resolution

Add:

```text
audit.backtest_metrics
```

Canonical primary key:

```sql
run_id VARCHAR PRIMARY KEY
```

Data-Spec `n_sessions` means formal out-of-sample sessions included in
acceptance statistics.

Canonical columns include every Data Specification section 86 minimum metric:

```text
run_id
n_sessions
n_trade_signals
n_no_trade
trade_frequency
gross_pnl
net_pnl
mean_pnl
median_pnl
win_rate
avg_win
avg_loss
profit_factor
ev_predicted_mean
ev_realized_mean
max_drawdown
sharpe
sortino
largest_win
largest_loss
call_spread_count
put_spread_count
calibration_q10
calibration_q50
calibration_q90
distribution_skill
```

Also add the required acceptance evidence:

```text
mean_net_pnl_ci_lower_95
aggregate_oos_ev
acceptance_result
```

The `acceptance_result` domain is:

```text
POTENTIAL_ALPHA
NO_VALIDATED_ALPHA
```

This does not modify the acceptance criteria; it persists the already-frozen
result.

Use `DECIMAL` for aggregate cash P&L, drawdown, and largest-win/loss
quantities. Use `DOUBLE` for statistical ratios, means, calibration, and EV
statistics. Counts use `BIGINT`.

## 23. Dataset Snapshot Resolution

Data Specification section 83 does not require a relational DuckDB table.
The canonical v0.1 dataset snapshot is an immutable manifest artifact.

The artifact must contain:

```text
dataset_snapshot_id
all raw-file SHA256 identities
all normalized partition SHA256 identities
calendar version
event-calendar version
```

Its aggregate digest is `data_snapshot_sha256`. Database tables persist only
the digest where required.

The exact deterministic manifest serialization and hashing algorithm is
assigned to a later dedicated lineage/snapshot stage before any formal
backtest. It must not be invented in S1.08A.

## 24. No Foreign Keys, Defaults, or Indexes

Unless already explicitly frozen:

- do not introduce foreign keys;
- do not introduce `DEFAULT` clauses; and
- do not introduce standalone indexes.

Primary keys listed in this erratum are authoritative.

## 25. Stage Ownership After This Erratum

### S1.08B — Complete Core Persistence

Owns adding:

```text
core.index_sessions
core.macro_events
core.fee_schedules
core.decision_option_snapshots
```

to the corrected core migration and tests.

### S1.09 — Research SQL Migration

Owns the complete reconciled research contract in this erratum.

### S1.10 — Audit SQL Migration

Owns:

```text
audit.backtest_runs
audit.backtest_metrics
```

Dataset snapshot manifest implementation is deferred to a future dedicated
lineage/snapshot implementation stage before formal walk-forward acceptance.

## 26. Version and Implementation Boundary

This erratum creates no SQL migration, application code, DTO, test, dataset
manifest serialization, or backtest implementation. Those changes belong only
to their explicitly assigned later stages.

# END OF PERSISTENCE CONTRACT ERRATA
