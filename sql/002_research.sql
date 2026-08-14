CREATE SCHEMA IF NOT EXISTS research;

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

CREATE TABLE research.model_samples (
    session_date_et DATE PRIMARY KEY,
    decision_spx_px DECIMAL(18,6) NOT NULL,
    decision_xsp_reference_px DECIMAL(18,6) NOT NULL,
    settlement_xsp DECIMAL(18,6),
    terminal_log_return DOUBLE,
    label_available_from TIMESTAMPTZ,
    label_valid BOOLEAN NOT NULL
);

CREATE TABLE research.model_scaler_snapshots (
    session_date_et DATE NOT NULL,
    feature_name VARCHAR NOT NULL,
    median DOUBLE NOT NULL,
    mad DOUBLE NOT NULL,
    scale_denominator DOUBLE NOT NULL,

    PRIMARY KEY(session_date_et, feature_name)
);

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
    code_commit VARCHAR,

    k INTEGER NOT NULL,
    created_ts TIMESTAMPTZ NOT NULL
);

CREATE TABLE research.forecast_scenarios (
    forecast_id VARCHAR NOT NULL,
    scenario_rank INTEGER NOT NULL,
    historical_session DATE NOT NULL,
    terminal_log_return DOUBLE NOT NULL,
    scenario_weight DOUBLE NOT NULL,
    projected_xsp_settlement DOUBLE NOT NULL,

    PRIMARY KEY(forecast_id, scenario_rank)
);

CREATE TABLE research.forecast_neighbors (
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
);

CREATE TABLE research.forecast_evaluations (
    forecast_id VARCHAR PRIMARY KEY,
    realized_y DOUBLE NOT NULL,
    evaluated_ts_utc TIMESTAMPTZ NOT NULL
);

CREATE TABLE research.option_candidates (
    candidate_id VARCHAR PRIMARY KEY,
    forecast_id VARCHAR NOT NULL,
    strategy_type VARCHAR NOT NULL,

    long_contract_id VARCHAR NOT NULL,
    short_contract_id VARCHAR NOT NULL,

    long_strike DECIMAL(18,4) NOT NULL,
    short_strike DECIMAL(18,4) NOT NULL,

    d_mid DECIMAL(18,6),
    d_natural DECIMAL(18,6),
    d_exec DECIMAL(18,6),
    spread_friction DECIMAL(18,6),

    fee DECIMAL(18,6),
    max_loss DECIMAL(18,6),
    max_profit DECIMAL(18,6),

    expected_payoff DOUBLE,
    ev DOUBLE,
    ev_over_max_loss DOUBLE,
    ev_lcb DOUBLE,
    lcb_over_max_loss DOUBLE,
    probability_profit DOUBLE,
    robust_score DOUBLE,

    liquidity_pass BOOLEAN,
    edge_pass BOOLEAN,

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
);

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
    max_loss DECIMAL(18,6),
    robust_score DOUBLE,

    run_id VARCHAR NOT NULL,

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
);

CREATE TABLE research.simulated_orders (
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
);

CREATE TABLE research.simulated_fills (
    fill_id VARCHAR PRIMARY KEY,
    order_id VARCHAR NOT NULL,
    fill_ts_utc TIMESTAMPTZ NOT NULL,
    fill_price DECIMAL(18,6) NOT NULL,
    quantity INTEGER NOT NULL,
    fee DECIMAL(18,6) NOT NULL,
    fee_source VARCHAR NOT NULL,
    fill_model VARCHAR NOT NULL
);

CREATE TABLE research.trade_results (
    decision_id VARCHAR PRIMARY KEY,

    settlement_value DECIMAL(18,6),
    gross_payoff DECIMAL(18,6),

    entry_cost DECIMAL(18,6) NOT NULL,
    fee_total DECIMAL(18,6) NOT NULL,

    net_pnl DECIMAL(18,6),
    return_on_max_loss DOUBLE,
    won BOOLEAN,

    session_date_et DATE NOT NULL,
    expected_ev DOUBLE NOT NULL,
    expected_ev_lcb DOUBLE NOT NULL,
    settled BOOLEAN NOT NULL
);
