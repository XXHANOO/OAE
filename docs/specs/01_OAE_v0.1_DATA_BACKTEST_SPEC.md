# Options Alpha Engine v0.1 — Data Specification + Backtest Architecture

**Document ID:** OAE-DATA-BT-v0.1.0  
**System Version:** OAE-v0.1.0  
**Status:** CANONICAL / FROZEN IMPLEMENTATION INPUT  
**Purpose:** Map every frozen mathematical variable to point-in-time data, timestamps, schemas, persistence rules, and deterministic walk-forward backtest execution.

This document does not change the OAE v0.1 mathematics. If a conflict is discovered with the Frozen Mathematical Specification, development must stop and the conflict must be escalated rather than silently resolved.

---

# 1. System Data Flow

```text
Raw Market Data
      ↓
Immutable Raw Store
      ↓
Normalization
      ↓
Point-in-Time / As-Of Engine
      ↓
Session Dataset
      ↓
Feature Engine
      ↓
Historical Label Store
      ↓
KNN Distribution Model
      ↓
Model Health / OOD / Skill Gates
      ↓
XSP Candidate Generator
      ↓
Execution Pricing Engine
      ↓
EV / LCB / PoP Engine
      ↓
Decision Engine
      ↓
Simulated Execution
      ↓
Official Settlement
      ↓
Realized P&L
      ↓
Audit + Walk-Forward History
```

Highest-order data rule:

\[
\boxed{\text{No component may read information that did not yet exist at the decision time}}
\]

The entire system must be point-in-time correct.

---

# 2. Storage Architecture

## 2.1 Immutable Raw Store

Preferred format:

```text
Parquet
```

Purpose:

- preserve provider-originated raw market data;
- never overwrite historical raw files;
- allow the backtest to be reconstructed;
- preserve lineage;
- retain the evidence underlying every derived dataset.

Suggested layout:

```text
data/
├── raw/
│   ├── spx_index/
│   ├── spx_options_nbbo/
│   ├── xsp_options_nbbo/
│   ├── xsp_settlement/
│   ├── trading_calendar/
│   └── macro_events/
│
├── normalized/
├── features/
├── forecasts/
├── decisions/
└── backtests/
```

Each raw file must be registered in:

```text
raw_file_manifest
```

with at least:

```text
source
source_file_name
ingested_at_utc
sha256
schema_version
min_event_ts
max_event_ts
row_count
```

## 2.2 Analytical Store

v0.1 uses:

```text
DuckDB + Parquet
```

Rationale:

- single-machine research is sufficient;
- SQL is easy to audit;
- Parquet is directly supported;
- walk-forward queries remain reproducible;
- no premature distributed-system complexity.

A later live system may migrate to another database, but the v0.1 backtest must not depend on mutable production state.

---

# 3. Timestamp Standard

Persistent standard timestamp:

```text
UTC
```

All event timestamps must be timezone aware.

Logical type:

```text
TIMESTAMP WITH TIME ZONE
```

or DuckDB:

```text
TIMESTAMPTZ
```

Also persist:

```text
session_date_et
```

Market timezone:

```text
America/New_York
```

Never hardcode UTC-5 because DST changes the offset.

Naive datetimes are forbidden.

---

# 4. Decision Timestamp

Each eligible full session has exactly one decision time:

\[
\boxed{t_0=13:30:00\ America/New\_York}
\]

Persist:

```text
decision_ts_utc
decision_ts_et
session_date_et
```

DST conversion must use a proper timezone database.

---

# 5. One-Minute Bar Semantics

One-minute bars are frozen as:

\[
[start,end)
\]

The last allowed bar at the 13:30 decision is:

```text
13:29:00 <= event_time < 13:30:00
```

Persist:

```text
bar_start_ts
bar_end_ts
```

Usable only when:

\[
bar\_end\_ts\le decision\_ts
\]

Therefore:

\[
S_t
\]

is the close of the 13:29–13:30 bar.

The 13:30–13:31 bar is future information and is forbidden.

---

# 6. SPX One-Minute Bar Table

Table:

```text
index_bars_1m
```

Schema:

| Field | Type | Meaning |
|---|---|---|
| symbol | TEXT | `SPX` |
| session_date_et | DATE | ET trading date |
| bar_start_ts_utc | TIMESTAMPTZ | bar start |
| bar_end_ts_utc | TIMESTAMPTZ | bar end |
| open | DECIMAL(18,6) | open |
| high | DECIMAL(18,6) | high |
| low | DECIMAL(18,6) | low |
| close | DECIMAL(18,6) | close |
| observation_count | INTEGER | raw observation count |
| source | TEXT | source |
| raw_file_id | UUID/VARCHAR | lineage |
| quality_status | TEXT | validity state |

Primary key:

```text
(symbol, bar_end_ts_utc)
```

---

# 7. SPX Session-Level State

Derived table:

```text
index_sessions
```

Fields:

```text
session_date_et
spx_official_prev_close
spx_open
spx_decision_px
intraday_high_to_t0
intraday_low_to_t0
is_full_session
session_open_ts
session_close_ts
```

Mappings:

\[
S_{pc}=spx\_official\_prev\_close
\]

\[
S_o=spx\_open
\]

where SPX open is the open of the 09:30–09:31 bar.

\[
S_t=spx\_decision\_px
\]

where decision price is the close of the 13:29–13:30 bar.

---

# 8. Canonical Minute Return Series

For the first regular-session minute:

\[
r_{09:31}
=
\ln
\left(
\frac{Close_{09:31}}{S_o}
\right)
\]

For each later minute:

\[
r_m=
\ln
\left(
\frac{Close_m}{Close_{m-1}}
\right)
\]

The last allowed return is the one associated with the bar ending at 13:30.

x5, x6, and x8 must reuse exactly this same return series.

---

# 9. Option Contract Master

Create:

```text
option_contracts
```

Schema:

| Field | Type |
|---|---|
| contract_id | UUID/VARCHAR |
| vendor_symbol | TEXT |
| product | TEXT |
| root_symbol | TEXT |
| underlying | TEXT |
| option_type | C/P |
| strike | DECIMAL(18,4) |
| expiration_date | DATE |
| settlement_style | AM/PM |
| exercise_style | EUROPEAN/AMERICAN |
| multiplier | INTEGER |
| series_type | TEXT |
| expiration_ts_utc | TIMESTAMPTZ |
| first_seen_date | DATE |
| last_seen_date | DATE |
| source | TEXT |

A vendor may use root `SPXW` for PM Weeklys. Internal semantics should preserve the SPX product/underlying while retaining the vendor root:

```text
product = SPX
underlying = SPX
root_symbol = SPXW
```

where applicable.

---

# 10. PM-Only Eligibility

For x9 and same-day SPX option state:

```text
product = SPX
settlement_style = PM
expiration_date = session_date
```

For x11 next expiry:

\[
e_1=\min(e>session\_date)
\]

subject to:

```text
settlement_style = PM
```

For actual trade candidates:

```text
product = XSP
settlement_style = PM
expiration_date = session_date
```

---

# 11. Option NBBO Tick Schema

Table:

```text
option_nbbo
```

Schema:

| Field | Type |
|---|---|
| contract_id | UUID/VARCHAR |
| quote_ts_utc | TIMESTAMPTZ |
| session_date_et | DATE |
| bid_px | DECIMAL(18,6) |
| ask_px | DECIMAL(18,6) |
| bid_size | INTEGER |
| ask_size | INTEGER |
| bid_exchange | TEXT |
| ask_exchange | TEXT |
| quote_condition | TEXT |
| sequence_no | BIGINT |
| source | TEXT |
| raw_file_id | UUID/VARCHAR |

A future live system may also store:

```text
recv_ts_utc
```

for feed-latency analysis.

---

# 12. NBBO As-Of Rule

For contract quotes at decision time \(t_0\), select:

\[
\boxed{
q^*
=
\arg\max_q quote\_ts(q)
\quad
s.t.\quad quote\_ts(q)\le t_0
}
\]

Never use nearest-timestamp selection.

Allowed semantic:

```text
asof backward
```

Forbidden:

```text
nearest timestamp
future quote
```

---

# 13. Quote Age

\[
QuoteAge=t_0-quote\_ts
\]

Frozen rule:

\[
\boxed{QuoteAge\le2.000s}
\]

Boundary examples:

```text
1.999s -> valid
2.000s -> valid
2.001s -> invalid/stale
```

---

# 14. Historical Quote Capability Requirement

Because the frozen model requires quote age ≤ 2 seconds, the formal acceptance dataset must retain the actual last quote-update timestamp, or an equivalent field that allows exact staleness verification.

A one-minute snapshot that only reports a 13:30 state but does not preserve the actual underlying NBBO update timestamp cannot satisfy the formal rule.

Therefore:

\[
\boxed{\text{minute-only option snapshots without actual quote-update timestamps are insufficient for formal v0.1 acceptance}}
\]

unless the provider supplies `last_quote_update_ts` or equivalent.

---

# 15. NBBO Validity

A required quote is valid only if:

\[
Bid>0
\]

\[
Ask>Bid
\]

\[
BidSize\ge1
\]

\[
AskSize\ge1
\]

\[
QuoteAge\le2.000s
\]

Under the frozen rule:

```text
Bid == Ask
```

is invalid.

Do not silently relax this rule.

---

# 16. XSP Decision Reference

No separate intraday XSP index feed is required for the v0.1 reference.

Define:

\[
\boxed{X_t=S_t/10}
\]

Persist:

```text
xsp_reference_px
```

This reference is distinct from official settlement.

---

# 17. Official Settlement Table

Create:

```text
option_settlements
```

Schema:

| Field | Type |
|---|---|
| product | TEXT |
| expiration_date | DATE |
| settlement_style | TEXT |
| settlement_value | DECIMAL(18,6) |
| effective_ts_utc | TIMESTAMPTZ |
| published_ts_utc | TIMESTAMPTZ nullable |
| source | TEXT |
| raw_file_id | UUID/VARCHAR |

For model labels and realized outcomes, use official:

```text
product = XSP
settlement_style = PM
```

Do not substitute:

- last option quote;
- a 15:59:59 option quote;
- an approximate XSP mark;
- SPX/10 as the official settlement.

---

# 18. Label Availability Rule

Persist:

```text
label_available_from
```

Frozen conservative rule:

\[
\boxed{\text{next eligible trading session at 09:30 ET}}
\]

Session \(d\)'s label may enter training only from the next eligible session onward.

---

# 19. Model Sample / Label Table

Create:

```text
model_samples
```

Core fields:

```text
session_date_et
decision_spx_px
decision_xsp_reference_px
settlement_xsp
terminal_log_return
label_available_from
```

Decision XSP reference:

\[
X_{13:30,d}=SPX_{13:30,d}/10
\]

Label:

\[
\boxed{
Y_d=
\ln
\left(
\frac{X_{T,d}}{X_{13:30,d}}
\right)
}
\]

Persist:

```text
terminal_log_return
```

---

# 20. Feature Snapshot Table

Create:

```text
feature_snapshots
```

One row per session:

```text
feature_version
session_date_et
decision_ts_utc

x1_overnight_gap
x2_open_to_now
x3_momentum_5m
x4_momentum_30m
x5_rv_30m
x6_rv_intraday
x7_range_position
x8_trend_efficiency
x9_atm_straddle_move
x10_downside_skew
x11_term_structure

feature_valid
invalid_reason
```

Frozen version:

```text
OAE-v0.1.0
```

---

# 21. x1 Mapping

\[
x_1=
\ln
\frac{S_o}{S_{pc}}
\]

Inputs:

```text
spx_open
spx_official_prev_close
```

---

# 22. x2 Mapping

\[
x_2=
\ln
\frac{S_t}{S_o}
\]

Inputs:

```text
spx_decision_px
spx_open
```

---

# 23. x3 Mapping

\[
x_3=
\ln
\frac{S_t}{S_{t-5m}}
\]

Frozen bar mapping:

```text
S_t    = bar ending 13:30
S_t-5m = bar ending 13:25
```

---

# 24. x4 Mapping

\[
x_4=
\ln
\frac{S_t}{S_{t-30m}}
\]

Frozen:

```text
13:30 close
13:00 close
```

---

# 25. x5 Mapping

Use the final 30 canonical one-minute returns ending at the decision:

\[
x_5=
\sqrt{\sum_{j=1}^{30}r_j^2}
\]

Equivalent interval:

```text
13:00 -> 13:30
```

Not annualized.

---

# 26. x6 Mapping

Use all canonical regular-session returns from open through 13:30:

\[
x_6=
\sqrt{\sum r_j^2}
\]

---

# 27. x7 Mapping

Inputs:

```text
intraday_high_to_t0
intraday_low_to_t0
spx_decision_px
```

\[
x_7=
\frac{S_t-L_t}
{H_t-L_t+10^{-8}}
\]

Only bars fully available by 13:30 may contribute to high/low.

---

# 28. x8 Mapping

\[
x_8=
\frac{
|\ln(S_t/S_o)|
}{
\sum|r_j|+10^{-8}
}
\]

Use the same canonical return series as x6.

---

# 29. x9 — Same-Day ATM Straddle

Eligible chain:

```text
SPX
PM settlement
expiration_date = session_date
```

Choose:

\[
K_{ATM}
=
\arg\min_K|K-S_t|
\]

Frozen tie break:

1. smallest absolute distance;
2. lower strike.

For the call and put at that strike, use valid point-in-time NBBO.

Mid:

\[
Mid=(Bid+Ask)/2
\]

Then:

\[
x_9=
\frac{C_{mid}+P_{mid}}{S_t}
\]

Both quotes must be valid.

Otherwise:

```text
feature_valid = false
```

and no trade is permitted.

---

# 30. x10 — Downside Skew

Targets:

\[
K^-_{target}=0.995S_t
\]

\[
K^+_{target}=1.005S_t
\]

Choose nearest listed strikes with the same deterministic tie rule.

Then:

\[
x_{10}
=
\frac{
P_{mid}(K^-)-C_{mid}(K^+)
}{
C_{ATM}^{mid}+P_{ATM}^{mid}
}
\]

---

# 31. x11 — Term Structure

Same-day PM expiry:

```text
e0
```

Next eligible PM expiry:

\[
e_1=\min(expiration>today)
\]

Choose ATM independently for each expiry.

\[
M_0=
\frac{C_0+P_0}{S_t}
\]

\[
M_1=
\frac{C_1+P_1}{S_t}
\]

Calendar time:

\[
\boxed{
\tau=
\frac{
expiration\_reference\_ts-decision\_ts
}{
365.25\times86400
}
}
\]

Use PM reference timestamp:

```text
16:00:00 America/New_York
```

for \(\tau\) only.

It is not the settlement publication time.

Then:

\[
x_{11}
=
\frac{M_0}{\sqrt{\tau_0}}
-
\frac{M_1}{\sqrt{\tau_1}}
\]

---

# 32. Trading Calendar Schema

Create:

```text
trading_sessions
```

Fields:

```text
session_date_et
session_seq
open_ts_utc
regular_close_ts_utc
is_trading_day
is_full_session
is_half_day
xsp_0dte_exists
```

`session_seq` is a monotonically increasing trading-session index.

---

# 33. Training Age

For current session sequence \(s_t\) and historical session \(s_i\):

\[
Age_i=s_t-s_i
\]

Use trading-session distance, not calendar days.

---

# 34. Macro Event Schema

Create:

```text
macro_events
```

Fields:

```text
event_id
event_date_et
event_start_ts_utc
event_end_ts_utc
event_type
event_name
source
verified
```

v0.1 recognizes only:

```text
FOMC_DECISION
FOMC_PRESS_CONFERENCE
```

If the event interval overlaps:

```text
13:30-16:00 ET
```

then the current session is NO TRADE.

A diagnostic forecast may still be produced if otherwise valid.

---

# 35. Training Eligibility

A historical session may enter training only if:

```text
is_full_session = true
feature_valid = true
label_valid = true
label_available_from < current_decision_ts
```

A historical full FOMC session may remain in the training distribution.

Half-days are excluded because the 13:30-to-settlement horizon differs.

---

# 36. Historical Data Requirement

Formal acceptance dataset target:

\[
\boxed{\ge1300\ complete\ valid\ sessions}
\]

This allows:

- 756-session full training window;
- 500+ formal OOS sessions;
- buffer for holidays, bad rows, missing sessions, and corrupted data.

---

# 37. Warm-Up States

### Fewer than 504 valid prior sessions

```text
MODEL_NOT_READY
```

No official signal.

### 504–755 valid prior sessions

Shadow forecasts may be generated using available valid prior sessions.

These may help accumulate health history but do not belong in formal acceptance-performance statistics.

### 756 or more valid prior sessions

Use exactly the most recent:

\[
756
\]

valid prior sessions.

---

# 38. Robust Scaler Persistence

For each current training window compute:

```text
median[11]
mad[11]
```

Persist:

```text
model_scaler_snapshots
```

Fields:

```text
session_date
feature_name
median
mad
scale_denominator
```

with:

\[
scale\_denominator=1.4826MAD+10^{-8}
\]

Clip standardized values to:

\[
[-5,+5]
\]

---

# 39. Neighbor Persistence

Create:

```text
model_neighbors
```

Persist all 80 neighbors:

```text
forecast_id
neighbor_rank
neighbor_session_date
distance
terminal_return_y
similarity_weight_raw
recency_weight
combined_weight_raw
normalized_weight
age_sessions
```

---

# 40. Forecast Run Schema

Create:

```text
forecast_runs
```

Fields:

```text
forecast_id
session_date_et
model_version
n_train
k
neff
d40
d80_today
ood_threshold
ood_pass

q10
q25
q50
q75
q90

distribution_skill
health_pass

created_ts
data_snapshot_hash
code_commit
```

---

# 41. Forecast Scenario Table

Create:

```text
forecast_scenarios
```

Fields:

```text
forecast_id
scenario_rank
historical_session
terminal_log_return
scenario_weight
projected_xsp_settlement
```

Projection:

\[
X^*_{T,i}=X_t e^{Y_i}
\]

---

# 42. Effective Sample Size

Persist:

```text
neff
```

\[
N_{eff}
=
\frac1{\sum_iw_i^2}
\]

Invariant:

\[
1\le N_{eff}\le80
\]

Gate:

\[
N_{eff}\ge30
\]

---

# 43. OOD Implementation

For each current training window:

1. fit robust scaler on training data only;
2. standardize training and current feature vectors;
3. for each training observation, perform leave-one-out distance calculation;
4. compute each training observation's 80th-nearest-neighbor distance;
5. calculate:

\[
OODThreshold=Q_{99.5\%}(d80_{train})
\]

Current state passes only if:

\[
d80_t\le OODThreshold
\]

Otherwise:

```text
NT_OOD
```

---

# 44. Model-Health History

Store each original point-in-time forecast.

Do not retrospectively rebuild past predictions with future-expanded data and treat them as historical forecasts.

Health window:

\[
\boxed{\text{most recent 126 valid OOS forecasts}}
\]

not 126 calendar days.

---

# 45. Quantile Coverage

Persist for each evaluated historical forecast:

```text
q10
q50
q90
realized_y
```

Coverage gates:

\[
0.05\le Q10Coverage\le0.15
\]

\[
0.43\le Q50Coverage\le0.57
\]

\[
0.85\le Q90Coverage\le0.95
\]

If fewer than 126 eligible historical forecast evaluations exist:

```text
MODEL_HEALTH_WARMUP
```

No formal trade signal.

---

# 46. CRPS

Use terminal log-return scale.

\[
\boxed{
CRPS(F,y)
=
\sum_iw_i|Y_i-y|
-
\frac12
\sum_i\sum_j
w_iw_j|Y_i-Y_j|
}
\]

---

# 47. Unconditional Baseline

Use the same historical training-window returns but ignore features.

Baseline weights:

\[
w_i=1/N
\]

Over the health window calculate:

\[
DistributionSkill
=
1-
\frac{CRPS_{OAE}}
{CRPS_{baseline}}
\]

Require:

\[
\boxed{DistributionSkill\ge0.02}
\]

---

# 48. XSP Candidate Universe

At 13:30 load:

```text
XSP
expiration_date = session_date
settlement_style = PM
```

Reference:

\[
X_t=S_t/10
\]

Eligible long strikes:

\[
\left|
\frac K{X_t}-1
\right|
\le0.005
\]

---

# 49. Bull Call Candidate

For eligible \(K\), only create if \(K+1\) exists:

```text
BULL_CALL_DEBIT
BUY  1 CALL K
SELL 1 CALL K+1
```

Invariant:

\[
ShortStrike-LongStrike=1.0000
\]

---

# 50. Bear Put Candidate

For eligible \(K\), only create if \(K-1\) exists:

```text
BEAR_PUT_DEBIT
BUY  1 PUT K
SELL 1 PUT K-1
```

Invariant:

\[
LongStrike-ShortStrike=1.0000
\]

---

# 51. Candidate Table

Create:

```text
option_candidates
```

Fields:

```text
candidate_id
session_date
strategy_type

long_contract_id
short_contract_id

long_strike
short_strike

long_bid
long_ask
short_bid
short_ask

long_quote_ts
short_quote_ts

d_mid
d_natural
d_exec
spread_friction

fee
max_loss
max_profit

expected_payoff
ev
ev_over_maxloss
ev_lcb
lcb_over_maxloss
prob_profit
robust_score

liquidity_pass
edge_pass
candidate_valid
```

---

# 52. Natural and Mid Prices

\[
D_{nat}=Ask_{long}-Bid_{short}
\]

\[
D_{mid}
=
\frac{Bid_L+Ask_L}{2}
-
\frac{Bid_S+Ask_S}{2}
\]

---

# 53. Executable Price

Frozen tick:

\[
tick=0.01
\]

\[
D_{exec}
=
\left\lceil
\frac{D_{nat}}{0.01}
\right\rceil0.01
\]

Invariant:

\[
D_{exec}\ge D_{nat}
\]

---

# 54. Backtest Fill Assumption

Frozen execution model:

```text
CONSERVATIVE_NATURAL_ONE_LOT
```

When both legs have valid quotes and at least one contract of displayed bid/ask size, assume one spread can fill at:

\[
D_{exec}
\]

Persist:

```text
fill_type = SIMULATED_NATURAL
```

This is a model assumption, not historical order evidence.

Shadow-live work must later test the fill assumption.

---

# 55. Midpoint Fill Is Forbidden

Do not use:

```text
fill_price = D_mid
```

Formal v0.1 entry fill uses only:

\[
D_{exec}
\]

---

# 56. Liquidity Gate

\[
F_{spread}=D_{exec}-D_{mid}
\]

Required:

\[
0.15\le D_{exec}\le0.75
\]

\[
F_{spread}\le0.05
\]

\[
\frac{F_{spread}}{D_{exec}}\le0.25
\]

Each leg:

```text
bid_size >= 1
ask_size >= 1
quote_age <= 2.000s
bid > 0
ask > bid
```

---

# 57. Fee Engine

Create:

```text
fee_schedules
```

Fields:

```text
effective_from
effective_to
broker
product
per_contract_fee
exchange_fee
regulatory_fee
settlement_fee
source
```

If accurate historical all-in fee exists:

\[
Fee=\max(Fee_{actual},3)
\]

Otherwise:

\[
\boxed{Fee=\$3.00}
\]

Persist:

```text
fee_source = ACTUAL
```

or:

```text
fee_source = CONSERVATIVE_FLOOR
```

---

# 58. EV Engine

Bull-call scenario payoff:

\[
\pi_i=
\min[
\max(X^*_{T,i}-K,0),
1
]
\]

Bear-put scenario payoff:

\[
\pi_i=
\min[
\max(K-X^*_{T,i},0),
1
]
\]

Expected payoff:

\[
E[\pi]=\sum_iw_i\pi_i
\]

Cash EV:

\[
\boxed{
EV=100(E[\pi]-D_{exec})-Fee
}
\]

---

# 59. Maximum Loss and Profit

\[
MaxLoss=100D_{exec}+Fee
\]

\[
MaxProfit=100(1-D_{exec})-Fee
\]

Assertions:

\[
MaxLoss>0
\]

\[
MaxProfit>0
\]

---

# 60. Probability of Profit

Bull call:

\[
BE=
K+D_{exec}+\frac{Fee}{100}
\]

\[
P_{profit}
=
\sum_iw_iI(X^*_{T,i}>BE)
\]

Bear put:

\[
BE=
K-D_{exec}-\frac{Fee}{100}
\]

\[
P_{profit}
=
\sum_iw_iI(X^*_{T,i}<BE)
\]

---

# 61. Dirichlet LCB

Frozen:

```text
B = 1000
```

\[
\alpha_i=N_{eff}w_i
\]

\[
w^{(b)}\sim Dirichlet(\alpha)
\]

Recalculate:

\[
EV^{(b)}
\]

Then:

\[
EV_{LCB}=Q_{0.05}(EV^{(b)})
\]

---

# 62. Deterministic Random Seed

Frozen base seed:

```text
BASE_RANDOM_SEED = 20260813
```

Per-session seed derives deterministically from:

```text
SHA256("OAE-v0.1.0|YYYY-MM-DD|20260813")
```

Use a stable documented conversion such as the first 32 bits.

Same data + same code + same config + same seed derivation must yield the same result.

---

# 63. Edge Gate Persistence

Persist:

```text
gate_ev
gate_ev_ratio
gate_lcb
gate_lcb_ratio
gate_pop
```

Thresholds:

\[
EV\ge5
\]

\[
EV/MaxLoss\ge0.10
\]

\[
EV_{LCB}>0
\]

\[
EV_{LCB}/MaxLoss\ge0.02
\]

\[
P_{profit}\ge0.40
\]

Final:

```text
edge_pass = AND(all five)
```

after all upstream gates pass.

---

# 64. Candidate Selection

\[
RobustScore=
\frac{EV_{LCB}}{MaxLoss}
\]

Choose the maximum score among edge-positive candidates, subject to the ambiguity rule.

---

# 65. Direction Conflict

If both best call and best put exist and:

\[
|Score_C-Score_P|<0.01
\]

then:

```text
NO_TRADE_AMBIGUOUS
```

At exactly 0.0100, the strict `< 0.01` rule does not trigger.

---

# 66. Daily Decision Table

Create:

```text
daily_decisions
```

Fields:

```text
decision_id
session_date
decision_ts

model_version
data_version

model_status

n_train
neff
ood_pass
health_pass
skill_pass

best_candidate_id

decision
primary_reason_code

expected_payoff
ev
ev_lcb
prob_profit
max_loss
max_profit
robust_score

created_at
run_id
```

Decision domain:

```text
TRADE
NO_TRADE
```

---

# 67. Frozen No-Trade Reason Codes

```text
NT_NON_FULL_SESSION
NT_NO_XSP_0DTE
NT_FOMC_AFTERNOON

NT_MISSING_SPX
NT_MISSING_SPX_CHAIN
NT_MISSING_XSP_CHAIN
NT_MISSING_SETTLEMENT

NT_STALE_QUOTE
NT_INVALID_NBBO

NT_TRAIN_LT_504
NT_HEALTH_WARMUP
NT_NEFF
NT_OOD
NT_CALIBRATION
NT_DISTRIBUTION_SKILL

NT_NO_1PT_PAIR
NT_LIQUIDITY

NT_NO_EDGE
NT_AMBIGUOUS

NT_MARKET_HALT
NT_DATA_INTEGRITY
```

May also store:

```text
all_reason_codes[]
```

but exactly one deterministic primary reason is required.

---

# 68. Gate Execution Order

Frozen primary-reason category order:

```text
1 Calendar
2 Macro
3 Raw Data
4 Feature
5 Training Readiness
6 Model Health
7 OOD
8 Distribution Skill
9 Candidate Availability
10 Liquidity
11 Edge
12 Ambiguity
13 Trade
```

---

# 69. Simulated Orders

Create:

```text
simulated_orders
```

Fields:

```text
order_id
decision_id
strategy
quantity
submit_ts
order_type
limit_price
expected_fill_price
execution_model
status
```

Frozen:

```text
quantity = 1
order_type = COMPLEX_LIMIT
limit_price = d_exec
execution_model = CONSERVATIVE_NATURAL_ONE_LOT
```

---

# 70. Simulated Fills

Create:

```text
simulated_fills
```

Fields:

```text
fill_id
order_id
fill_ts
fill_price
quantity
fee
fill_model
```

Frozen:

```text
fill_ts = decision_ts
quantity = 1
fill_price = d_exec
```

No partial fills in v0.1.

---

# 71. No Exit Engine

No:

```text
stop loss
profit target
trailing stop
intraday discretionary exit
```

Position state:

```text
OPEN -> SETTLED
```

---

# 72. Settlement P&L

Bull-call cash payoff:

\[
Payoff
=
100
\min[
\max(X_T-K,0),
1
]
\]

Bear-put cash payoff:

\[
Payoff
=
100
\min[
\max(K-X_T,0),
1
]
\]

Net P&L:

\[
\boxed{
PnL=
Payoff-100D_{exec}-Fee
}
\]

---

# 73. Trade Result Table

Create:

```text
trade_results
```

Fields:

```text
decision_id
session_date

settlement_value
gross_payoff
entry_cost
fee_total
net_pnl

return_on_max_loss
won

expected_ev
expected_ev_lcb
forecast_error

settled
```

---

# 74. Persist No-Trade Sessions

Every evaluated full session must produce a daily decision row.

Do not retain only trade days.

This is required to audit abstention frequency and No-Trade reasons.

---

# 75. Backtest Run Manifest

Create:

```text
backtest_runs
```

Fields:

```text
run_id
started_at
finished_at

model_version
feature_version
execution_version

git_commit
config_sha256
data_snapshot_sha256

start_date
end_date

random_seed
python_environment_hash

status
```

Status:

```text
SUCCESS
FAILED
```

---

# 76. Frozen Config

Use a single file:

```text
config/oae_v0_1_frozen.yaml
```

Canonical values:

```yaml
version: OAE-v0.1.0

timezone: America/New_York

decision_time: "13:30:00"

instrument:
  signal_underlying: SPX
  trade_underlying: XSP
  multiplier: 100
  settlement: PM

model:
  train_window: 756
  min_train: 504
  k: 80
  bandwidth_neighbor: 40
  recency_half_life: 252
  min_neff: 30
  feature_clip: 5.0

health:
  window: 126
  min_distribution_skill: 0.02

ood:
  percentile: 0.995

strategy:
  allowed:
    - BULL_CALL_DEBIT
    - BEAR_PUT_DEBIT
  spread_width: 1.0
  max_trades_per_day: 1
  hold_to_settlement: true

candidate:
  max_moneyness_distance: 0.005

quotes:
  max_age_seconds: 2.0
  min_bid_size: 1
  min_ask_size: 1

execution:
  tick_size: 0.01
  min_debit: 0.15
  max_debit: 0.75
  max_absolute_friction: 0.05
  max_relative_friction: 0.25
  model: CONSERVATIVE_NATURAL_ONE_LOT

fees:
  conservative_floor_usd: 3.00

edge:
  min_ev_usd: 5.00
  min_ev_over_max_loss: 0.10
  min_lcb_usd_exclusive: 0.00
  min_lcb_over_max_loss: 0.02
  min_probability_profit: 0.40

bootstrap:
  draws: 1000
  base_seed: 20260813

ambiguity:
  max_score_difference: 0.01
```

Hash the normalized config and persist the hash with official runs.

---

# 77. Walk-Forward Backtest Engine

Core conceptual class:

```text
WalkForwardBacktestEngine
```

Pseudo-order:

```python
for session in sessions:

    build_point_in_time_state(session)

    validate_calendar()

    build_features()

    load_only_prior_available_labels()

    train_model()

    generate_forecast()

    update_model_health()

    run_model_gates()

    generate_xsp_candidates()

    price_candidates()

    calculate_ev()

    select_trade_or_no_trade()

    simulate_execution()

    load_official_settlement()

    calculate_realized_pnl()

    persist_everything()
```

Random train/test split is forbidden.

---

# 78. Exact Daily Replay Order

For session \(d\):

1. load session calendar;
2. validate full-day and same-day XSP PM-expiry state;
3. construct exact 13:30 snapshot;
4. read SPX data only through 13:30;
5. read option NBBO only with `quote_ts <= 13:30`;
6. calculate x1–x11;
7. construct training set from prior sessions with available labels;
8. robust-scale;
9. run KNN;
10. generate 80 weighted settlement scenarios;
11. compute N_eff, OOD, health, and CRPS skill;
12. FOMC-blocked sessions may still persist a diagnostic forecast;
13. generate XSP candidates;
14. apply liquidity gates;
15. calculate EV, LCB, PoP;
16. rank and apply ambiguity rule;
17. persist TRADE / NO_TRADE;
18. if trade, simulate fill at D_exec;
19. only after decision persistence, read official settlement;
20. calculate realized P&L;
21. current session's label becomes training-eligible only at the frozen future availability time.

---

# 79. Mandatory Future-Leak Assertions

Examples:

```python
assert max_feature_source_ts <= decision_ts
```

```python
assert quote_ts <= decision_ts
```

```python
assert max(training_session_date) < current_session_date
```

Before decision:

```python
assert current_settlement_not_loaded
```

Historical health:

```python
assert forecast_created_from_point_in_time_data
```

An invariant failure must fail the backtest rather than silently skip the problem.

---

# 80. Missing-Data Policy

Do not impute critical market state.

Forbidden:

```text
future NBBO forward-fill
option-price interpolation
replace missing bar with next bar
replace official XSP settlement with SPX/10
```

Missing current-session inputs produce NO TRADE.

Invalid historical samples are marked as such and excluded according to the frozen eligibility rules.

---

# 81. Data Repair Policy

Only deterministic documented corrections are allowed in normalized/derived data.

Example:

- exact duplicate quote messages may be de-duplicated using stable sequence metadata.

The original raw row remains preserved.

---

# 82. Quality Flags

Use the common vocabulary:

```text
VALID
STALE
CROSSED
LOCKED
ZERO_BID
ZERO_SIZE
MISSING
OUT_OF_ORDER
DUPLICATE
HALTED
UNKNOWN
```

---

# 83. Dataset Snapshot

Formal backtests freeze their input dataset.

Create:

```text
dataset_snapshot_id
```

Include:

```text
all raw-file SHA256 values
all normalized partition SHA256 values
calendar version
event-calendar version
```

Hash the aggregate manifest to produce:

```text
data_snapshot_sha256
```

Do not modify an official run's dataset in place.

---

# 84. Deterministic Reproducibility

Required identity:

\[
\boxed{
SameCode+SameConfig+SameData+SameSeed
\Rightarrow
SameOutput
}
\]

This includes:

- neighbors;
- weights;
- scenarios;
- EV;
- EV LCB;
- decisions;
- reason codes;
- fills;
- P&L.

---

# 85. Formal Acceptance-Backtest Start

Formal performance begins only once:

```text
n_train >= 756
health_history >= 126
```

Warm-up forecasts are excluded from formal performance.

---

# 86. Backtest Metrics

Create:

```text
backtest_metrics
```

Minimum fields:

```text
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

---

# 87. Distinguish Three Return Concepts

Always separate:

1. predicted model EV;
2. gross realized P&L before fees;
3. net realized P&L after modeled costs.

Primary evidence uses:

\[
\boxed{Net}
\]

---

# 88. Formal Acceptance Conditions

Require:

\[
500
\]

formal OOS sessions and:

\[
150
\]

trade signals.

Then require:

\[
Mean(NetPnL)>0
\]

95% bootstrap CI lower bound of mean net P&L:

\[
>0
\]

Profit Factor:

\[
\ge1.20
\]

Aggregate OOS EV:

\[
>0
\]

If all pass:

```text
POTENTIAL_ALPHA
```

Otherwise:

```text
NO_VALIDATED_ALPHA
```

Do not claim historical proof of future profitability.

---

# 89. Recommended Repository Layout

```text
options-alpha-engine/
│
├── README.md
├── pyproject.toml
├── config/
│   └── oae_v0_1_frozen.yaml
│
├── src/oae/
│   ├── schemas/
│   │   ├── market.py
│   │   ├── options.py
│   │   ├── model.py
│   │   └── backtest.py
│   ├── data/
│   │   ├── adapters/
│   │   ├── ingest.py
│   │   ├── normalize.py
│   │   ├── quality.py
│   │   ├── asof.py
│   │   └── lineage.py
│   ├── calendar/
│   │   ├── sessions.py
│   │   └── macro_events.py
│   ├── features/
│   │   └── v0_1.py
│   ├── model/
│   │   ├── scaler.py
│   │   ├── knn.py
│   │   ├── distribution.py
│   │   ├── health.py
│   │   ├── crps.py
│   │   └── ood.py
│   ├── strategy/
│   │   ├── candidates.py
│   │   ├── payoff.py
│   │   ├── ev.py
│   │   └── selection.py
│   ├── execution/
│   │   ├── pricing.py
│   │   ├── fees.py
│   │   └── simulator.py
│   ├── backtest/
│   │   ├── engine.py
│   │   ├── metrics.py
│   │   └── report.py
│   └── audit/
│       ├── manifest.py
│       └── leakage.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── leakage/
│   └── regression/
├── data/
└── scripts/
```

---

# 90. Development Order

```text
Phase 1
schemas
timezone
calendar
raw manifest

Phase 2
SPX bars
option contract master
NBBO as-of engine

Phase 3
feature engine x1-x11

Phase 4
label engine

Phase 5
KNN
weights
Neff
forecast distribution

Phase 6
health
CRPS
OOD

Phase 7
candidate generator
payoff
EV
LCB

Phase 8
execution simulator

Phase 9
walk-forward backtest

Phase 10
audit/report
```

Do not begin with GUI, AI, or broker integration.

---

# 91. Mandatory Regression Tests

### Timestamp

```text
13:30:00.001 quote -> forbidden
13:29:59.999 quote -> allowed
```

### Staleness

```text
2.000s -> allowed
2.001s -> rejected
```

### Bars

```text
13:30-13:31 bar -> forbidden
```

### Training

Current session may never appear in its own training set.

### Spread Width

Bull call:

\[
K_2-K_1=1
\]

Bear put:

\[
K_1-K_2=1
\]

### Payoff

\[
0\le\pi\le1
\]

### Weights

\[
\sum_iw_i=1
\]

with error < \(10^{-12}\).

### N_eff

\[
1\le N_{eff}\le80
\]

### Execution

\[
D_{exec}\ge D_{nat}
\]

and D_exec uses the 0.01 tick.

### P&L

\[
PnL=Payoff-Cost-Fee
\]

### Determinism

Repeat the same fixture and require identical decision output hash.

---

# 92. Leakage Tests

Maintain:

```text
tests/leakage/
```

Inject intentionally invalid:

```text
13:30:01 quote
current settlement before decision
future/next-session label
future scaler observation
future bar
```

The system must reject these cases.

No-look-ahead is a product requirement.

---

# 93. Explicitly Out of Scope for v0.1

Do not add:

```text
XGBoost
LightGBM
neural networks
Transformers
reinforcement learning
LLM trading
news sentiment
order-flow model
dealer gamma
dynamic sizing
Kelly
stop loss
profit target
intraday re-entry
multiple trades/day
multi-asset options
live broker execution
dashboard optimization
```

---

# 94. Market Data Adapter Interface

All providers implement a common logical interface:

```python
class MarketDataAdapter:

    get_index_bars(...)
    get_option_contracts(...)
    get_option_nbbo(...)
    get_settlement(...)
    get_trading_calendar(...)
```

Model code must not know which provider supplied the data.

---

# 95. Required Provider Capabilities

### SPX

```text
1-minute OHLC
```

### SPX Options

```text
PM contract metadata
expiration metadata
NBBO
bid/ask sizes
actual quote timestamps
```

At least for:

```text
same-day expiry
next eligible PM expiry
```

### XSP Options

```text
same-day PM contracts
strike
call/put flag
NBBO
sizes
actual quote timestamps
```

### XSP Settlement

```text
official PM settlement
```

### Calendar

```text
full sessions
half-days
```

### FOMC

Official event timestamps needed by the event gate.

---

# 96. Decision Snapshot Dataset

Because v0.1 makes only one daily decision, a derived point-in-time decision snapshot may be precomputed from large tick datasets.

For example, a narrow raw tick window around 13:30 may be scanned to preserve the final eligible quote for each required contract.

The derived snapshot must retain actual quote timestamps.

Raw source data must not be deleted merely because a derived snapshot exists.

---

# 97. Derived As-Of Snapshot Table

Create:

```text
decision_option_snapshots
```

Fields:

```text
session_date
decision_ts
contract_id
quote_ts
quote_age_ms
bid
ask
bid_size
ask_size
quote_valid
source_quote_id
```

---

# 98. Performance Optimization Priority

\[
\boxed{
Correctness
>
PointInTimeIntegrity
>
Reproducibility
>
Performance
}
\]

A slow correct replay is preferable to a fast biased backtest.

---

# 99. Principal Engineering Risk

The principal early risk is historical point-in-time option quote quality, especially:

```text
XSP 0DTE NBBO
actual quote timestamp
bid/ask size
13:30 ET
```

Because the minimum EV threshold is only a few dollars per spread, a few cents of optimistic entry pricing can consume the modeled edge.

Data quality and execution realism are therefore first-order concerns.

---

# 100. Architecture Completion Criterion

With this specification and the Frozen Mathematical Specification:

\[
\boxed{\text{Layer 1 — Mathematical Specification}}
\]

defines what is predicted, valued, traded, and rejected.

\[
\boxed{\text{Layer 2 — Data Specification}}
\]

defines exactly which point-in-time fields produce each mathematical variable.

\[
\boxed{\text{Layer 3 — Backtest Architecture}}
\]

defines how historical decisions are replayed, executed, settled, and audited.

Once these layers are frozen, implementation can proceed without reopening theory unless a genuine inconsistency is discovered.

---

# END OF DATA SPECIFICATION + BACKTEST ARCHITECTURE
