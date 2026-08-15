CREATE SCHEMA IF NOT EXISTS audit;

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
    python_environment_hash VARCHAR NOT NULL,

    status VARCHAR NOT NULL
        CHECK(status IN ('SUCCESS','FAILED'))
);

CREATE TABLE audit.backtest_metrics (
    run_id VARCHAR PRIMARY KEY,

    n_sessions BIGINT NOT NULL,
    n_trade_signals BIGINT NOT NULL,
    n_no_trade BIGINT NOT NULL,
    trade_frequency DOUBLE NOT NULL,

    gross_pnl DECIMAL(18,6) NOT NULL,
    net_pnl DECIMAL(18,6) NOT NULL,

    mean_pnl DOUBLE NOT NULL,
    median_pnl DOUBLE NOT NULL,

    win_rate DOUBLE NOT NULL,
    avg_win DOUBLE NOT NULL,
    avg_loss DOUBLE NOT NULL,

    profit_factor DOUBLE NOT NULL,

    ev_predicted_mean DOUBLE NOT NULL,
    ev_realized_mean DOUBLE NOT NULL,

    max_drawdown DECIMAL(18,6) NOT NULL,

    sharpe DOUBLE NOT NULL,
    sortino DOUBLE NOT NULL,

    largest_win DECIMAL(18,6) NOT NULL,
    largest_loss DECIMAL(18,6) NOT NULL,

    call_spread_count BIGINT NOT NULL,
    put_spread_count BIGINT NOT NULL,

    calibration_q10 DOUBLE NOT NULL,
    calibration_q50 DOUBLE NOT NULL,
    calibration_q90 DOUBLE NOT NULL,

    distribution_skill DOUBLE NOT NULL,

    mean_net_pnl_ci_lower_95 DOUBLE NOT NULL,
    aggregate_oos_ev DOUBLE NOT NULL,

    acceptance_result VARCHAR NOT NULL
        CHECK(
            acceptance_result IN (
                'POTENTIAL_ALPHA',
                'NO_VALIDATED_ALPHA'
            )
        )
);
