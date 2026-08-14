# Options Alpha Engine v0.1 — Frozen Mathematical Specification

**Document ID:** OAE-MATH-v0.1.0  
**System Version:** OAE-v0.1.0  
**Status:** CANONICAL / FROZEN  
**Purpose:** Define exactly what OAE v0.1 reads, predicts, values, trades, rejects, and records.  
**Modification Policy:** No mathematical or trading-semantic change is permitted inside v0.1. Any such change requires explicit human architectural review and a new version (normally OAE v0.2).

---

## 1. Scope and First-Version Trading Definition

OAE v0.1 is a deliberately narrow quantitative research baseline.

The first version is frozen as:

- **Signal market:** SPX.
- **Trade vehicle:** XSP 0DTE options.
- **Decision epoch:** exactly **13:30:00 America/New_York** on each eligible full trading day.
- **Maximum positions:** at most **one spread per day**.
- **Position size:** exactly **one contract spread**.
- **Holding rule:** hold the position to the official same-day PM settlement.
- **Allowed strategies only:**
  1. Bull call debit vertical: `+1 C(K) - 1 C(K+1)`.
  2. Bear put debit vertical: `+1 P(K) - 1 P(K-1)`.
- **Spread width:** exactly **1.00 XSP index point**.
- **Gross maximum spread payoff:** 1.00 XSP point = $100 at multiplier 100.
- **If an exact 1-point pair does not exist:** NO TRADE.

Explicitly excluded from v0.1:

- single calls;
- single puts;
- credit spreads;
- iron condors;
- calendars;
- diagonals;
- butterflies;
- SPY options;
- single-stock options;
- multiple trades per day;
- intraday re-entry;
- stop losses;
- profit targets;
- trailing exits;
- early exits;
- averaging down;
- adding to positions;
- Kelly sizing;
- dynamic position sizing;
- live-broker routing.

The narrow scope is intentional. It minimizes degrees of freedom and makes the first backtest falsifiable.

---

## 2. Prediction Target

OAE v0.1 does **not** predict a binary up/down label.

It predicts the full conditional distribution of the same-day XSP settlement level.

At decision time \(t\):

\[
F_t(s)=P(X_T\le s\mid x_t)
\]

where:

- \(X_t\) = XSP reference level at the 13:30 ET decision time;
- \(X_T\) = official XSP PM settlement value for that expiration;
- \(x_t\) = frozen 11-dimensional market-state feature vector.

The historical terminal-return label for session \(d\) is:

\[
Y_d=\ln\left(\frac{X_{T,d}}{X_{13:30,d}}\right)
\]

The model learns a conditional distribution of \(Y_d\), then maps historical analog returns onto the current XSP reference level.

---

## 3. Allowed Raw Inputs

OAE v0.1 may read only the following information:

1. SPX 1-minute OHLC data.
2. SPX same-day (0DTE) option NBBO.
3. SPX next eligible PM-expiry option NBBO.
4. XSP same-day (0DTE) option NBBO.
5. Official XSP PM settlement values, but only after they are available as labels/outcomes.
6. Trading-session calendar.
7. FOMC decision / FOMC press-conference calendar for the explicit event gate.

No other predictive information is allowed in v0.1.

Explicitly prohibited inputs:

- news text;
- social media;
- X/Twitter;
- Reddit;
- analyst ratings;
- LLM sentiment;
- earnings text;
- proprietary order-flow signals;
- dealer-gamma estimates;
- dark-pool data;
- put/call ratio features;
- external macro forecasts;
- hand-added discretionary signals;
- extra ML-generated features.

SPX itself has no exchange volume in the ordinary stock-volume sense; therefore v0.1 does not use SPX VWAP or SPX volume features.

---

## 4. Frozen Feature Vector

At 13:30 ET define:

\[
x_t=(x_1,\ldots,x_{11})
\]

All eleven features are frozen.

Let:

- \(S_{pc}\) = previous trading session official SPX close;
- \(S_o\) = current session SPX open;
- \(S_t\) = SPX decision price at 13:30 ET;
- \(r_j\) = one-minute SPX log return;
- \(H_t\) = intraday SPX high from regular open through decision time;
- \(L_t\) = intraday SPX low from regular open through decision time;
- \(\epsilon=10^{-8}\).

### 4.1 Feature 1 — Overnight Gap

\[
x_1=\ln\left(\frac{S_o}{S_{pc}}\right)
\]

### 4.2 Feature 2 — Open-to-Now Return

\[
x_2=\ln\left(\frac{S_t}{S_o}\right)
\]

### 4.3 Feature 3 — Five-Minute Momentum

\[
x_3=\ln\left(\frac{S_t}{S_{t-5m}}\right)
\]

### 4.4 Feature 4 — Thirty-Minute Momentum

\[
x_4=\ln\left(\frac{S_t}{S_{t-30m}}\right)
\]

### 4.5 Feature 5 — Thirty-Minute Realized Volatility

Not annualized:

\[
x_5=
\sqrt{
\sum_{j=t-29}^{t}r_j^2
}
\]

where:

\[
r_j=\ln\left(\frac{S_j}{S_{j-1}}\right)
\]

### 4.6 Feature 6 — Intraday Realized Volatility

From regular open to decision time, not annualized:

\[
x_6=
\sqrt{
\sum_{j=open}^{t}r_j^2
}
\]

### 4.7 Feature 7 — Intraday Range Position

\[
x_7=
\frac{S_t-L_t}
{H_t-L_t+\epsilon}
\]

### 4.8 Feature 8 — Trend Efficiency

\[
x_8=
\frac{
\left|\ln(S_t/S_o)\right|
}{
\sum_{j=open}^{t}|r_j|+\epsilon
}
\]

### 4.9 Feature 9 — Normalized 0DTE ATM Straddle

Choose:

\[
K_{ATM}=\arg\min_K |K-S_t|
\]

using the eligible same-day SPX PM-expiry option chain.

Let:

\[
C_{ATM}^{mid}=\frac{Bid_C+Ask_C}{2}
\]

\[
P_{ATM}^{mid}=\frac{Bid_P+Ask_P}{2}
\]

Then:

\[
x_9=
\frac{
C_{ATM}^{mid}+P_{ATM}^{mid}
}{
S_t
}
\]

### 4.10 Feature 10 — Price-Based Downside Skew

Choose:

\[
K^- \approx 0.995S_t
\]

as the nearest listed put strike and:

\[
K^+ \approx 1.005S_t
\]

as the nearest listed call strike.

Then:

\[
x_{10}
=
\frac{
P^{mid}(K^-)-C^{mid}(K^+)
}{
C_{ATM}^{mid}+P_{ATM}^{mid}
}
\]

This is deliberately price-based. v0.1 does not invert option prices to implied volatility or delta for this feature.

### 4.11 Feature 11 — Short-Term Option Term Structure

For same-day PM expiry \(e_0\):

\[
M_0=
\frac{
C_{ATM,0}^{mid}+P_{ATM,0}^{mid}
}{
S_t
}
\]

For the next eligible PM expiry \(e_1\):

\[
M_1=
\frac{
C_{ATM,1}^{mid}+P_{ATM,1}^{mid}
}{
S_t
}
\]

Let \(\tau_0,\tau_1\) be calendar time to their PM reference timestamps.

Then:

\[
x_{11}
=
\frac{M_0}{\sqrt{\tau_0}}
-
\frac{M_1}{\sqrt{\tau_1}}
\]

This is also price-based and deliberately avoids a Black-Scholes implied-volatility inversion.

---

## 5. Why v0.1 Does Not Use Black-Scholes for Trade Valuation

The v0.1 strategy is:

- same-day;
- defined-risk;
- opened once;
- held to settlement.

Therefore the terminal payoff of every permitted position is exactly determined by \(X_T\).

Option prices are used for:

- market-state features;
- entry execution prices.

They are not required for pre-expiry revaluation because v0.1 has no dynamic exit.

The valuation problem is therefore:

\[
P(X_T\mid x_t)
\rightarrow
E[\text{terminal payoff}]
\rightarrow
EV
\]

rather than predicting a future option mark.

No Black-Scholes pricing model is required to define v0.1 trade EV.

---

## 6. Prediction Engine — Kernel-Weighted Historical Analog Model

OAE v0.1 deliberately uses a transparent historical-analog engine rather than XGBoost, neural networks, Transformers, or reinforcement learning.

### 6.1 Training Window

Normal rolling training window:

\[
N_{train}=756
\]

prior full valid sessions.

Minimum history:

\[
N_{min}=504
\]

If fewer than 504 valid historical sessions exist:

\[
\boxed{\text{SHADOW ONLY / MODEL NOT READY}}
\]

No official trade signal may be generated.

### 6.2 Robust Scaling

For each feature \(j\) on the current training window:

\[
Median_j=\operatorname{Median}(x_{i,j})
\]

\[
MAD_j=
\operatorname{Median}
\left(
|x_{i,j}-Median_j|
\right)
\]

Standardized feature:

\[
z_j=
\frac{
x_j-Median_j
}{
1.4826MAD_j+10^{-8}
}
\]

Each standardized feature is clipped:

\[
z_j\in[-5,5]
\]

All scaling parameters must be fit using prior training data only.

### 6.3 Distance

All eleven features use equal frozen weight.

For historical session \(i\):

\[
d_i=
\sqrt{
\sum_{j=1}^{11}
(z_{t,j}-z_{i,j})^2
}
\]

### 6.4 Number of Neighbors

Frozen:

\[
k=80
\]

Sort:

\[
d_{(1)}\le\ldots\le d_{(80)}
\]

### 6.5 Kernel Bandwidth

Frozen bandwidth anchor:

\[
h=d_{(40)}
\]

If \(h=0\), use:

\[
h=10^{-8}
\]

### 6.6 Similarity Weight

\[
w_i^{sim}
=
\exp
\left[
-\frac12
\left(\frac{d_i}{h}\right)^2
\right]
\]

### 6.7 Recency Weight

Historical-session age is measured in trading sessions.

Half-life:

\[
252
\]

sessions.

\[
w_i^{time}
=
\exp
\left[
-\ln(2)\frac{Age_i}{252}
\right]
\]

### 6.8 Final Weight

\[
\tilde w_i=w_i^{sim}w_i^{time}
\]

Normalize:

\[
w_i=
\frac{\tilde w_i}
{\sum_j\tilde w_j}
\]

with:

\[
\sum_iw_i=1
\]

### 6.9 Effective Sample Size

\[
N_{eff}
=
\frac{1}{\sum_iw_i^2}
\]

Required:

\[
\boxed{N_{eff}\ge30}
\]

Otherwise:

\[
\boxed{\text{NO TRADE}}
\]

---

## 7. Predictive Settlement Distribution

Each selected historical neighbor has historical label \(Y_i\).

Map that return onto today's XSP reference level:

\[
X^*_{T,i}
=
X_t e^{Y_i}
\]

The predictive weighted empirical CDF is:

\[
F_t(s)
=
\sum_{i=1}^{80}
w_i
\mathbf{1}
(X^*_{T,i}\le s)
\]

This 80-scenario weighted settlement distribution is the sole basis for v0.1 option EV.

---

## 8. Out-of-Distribution Gate

Inside each training window:

1. For each historical training observation, perform leave-one-out nearest-neighbor calculation.
2. Compute its distance to its 80th nearest neighbor.
3. Form the empirical distribution of those \(d_{80}\) values.
4. Calculate:

\[
Q_{99.5}(d_{80})
\]

For today's state calculate:

\[
d_{80,t}
\]

If:

\[
d_{80,t}>Q_{99.5}(d_{80})
\]

then:

\[
\boxed{\text{NO TRADE: OOD}}
\]

---

## 9. XSP Candidate Universe

Use the XSP same-day PM-expiry chain at 13:30 ET.

Define current XSP reference:

\[
X_t=\frac{S_t}{10}
\]

A long-leg strike \(K\) is eligible only if:

\[
\left|
\frac{K}{X_t}-1
\right|
\le0.005
\]

Generate only exact 1-point verticals.

### 9.1 Bull Call Debit Candidate

\[
+C(K)-C(K+1)
\]

### 9.2 Bear Put Debit Candidate

\[
+P(K)-P(K-1)
\]

If the exact paired strike is unavailable, that candidate does not exist.

---

## 10. Quote and Liquidity Validity

A candidate requires valid 13:30 point-in-time NBBO for both legs.

For each required quote:

- Bid > 0.
- Ask > Bid.
- Bid size ≥ 1.
- Ask size ≥ 1.
- Quote age ≤ 2.000 seconds.
- Quote timestamp ≤ decision timestamp.
- No stale, crossed, invalid, or halted-market condition.

Failure makes the candidate invalid.

---

## 11. Entry Pricing and Execution Model

The backtest must never use package midpoint as the assumed fill.

### 11.1 Natural Debit

\[
D_{nat}
=
Ask_{long}-Bid_{short}
\]

### 11.2 Package Mid

\[
D_{mid}
=
Mid_{long}-Mid_{short}
\]

where:

\[
Mid=\frac{Bid+Ask}{2}
\]

### 11.3 Frozen Net Tick

\[
tick=0.01
\]

### 11.4 Conservative Executable Debit

\[
D_{exec}
=
\left\lceil
\frac{D_{nat}}{0.01}
\right\rceil
0.01
\]

### 11.5 Spread Friction

\[
F_{spread}=D_{exec}-D_{mid}
\]

Candidate liquidity gates:

\[
0.15\le D_{exec}\le0.75
\]

\[
F_{spread}\le0.05
\]

\[
\frac{F_{spread}}{D_{exec}}\le0.25
\]

Both legs must also pass all quote validity rules.

This is a conservative one-lot simulated execution model, not a claim that a historical complex order actually filled.

---

## 12. Fee Rule

Let `Fee_actual` denote a correctly reconstructed all-in opening cost if historical fee data are available.

Frozen research fee:

\[
Fee=\max(Fee_{actual},\$3.00)
\]

If accurate historical fee reconstruction is unavailable:

\[
\boxed{Fee=\$3.00}
\]

The $3 value is a conservative research reserve, not a claim that actual fees are always exactly $3.

---

## 13. Exact Expiry Payoffs

XSP multiplier:

\[
100
\]

### 13.1 Bull Call Debit Spread

\[
\pi_C(X_T)
=
\min
\left(
\max(X_T-K,0),
1
\right)
\]

Cash payoff:

\[
100\pi_C(X_T)
\]

### 13.2 Bear Put Debit Spread

\[
\pi_P(X_T)
=
\min
\left(
\max(K-X_T,0),
1
\right)
\]

Cash payoff:

\[
100\pi_P(X_T)
\]

For every permitted position:

\[
0\le\pi\le1
\]

---

## 14. Expected Payoff and Expected Value

For candidate \(c\):

\[
E[\pi_c]
=
\sum_iw_i\pi_c(X^*_{T,i})
\]

Net expected value in dollars:

\[
\boxed{
EV_c
=
100(E[\pi_c]-D_{exec,c})-Fee
}
\]

Maximum loss:

\[
MaxLoss_c
=
100D_{exec,c}+Fee
\]

Maximum profit:

\[
MaxProfit_c
=
100(1-D_{exec,c})-Fee
\]

Expected return on maximum loss:

\[
EROML_c
=
\frac{EV_c}{MaxLoss_c}
\]

---

## 15. Probability of Profit

### 15.1 Bull Call Breakeven

\[
BE_C
=
K+D_{exec}+\frac{Fee}{100}
\]

\[
P_{profit,C}
=
\sum_i
w_i
\mathbf{1}
(X^*_{T,i}>BE_C)
\]

### 15.2 Bear Put Breakeven

\[
BE_P
=
K-D_{exec}-\frac{Fee}{100}
\]

\[
P_{profit,P}
=
\sum_i
w_i
\mathbf{1}
(X^*_{T,i}<BE_P)
\]

---

## 16. Trade-Level EV Uncertainty — Dirichlet Reweighting

Frozen draw count:

\[
B=1000
\]

For each draw:

\[
w^{(b)}
\sim
Dirichlet(N_{eff}w)
\]

Recompute candidate EV:

\[
EV_c^{(b)}
\]

Define one-sided 95% lower confidence bound:

\[
\boxed{
EV_{LCB,c}
=
Q_{5\%}
\left\{
EV_c^{(1)},\ldots,EV_c^{(1000)}
\right\}
}
\]

The simulation seed must be deterministic for reproducibility.

This LCB is a local uncertainty measure for the weighted analog distribution and does not claim to capture every source of model uncertainty or serial dependence.

---

## 17. Formal Edge Definition

A candidate has `EDGE=TRUE` only if **all** of the following hold:

\[
EV_c\ge \$5
\]

\[
\frac{EV_c}{MaxLoss_c}\ge10\%
\]

\[
EV_{LCB,c}>0
\]

\[
\frac{EV_{LCB,c}}{MaxLoss_c}\ge2\%
\]

\[
P_{profit,c}\ge40\%
\]

and all data, session, model-health, OOD, \(N_{eff}\), quote, and liquidity gates pass.

The objective is positive net expected value, not maximizing win rate.

---

## 18. Model Health Gate

Use the most recent:

\[
126
\]

valid full out-of-sample forecast sessions.

Each historical forecast must have been generated strictly with information available at its original decision time.

### 18.1 Quantile Calibration

10% quantile empirical coverage:

\[
0.05\le Coverage_{Q10}\le0.15
\]

Median coverage:

\[
0.43\le Coverage_{Q50}\le0.57
\]

90% quantile coverage:

\[
0.85\le Coverage_{Q90}\le0.95
\]

Failure of any band:

\[
\boxed{\text{MODEL DISABLED / NO TRADE}}
\]

### 18.2 Conditional Distribution Skill

For weighted empirical outcomes \(y_i\), weights \(w_i\), realized \(y\):

\[
CRPS(F,y)
=
\sum_iw_i|y_i-y|
-
\frac12
\sum_i\sum_jw_iw_j|y_i-y_j|
\]

The unconditional baseline uses the same rolling return history but ignores features and assigns equal weights.

Over the model-health window:

\[
DistributionSkill
=
1-
\frac{CRPS_{OAE}}
{CRPS_{baseline}}
\]

Required:

\[
\boxed{DistributionSkill\ge2\%}
\]

Otherwise NO TRADE.

The 126-session calibration bands and 2% CRPS threshold are frozen ex-ante heuristic design thresholds and are not claimed to be mathematically optimal.

---

## 19. Candidate Ranking

For each candidate that passes all Edge conditions:

\[
RobustScore_c
=
\frac{EV_{LCB,c}}{MaxLoss_c}
\]

Choose:

\[
c^*
=
\arg\max_c RobustScore_c
\]

At most one contract spread is selected.

---

## 20. Directional Ambiguity Rule

If both best call and best put candidates pass Edge and:

\[
|Score_C-Score_P|<0.01
\]

then:

\[
\boxed{\text{NO TRADE: AMBIGUOUS}}
\]

Otherwise the higher-score candidate may be selected, subject to all other gates.

---

## 21. Hard No-Trade Conditions

Any one of the following produces NO TRADE:

1. Non-full US equity trading session.
2. Half-day session.
3. No suitable XSP same-day PM expiry.
4. Scheduled FOMC decision or FOMC press conference overlaps 13:30–16:00 ET.
5. Required SPX or XSP data missing.
6. Required quote stale beyond 2 seconds.
7. Invalid/crossed/locked-under-frozen-rule/zero-bid/otherwise abnormal required NBBO.
8. Market halt affecting required market state.
9. Fewer than 504 valid historical sessions.
10. \(N_{eff}<30\).
11. OOD gate fails.
12. Model-health calibration fails.
13. DistributionSkill < 2%.
14. No exact 1-point candidate pair.
15. Liquidity gate fails for every candidate.
16. No candidate satisfies the formal Edge definition.
17. Call/put ambiguity rule triggers.

NO TRADE is a first-class strategy output, not an error.

---

## 22. No Stop Loss in v0.1

The absence of a stop loss is deliberate.

Each permitted debit spread already has defined maximum loss.

Adding a stop makes realized P&L path-dependent:

\[
P(X_{t_1},X_{t_2},\ldots,X_T)
\]

rather than terminal-state dependent:

\[
P(X_T)
\]

and introduces exit-price modeling, intraday path modeling, additional quote requirements, and extra tuning degrees of freedom.

Dynamic exits are reserved for a later version.

---

## 23. Daily Decision Record

Every evaluated session must persist at least:

### Identity
- OAE version.
- Session date.
- Decision timestamp.

### Model Status
- \(N_{train}\).
- \(N_{eff}\).
- OOD status.
- DistributionSkill.
- Q10/Q50/Q90 calibration.

### Best Candidate, if one exists
- strategy type;
- long strike;
- short strike;
- natural debit;
- executable debit;
- spread friction;
- fee.

### Model Metrics
- expected payoff;
- expected net P&L;
- EV / MaxLoss;
- 95% EV LCB;
- LCB / MaxLoss;
- probability of profit;
- maximum profit;
- maximum loss.

### Decision
- TRADE or NO_TRADE;
- machine-readable reason code.

The system must never output an unsupported bare instruction such as "BUY CALL" without quantified rationale.

---

## 24. Walk-Forward Research Discipline

For testing session \(d\):

- only data available by that session's 13:30 decision timestamp may enter features;
- only labels from sessions before \(d\) that were already available may enter training;
- current settlement must remain inaccessible until after the decision is persisted;
- historical 13:30 option quotes must be point-in-time;
- scaling must use prior training data only;
- strike selection must use only the current 13:30 chain;
- no future close, high, low, IV, settlement, or later quote may leak into the decision.

Forbidden:

- random train/test split;
- whole-sample normalization;
- hindsight strike selection;
- current-day settlement in training;
- future quote selection;
- future labels;
- tuning thresholds after reviewing full-sample results while still calling the result v0.1.

After official settlement the system may append the realized outcome and the new label, subject to the frozen label-availability rule.

---

## 25. Frozen-Rule Discipline

Operational data may grow over time. Implementation bugs may be fixed if the fix restores compliance with this specification.

The following may not change within v0.1 without explicit versioning:

- feature definitions;
- number of features;
- 13:30 decision time;
- instrument universe;
- strategy type;
- spread width;
- model class;
- training-window length;
- k;
- bandwidth rule;
- recency half-life;
- \(N_{eff}\) threshold;
- OOD percentile;
- calibration bands;
- CRPS skill threshold;
- liquidity thresholds;
- fee floor;
- EV threshold;
- EV/MaxLoss threshold;
- EV LCB threshold;
- LCB/MaxLoss threshold;
- probability-of-profit threshold;
- ambiguity threshold;
- hold-to-settlement rule.

A mathematical or trading-semantic change becomes a new version, normally v0.2.

---

## 26. Historical Alpha Acceptance Gate

Require at least:

\[
500
\]

formal out-of-sample sessions and at least:

\[
150
\]

actual trade signals.

Required:

\[
Mean(NetPnL)>0
\]

95% bootstrap confidence interval lower bound of mean net P&L:

\[
CI_{95\%,lower}>0
\]

Profit Factor:

\[
ProfitFactor\ge1.20
\]

and aggregate out-of-sample expected value:

\[
>0
\]

If all pass, research status may be:

`POTENTIAL_ALPHA`

Otherwise:

`NO_VALIDATED_ALPHA`

Historical results are not proof of future profitability.

---

## 27. Post-Backtest Progression

Even after historical acceptance:

1. historical walk-forward replay;
2. model and leakage audit;
3. live shadow mode;
4. at least 60 live/shadow signals;
5. compare modeled executable price with actually fillable market price;
6. only then consider tiny-capital pilot testing;
7. only after further evidence consider position sizing.

Position sizing is outside v0.1.

---

## 28. Research Question

OAE v0.1 exists to answer:

> Does a simple, transparent, point-in-time historical-analog model of the SPX/XSP same-day settlement distribution identify XSP 1-point 0DTE debit spreads whose conservative after-cost expected value is persistently positive out of sample?

The system is allowed to answer NO.

A valid negative result is preferable to manufacturing apparent profitability through extra tuning, optimistic fills, leakage, or model complexity.

---

# END OF FROZEN MATHEMATICAL SPECIFICATION
