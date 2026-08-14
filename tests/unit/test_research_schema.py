from collections.abc import Iterator, Sequence
from pathlib import Path

import duckdb
import pytest

from oae.db import open_database


CORE_SQL_PATH = Path("sql/001_core.sql")
RESEARCH_SQL_PATH = Path("sql/002_research.sql")

CORE_TABLES = {
    ("core", "decision_option_snapshots"),
    ("core", "fee_schedules"),
    ("core", "index_bars_1m"),
    ("core", "index_sessions"),
    ("core", "macro_events"),
    ("core", "option_contracts"),
    ("core", "option_nbbo"),
    ("core", "option_settlements"),
    ("core", "trading_sessions"),
    ("meta", "raw_file_manifest"),
}

RESEARCH_TABLES = {
    "daily_decisions",
    "feature_snapshots",
    "forecast_evaluations",
    "forecast_neighbors",
    "forecast_runs",
    "forecast_scenarios",
    "model_samples",
    "model_scaler_snapshots",
    "option_candidates",
    "simulated_fills",
    "simulated_orders",
    "trade_results",
}


def apply_research_migrations(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    for path in (CORE_SQL_PATH, RESEARCH_SQL_PATH):
        connection.execute(path.read_text(encoding="utf-8"))


@pytest.fixture
def migrated_connection(
    tmp_path: Path,
) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = open_database(tmp_path / "research_schema.duckdb")
    try:
        apply_research_migrations(connection)
        yield connection
    finally:
        connection.close()


def _column_contract(
    connection: duckdb.DuckDBPyConnection,
    table: str,
) -> list[tuple[str, str, bool]]:
    rows = connection.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'research' AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table],
    ).fetchall()
    return [
        (column_name, data_type, is_nullable == "YES")
        for column_name, data_type, is_nullable in rows
    ]


def _assert_column_contract(
    connection: duckdb.DuckDBPyConnection,
    table: str,
    expected: Sequence[tuple[str, str, bool]],
) -> None:
    assert _column_contract(connection, table) == list(expected)


def _primary_key_columns(
    connection: duckdb.DuckDBPyConnection,
    table: str,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_catalog = kcu.constraint_catalog
         AND tc.constraint_schema = kcu.constraint_schema
         AND tc.constraint_name = kcu.constraint_name
        WHERE tc.table_schema = 'research'
          AND tc.table_name = ?
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
        """,
        [table],
    ).fetchall()
    return [column_name for (column_name,) in rows]


def _insert_daily_decision(
    connection: duckdb.DuckDBPyConnection,
    decision_id: str,
    decision: str,
) -> None:
    connection.execute(
        """
        INSERT INTO research.daily_decisions (
            decision_id,
            session_date_et,
            decision_ts_utc,
            model_version,
            decision,
            primary_reason_code,
            run_id,
            data_snapshot_sha256,
            model_status,
            created_at
        ) VALUES (
            ?, DATE '2026-08-14',
            TIMESTAMPTZ '2026-08-14 17:30:00+00',
            'OAE-v0.1.0', ?, 'TEST_REASON', 'run-1', 'data-sha',
            'TEST_STATUS', TIMESTAMPTZ '2026-08-14 17:30:01+00'
        )
        """,
        [decision_id, decision],
    )


def test_research_migrations_execute_successfully(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    assert migrated_connection.execute("SELECT 1").fetchone() == (1,)


def test_exact_application_schema_set_without_audit(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    schemas = {
        schema_name
        for (schema_name,) in migrated_connection.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name IN ('meta', 'core', 'research', 'audit')
            """
        ).fetchall()
    }

    assert schemas == {"meta", "core", "research"}


def test_exact_research_table_set(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    tables = {
        table_name
        for (table_name,) in migrated_connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'research'
              AND table_type = 'BASE TABLE'
            """
        ).fetchall()
    }

    assert tables == RESEARCH_TABLES


def test_total_application_table_count_is_twenty_two(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    count = migrated_connection.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema IN ('meta', 'core', 'research', 'audit')
          AND table_type = 'BASE TABLE'
        """
    ).fetchone()

    assert count == (22,)


def test_core_persistence_table_set_remains_unchanged(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    tables = set(
        migrated_connection.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('meta', 'core')
              AND table_type = 'BASE TABLE'
            """
        ).fetchall()
    )

    assert tables == CORE_TABLES


def test_feature_snapshots_contract_and_physical_aliases(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "feature_snapshots",
        [
            ("session_date_et", "DATE", False),
            ("feature_version", "VARCHAR", False),
            ("decision_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("x1", "DOUBLE", False),
            ("x2", "DOUBLE", False),
            ("x3", "DOUBLE", False),
            ("x4", "DOUBLE", False),
            ("x5", "DOUBLE", False),
            ("x6", "DOUBLE", False),
            ("x7", "DOUBLE", False),
            ("x8", "DOUBLE", False),
            ("x9", "DOUBLE", False),
            ("x10", "DOUBLE", False),
            ("x11", "DOUBLE", False),
            ("feature_valid", "BOOLEAN", False),
            ("invalid_reason", "VARCHAR", True),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "feature_snapshots"
    ) == ["session_date_et"]

    column_names = {name for name, _, _ in _column_contract(
        migrated_connection, "feature_snapshots"
    )}
    semantic_names = {
        "x1_overnight_gap",
        "x2_open_to_now",
        "x3_momentum_5m",
        "x4_momentum_30m",
        "x5_rv_30m",
        "x6_rv_intraday",
        "x7_range_position",
        "x8_trend_efficiency",
        "x9_atm_straddle_move",
        "x10_downside_skew",
        "x11_term_structure",
    }
    assert column_names.isdisjoint(semantic_names)


def test_model_samples_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "model_samples",
        [
            ("session_date_et", "DATE", False),
            ("decision_spx_px", "DECIMAL(18,6)", False),
            ("decision_xsp_reference_px", "DECIMAL(18,6)", False),
            ("settlement_xsp", "DECIMAL(18,6)", True),
            ("terminal_log_return", "DOUBLE", True),
            ("label_available_from", "TIMESTAMP WITH TIME ZONE", True),
            ("label_valid", "BOOLEAN", False),
        ],
    )
    assert _primary_key_columns(migrated_connection, "model_samples") == [
        "session_date_et"
    ]


def test_model_scaler_snapshots_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "model_scaler_snapshots",
        [
            ("session_date_et", "DATE", False),
            ("feature_name", "VARCHAR", False),
            ("median", "DOUBLE", False),
            ("mad", "DOUBLE", False),
            ("scale_denominator", "DOUBLE", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "model_scaler_snapshots"
    ) == ["session_date_et", "feature_name"]


def test_forecast_runs_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "forecast_runs",
        [
            ("forecast_id", "VARCHAR", False),
            ("session_date_et", "DATE", False),
            ("model_version", "VARCHAR", False),
            ("n_train", "INTEGER", False),
            ("neff", "DOUBLE", True),
            ("d40", "DOUBLE", True),
            ("d80_today", "DOUBLE", True),
            ("ood_threshold", "DOUBLE", True),
            ("q10", "DOUBLE", True),
            ("q25", "DOUBLE", True),
            ("q50", "DOUBLE", True),
            ("q75", "DOUBLE", True),
            ("q90", "DOUBLE", True),
            ("distribution_skill", "DOUBLE", True),
            ("ood_pass", "BOOLEAN", True),
            ("health_pass", "BOOLEAN", True),
            ("config_sha256", "VARCHAR", False),
            ("data_snapshot_sha256", "VARCHAR", True),
            ("code_commit", "VARCHAR", True),
            ("k", "INTEGER", False),
            ("created_ts", "TIMESTAMP WITH TIME ZONE", False),
        ],
    )
    assert _primary_key_columns(migrated_connection, "forecast_runs") == [
        "forecast_id"
    ]
    assert "data_snapshot_hash" not in {
        name for name, _, _ in _column_contract(
            migrated_connection, "forecast_runs"
        )
    }


def test_incomplete_diagnostic_forecast_remains_storable(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    migrated_connection.execute(
        """
        INSERT INTO research.forecast_runs (
            forecast_id,
            session_date_et,
            model_version,
            n_train,
            config_sha256,
            k,
            created_ts
        ) VALUES (
            'warmup-forecast', DATE '2026-08-14', 'OAE-v0.1.0', 1,
            'config-sha', 17, TIMESTAMPTZ '2026-08-14 17:30:01+00'
        )
        """
    )

    row = migrated_connection.execute(
        """
        SELECT neff, d40, d80_today, ood_threshold,
               q10, q25, q50, q75, q90,
               distribution_skill, ood_pass, health_pass,
               data_snapshot_sha256, code_commit
        FROM research.forecast_runs
        WHERE forecast_id = 'warmup-forecast'
        """
    ).fetchone()
    assert row == (None,) * 14


def test_forecast_scenarios_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "forecast_scenarios",
        [
            ("forecast_id", "VARCHAR", False),
            ("scenario_rank", "INTEGER", False),
            ("historical_session", "DATE", False),
            ("terminal_log_return", "DOUBLE", False),
            ("scenario_weight", "DOUBLE", False),
            ("projected_xsp_settlement", "DOUBLE", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "forecast_scenarios"
    ) == ["forecast_id", "scenario_rank"]


def test_forecast_neighbors_full_weight_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "forecast_neighbors",
        [
            ("forecast_id", "VARCHAR", False),
            ("neighbor_rank", "INTEGER", False),
            ("neighbor_session_date", "DATE", False),
            ("distance", "DOUBLE", False),
            ("terminal_return", "DOUBLE", False),
            ("age_sessions", "INTEGER", False),
            ("normalized_weight", "DOUBLE", False),
            ("similarity_weight_raw", "DOUBLE", False),
            ("recency_weight", "DOUBLE", False),
            ("combined_weight_raw", "DOUBLE", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "forecast_neighbors"
    ) == ["forecast_id", "neighbor_rank"]


def test_forecast_evaluations_contract_without_quantile_duplication(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "forecast_evaluations",
        [
            ("forecast_id", "VARCHAR", False),
            ("realized_y", "DOUBLE", False),
            ("evaluated_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "forecast_evaluations"
    ) == ["forecast_id"]
    assert {"q10", "q50", "q90"}.isdisjoint(
        name for name, _, _ in _column_contract(
            migrated_connection, "forecast_evaluations"
        )
    )


def test_option_candidates_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "option_candidates",
        [
            ("candidate_id", "VARCHAR", False),
            ("forecast_id", "VARCHAR", False),
            ("strategy_type", "VARCHAR", False),
            ("long_contract_id", "VARCHAR", False),
            ("short_contract_id", "VARCHAR", False),
            ("long_strike", "DECIMAL(18,4)", False),
            ("short_strike", "DECIMAL(18,4)", False),
            ("d_mid", "DECIMAL(18,6)", True),
            ("d_natural", "DECIMAL(18,6)", True),
            ("d_exec", "DECIMAL(18,6)", True),
            ("spread_friction", "DECIMAL(18,6)", True),
            ("fee", "DECIMAL(18,6)", True),
            ("max_loss", "DECIMAL(18,6)", True),
            ("max_profit", "DECIMAL(18,6)", True),
            ("expected_payoff", "DOUBLE", True),
            ("ev", "DOUBLE", True),
            ("ev_over_max_loss", "DOUBLE", True),
            ("ev_lcb", "DOUBLE", True),
            ("lcb_over_max_loss", "DOUBLE", True),
            ("probability_profit", "DOUBLE", True),
            ("robust_score", "DOUBLE", True),
            ("liquidity_pass", "BOOLEAN", True),
            ("edge_pass", "BOOLEAN", True),
            ("session_date_et", "DATE", False),
            ("long_bid", "DECIMAL(18,6)", True),
            ("long_ask", "DECIMAL(18,6)", True),
            ("short_bid", "DECIMAL(18,6)", True),
            ("short_ask", "DECIMAL(18,6)", True),
            ("long_quote_ts_utc", "TIMESTAMP WITH TIME ZONE", True),
            ("short_quote_ts_utc", "TIMESTAMP WITH TIME ZONE", True),
            ("candidate_valid", "BOOLEAN", False),
            ("gate_ev", "BOOLEAN", True),
            ("gate_ev_ratio", "BOOLEAN", True),
            ("gate_lcb", "BOOLEAN", True),
            ("gate_lcb_ratio", "BOOLEAN", True),
            ("gate_pop", "BOOLEAN", True),
            ("fee_source", "VARCHAR", True),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "option_candidates"
    ) == ["candidate_id"]


def test_invalid_option_candidate_with_incomplete_evidence_is_storable(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    migrated_connection.execute(
        """
        INSERT INTO research.option_candidates (
            candidate_id,
            forecast_id,
            strategy_type,
            long_contract_id,
            short_contract_id,
            long_strike,
            short_strike,
            session_date_et,
            candidate_valid
        ) VALUES (
            'candidate-invalid', 'forecast-1', 'BULL_CALL_DEBIT',
            'long-contract', 'short-contract', 100.0000, 101.0000,
            DATE '2026-08-14', false
        )
        """
    )

    row = migrated_connection.execute(
        """
        SELECT d_mid, d_natural, d_exec, spread_friction,
               fee, max_loss, max_profit,
               expected_payoff, ev, ev_over_max_loss, ev_lcb,
               lcb_over_max_loss, probability_profit, robust_score,
               liquidity_pass, edge_pass,
               long_bid, long_ask, short_bid, short_ask,
               long_quote_ts_utc, short_quote_ts_utc,
               gate_ev, gate_ev_ratio, gate_lcb, gate_lcb_ratio, gate_pop,
               fee_source
        FROM research.option_candidates
        WHERE candidate_id = 'candidate-invalid'
        """
    ).fetchone()
    assert row == (None,) * 28


def test_daily_decisions_contract_and_max_loss_resolution(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "daily_decisions",
        [
            ("decision_id", "VARCHAR", False),
            ("session_date_et", "DATE", False),
            ("decision_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("model_version", "VARCHAR", False),
            ("forecast_id", "VARCHAR", True),
            ("decision", "VARCHAR", False),
            ("best_candidate_id", "VARCHAR", True),
            ("primary_reason_code", "VARCHAR", False),
            ("expected_ev", "DOUBLE", True),
            ("expected_ev_lcb", "DOUBLE", True),
            ("max_loss", "DECIMAL(18,6)", True),
            ("robust_score", "DOUBLE", True),
            ("run_id", "VARCHAR", False),
            ("data_snapshot_sha256", "VARCHAR", False),
            ("model_status", "VARCHAR", False),
            ("n_train", "INTEGER", True),
            ("neff", "DOUBLE", True),
            ("ood_pass", "BOOLEAN", True),
            ("health_pass", "BOOLEAN", True),
            ("skill_pass", "BOOLEAN", True),
            ("expected_payoff", "DOUBLE", True),
            ("probability_profit", "DOUBLE", True),
            ("max_profit", "DECIMAL(18,6)", True),
            ("created_at", "TIMESTAMP WITH TIME ZONE", False),
        ],
    )
    assert _primary_key_columns(migrated_connection, "daily_decisions") == [
        "decision_id"
    ]
    columns = {
        name for name, _, _ in _column_contract(
            migrated_connection, "daily_decisions"
        )
    }
    assert columns.isdisjoint(
        {"decision_ts_et", "data_version", "all_reason_codes"}
    )


def test_daily_decision_check_accepts_frozen_values_and_rejects_invalid(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_daily_decision(migrated_connection, "trade", "TRADE")
    _insert_daily_decision(migrated_connection, "no-trade", "NO_TRADE")

    with pytest.raises(duckdb.ConstraintException):
        _insert_daily_decision(migrated_connection, "invalid", "INVALID")


def test_no_trade_decision_with_nullable_evidence_is_storable(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_daily_decision(
        migrated_connection, "no-trade-nullable", "NO_TRADE"
    )

    row = migrated_connection.execute(
        """
        SELECT forecast_id, best_candidate_id,
               expected_ev, expected_ev_lcb, max_loss, robust_score,
               n_train, neff, ood_pass, health_pass, skill_pass,
               expected_payoff, probability_profit, max_profit
        FROM research.daily_decisions
        WHERE decision_id = 'no-trade-nullable'
        """
    ).fetchone()
    assert row == (None,) * 14


def test_simulated_orders_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "simulated_orders",
        [
            ("order_id", "VARCHAR", False),
            ("decision_id", "VARCHAR", False),
            ("strategy", "VARCHAR", False),
            ("quantity", "INTEGER", False),
            ("submit_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("order_type", "VARCHAR", False),
            ("limit_price", "DECIMAL(18,6)", False),
            ("expected_fill_price", "DECIMAL(18,6)", False),
            ("execution_model", "VARCHAR", False),
            ("status", "VARCHAR", False),
        ],
    )
    assert _primary_key_columns(migrated_connection, "simulated_orders") == [
        "order_id"
    ]


def test_simulated_fills_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "simulated_fills",
        [
            ("fill_id", "VARCHAR", False),
            ("order_id", "VARCHAR", False),
            ("fill_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("fill_price", "DECIMAL(18,6)", False),
            ("quantity", "INTEGER", False),
            ("fee", "DECIMAL(18,6)", False),
            ("fee_source", "VARCHAR", False),
            ("fill_model", "VARCHAR", False),
        ],
    )
    assert _primary_key_columns(migrated_connection, "simulated_fills") == [
        "fill_id"
    ]
    assert "fill_type" not in {
        name for name, _, _ in _column_contract(
            migrated_connection, "simulated_fills"
        )
    }


def test_canonical_simulated_fill_is_storable(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    migrated_connection.execute(
        """
        INSERT INTO research.simulated_fills (
            fill_id,
            order_id,
            fill_ts_utc,
            fill_price,
            quantity,
            fee,
            fee_source,
            fill_model
        ) VALUES (
            'fill-1', 'order-1', TIMESTAMPTZ '2026-08-14 17:30:00+00',
            0.500000, 1, 3.000000,
            'CONSERVATIVE_FLOOR', 'SIMULATED_NATURAL'
        )
        """
    )

    assert migrated_connection.execute(
        """
        SELECT fee_source, fill_model
        FROM research.simulated_fills
        WHERE fill_id = 'fill-1'
        """
    ).fetchone() == ("CONSERVATIVE_FLOOR", "SIMULATED_NATURAL")


def test_trade_results_contract_without_forecast_error(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "trade_results",
        [
            ("decision_id", "VARCHAR", False),
            ("settlement_value", "DECIMAL(18,6)", True),
            ("gross_payoff", "DECIMAL(18,6)", True),
            ("entry_cost", "DECIMAL(18,6)", False),
            ("fee_total", "DECIMAL(18,6)", False),
            ("net_pnl", "DECIMAL(18,6)", True),
            ("return_on_max_loss", "DOUBLE", True),
            ("won", "BOOLEAN", True),
            ("session_date_et", "DATE", False),
            ("expected_ev", "DOUBLE", False),
            ("expected_ev_lcb", "DOUBLE", False),
            ("settled", "BOOLEAN", False),
        ],
    )
    assert _primary_key_columns(migrated_connection, "trade_results") == [
        "decision_id"
    ]
    assert "forecast_error" not in {
        name for name, _, _ in _column_contract(
            migrated_connection, "trade_results"
        )
    }


def test_unsettled_trade_result_with_null_realized_values_is_storable(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    migrated_connection.execute(
        """
        INSERT INTO research.trade_results (
            decision_id,
            settlement_value,
            gross_payoff,
            entry_cost,
            fee_total,
            net_pnl,
            return_on_max_loss,
            won,
            session_date_et,
            expected_ev,
            expected_ev_lcb,
            settled
        ) VALUES (
            'decision-unsettled', NULL, NULL, 50.000000, 3.000000,
            NULL, NULL, NULL, DATE '2026-08-14', 6.0, 1.0, false
        )
        """
    )

    row = migrated_connection.execute(
        """
        SELECT settlement_value, gross_payoff, net_pnl,
               return_on_max_loss, won, settled
        FROM research.trade_results
        WHERE decision_id = 'decision-unsettled'
        """
    ).fetchone()
    assert row == (None, None, None, None, None, False)


def test_no_audit_schema_or_tables(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    schemas = {
        schema_name
        for (schema_name,) in migrated_connection.execute(
            "SELECT schema_name FROM information_schema.schemata"
        ).fetchall()
    }
    tables = {
        table_name
        for (table_name,) in migrated_connection.execute(
            "SELECT table_name FROM information_schema.tables"
        ).fetchall()
    }

    assert "audit" not in schemas
    assert tables.isdisjoint({"backtest_runs", "backtest_metrics"})


def test_no_unauthorized_research_relational_features(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    unauthorized_constraints = migrated_connection.execute(
        """
        SELECT table_name, constraint_type
        FROM information_schema.table_constraints
        WHERE table_schema = 'research'
          AND constraint_type IN ('FOREIGN KEY', 'UNIQUE')
        """
    ).fetchall()
    defaults = migrated_connection.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'research'
          AND column_default IS NOT NULL
        """
    ).fetchall()
    indexes = migrated_connection.execute(
        """
        SELECT index_name
        FROM duckdb_indexes()
        WHERE schema_name = 'research'
        """
    ).fetchall()

    assert unauthorized_constraints == []
    assert defaults == []
    assert indexes == []


def test_no_research_table_was_renamed_or_duplicated(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    tables = {
        table_name
        for (table_name,) in migrated_connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'research'
            """
        ).fetchall()
    }
    forbidden = {
        "model_neighbors",
        "health_history",
        "candidate_gates",
        "fills",
        "orders",
        "forecast_health",
    }

    assert tables == RESEARCH_TABLES
    assert tables.isdisjoint(forbidden)
