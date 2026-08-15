from collections.abc import Iterator, Sequence
from pathlib import Path

import duckdb
import pytest

from oae.db import open_database


MIGRATION_PATHS = (
    Path("sql/001_core.sql"),
    Path("sql/002_research.sql"),
    Path("sql/003_audit.sql"),
)

META_CORE_TABLES = {
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

BACKTEST_RUNS_CONTRACT = [
    ("run_id", "VARCHAR", False),
    ("started_at", "TIMESTAMP WITH TIME ZONE", False),
    ("finished_at", "TIMESTAMP WITH TIME ZONE", True),
    ("model_version", "VARCHAR", False),
    ("feature_version", "VARCHAR", False),
    ("execution_version", "VARCHAR", False),
    ("git_commit", "VARCHAR", False),
    ("config_sha256", "VARCHAR", False),
    ("data_snapshot_sha256", "VARCHAR", False),
    ("start_date", "DATE", False),
    ("end_date", "DATE", False),
    ("random_seed", "BIGINT", False),
    ("python_environment_hash", "VARCHAR", False),
    ("status", "VARCHAR", False),
]

BACKTEST_METRICS_CONTRACT = [
    ("run_id", "VARCHAR", False),
    ("n_sessions", "BIGINT", False),
    ("n_trade_signals", "BIGINT", False),
    ("n_no_trade", "BIGINT", False),
    ("trade_frequency", "DOUBLE", False),
    ("gross_pnl", "DECIMAL(18,6)", False),
    ("net_pnl", "DECIMAL(18,6)", False),
    ("mean_pnl", "DOUBLE", False),
    ("median_pnl", "DOUBLE", False),
    ("win_rate", "DOUBLE", False),
    ("avg_win", "DOUBLE", False),
    ("avg_loss", "DOUBLE", False),
    ("profit_factor", "DOUBLE", False),
    ("ev_predicted_mean", "DOUBLE", False),
    ("ev_realized_mean", "DOUBLE", False),
    ("max_drawdown", "DECIMAL(18,6)", False),
    ("sharpe", "DOUBLE", False),
    ("sortino", "DOUBLE", False),
    ("largest_win", "DECIMAL(18,6)", False),
    ("largest_loss", "DECIMAL(18,6)", False),
    ("call_spread_count", "BIGINT", False),
    ("put_spread_count", "BIGINT", False),
    ("calibration_q10", "DOUBLE", False),
    ("calibration_q50", "DOUBLE", False),
    ("calibration_q90", "DOUBLE", False),
    ("distribution_skill", "DOUBLE", False),
    ("mean_net_pnl_ci_lower_95", "DOUBLE", False),
    ("aggregate_oos_ev", "DOUBLE", False),
    ("acceptance_result", "VARCHAR", False),
]


def apply_audit_migrations(
    connection: duckdb.DuckDBPyConnection,
) -> None:
    for path in MIGRATION_PATHS:
        connection.execute(path.read_text(encoding="utf-8"))


@pytest.fixture
def migrated_connection(
    tmp_path: Path,
) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = open_database(tmp_path / "audit_schema.duckdb")
    try:
        apply_audit_migrations(connection)
        yield connection
    finally:
        connection.close()


def _column_contract(
    connection: duckdb.DuckDBPyConnection,
    schema: str,
    table: str,
) -> list[tuple[str, str, bool]]:
    rows = connection.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema, table],
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
    assert _column_contract(connection, "audit", table) == list(expected)


def _primary_key_columns(
    connection: duckdb.DuckDBPyConnection,
    schema: str,
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
        WHERE tc.table_schema = ?
          AND tc.table_name = ?
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
        """,
        [schema, table],
    ).fetchall()
    return [column_name for (column_name,) in rows]


def _insert_backtest_run(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    status: str,
    *,
    finished_at: str | None = "2026-08-14 20:00:00+00",
) -> None:
    connection.execute(
        """
        INSERT INTO audit.backtest_runs (
            run_id,
            started_at,
            finished_at,
            model_version,
            feature_version,
            execution_version,
            git_commit,
            config_sha256,
            data_snapshot_sha256,
            start_date,
            end_date,
            random_seed,
            python_environment_hash,
            status
        ) VALUES (
            ?, TIMESTAMPTZ '2026-01-01 14:30:00+00', ?,
            'OAE-v0.1.0', 'OAE-v0.1.0',
            'CONSERVATIVE_NATURAL_ONE_LOT',
            'code-sha', 'config-sha', 'data-sha',
            DATE '2026-01-01', DATE '2026-08-14',
            20260813, 'python-environment-sha', ?
        )
        """,
        [run_id, finished_at, status],
    )


def _insert_backtest_metrics(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    acceptance_result: str,
    *,
    n_sessions: int = 500,
    n_trade_signals: int = 150,
    profit_factor: float = 1.20,
    mean_net_pnl_ci_lower_95: float = 0.10,
    aggregate_oos_ev: float = 1.00,
) -> None:
    connection.execute(
        """
        INSERT INTO audit.backtest_metrics (
            run_id,
            n_sessions,
            n_trade_signals,
            n_no_trade,
            trade_frequency,
            gross_pnl,
            net_pnl,
            mean_pnl,
            median_pnl,
            win_rate,
            avg_win,
            avg_loss,
            profit_factor,
            ev_predicted_mean,
            ev_realized_mean,
            max_drawdown,
            sharpe,
            sortino,
            largest_win,
            largest_loss,
            call_spread_count,
            put_spread_count,
            calibration_q10,
            calibration_q50,
            calibration_q90,
            distribution_skill,
            mean_net_pnl_ci_lower_95,
            aggregate_oos_ev,
            acceptance_result
        ) VALUES (
            ?, ?, ?, 350, 0.30,
            1200.000000, 900.000000,
            6.0, 4.0,
            0.55, 25.0, -18.0,
            ?,
            7.0, 6.0,
            -300.000000,
            1.0, 1.2,
            100.000000, -53.000000,
            80, 70,
            0.10, 0.50, 0.90,
            0.03,
            ?, ?, ?
        )
        """,
        [
            run_id,
            n_sessions,
            n_trade_signals,
            profit_factor,
            mean_net_pnl_ci_lower_95,
            aggregate_oos_ev,
            acceptance_result,
        ],
    )


def test_full_migration_stack_executes_successfully(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    assert migrated_connection.execute("SELECT 1").fetchone() == (1,)


def test_exact_application_schema_set(
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

    assert schemas == {"meta", "core", "research", "audit"}


def test_exact_audit_table_set(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    tables = {
        table_name
        for (table_name,) in migrated_connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'audit'
              AND table_type = 'BASE TABLE'
            """
        ).fetchall()
    }

    assert tables == {"backtest_runs", "backtest_metrics"}


def test_total_application_table_count_and_breakdown(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    rows = migrated_connection.execute(
        """
        SELECT table_schema, COUNT(*)
        FROM information_schema.tables
        WHERE table_schema IN ('meta', 'core', 'research', 'audit')
          AND table_type = 'BASE TABLE'
        GROUP BY table_schema
        """
    ).fetchall()

    counts = dict(rows)
    assert counts == {"meta": 1, "core": 9, "research": 12, "audit": 2}
    assert sum(counts.values()) == 24


def test_backtest_runs_exact_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "backtest_runs",
        BACKTEST_RUNS_CONTRACT,
    )
    assert _primary_key_columns(
        migrated_connection, "audit", "backtest_runs"
    ) == ["run_id"]


def test_backtest_runs_status_domain(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_backtest_run(migrated_connection, "successful-run", "SUCCESS")
    _insert_backtest_run(migrated_connection, "failed-run", "FAILED")

    with pytest.raises(duckdb.ConstraintException):
        _insert_backtest_run(migrated_connection, "running-run", "RUNNING")


def test_backtest_runs_finished_at_is_nullable(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_backtest_run(
        migrated_connection,
        "unfinished-run",
        "FAILED",
        finished_at=None,
    )

    assert migrated_connection.execute(
        """
        SELECT finished_at IS NULL
        FROM audit.backtest_runs
        WHERE run_id = 'unfinished-run'
        """
    ).fetchone() == (True,)


def test_backtest_metrics_exact_complete_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "backtest_metrics",
        BACKTEST_METRICS_CONTRACT,
    )
    assert _primary_key_columns(
        migrated_connection, "audit", "backtest_metrics"
    ) == ["run_id"]
    assert all(
        not is_nullable
        for _, _, is_nullable in _column_contract(
            migrated_connection, "audit", "backtest_metrics"
        )
    )


def test_backtest_metrics_numeric_policy(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    types = {
        name: data_type
        for name, data_type, _ in _column_contract(
            migrated_connection, "audit", "backtest_metrics"
        )
    }

    assert {
        name for name, data_type in types.items() if data_type == "DECIMAL(18,6)"
    } == {
        "gross_pnl",
        "net_pnl",
        "max_drawdown",
        "largest_win",
        "largest_loss",
    }
    assert {name for name, data_type in types.items() if data_type == "BIGINT"} == {
        "n_sessions",
        "n_trade_signals",
        "n_no_trade",
        "call_spread_count",
        "put_spread_count",
    }
    assert {name for name, data_type in types.items() if data_type == "DOUBLE"} == {
        "trade_frequency",
        "mean_pnl",
        "median_pnl",
        "win_rate",
        "avg_win",
        "avg_loss",
        "profit_factor",
        "ev_predicted_mean",
        "ev_realized_mean",
        "sharpe",
        "sortino",
        "calibration_q10",
        "calibration_q50",
        "calibration_q90",
        "distribution_skill",
        "mean_net_pnl_ci_lower_95",
        "aggregate_oos_ev",
    }


def test_backtest_metrics_acceptance_result_domain(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_backtest_metrics(
        migrated_connection,
        "potential-alpha",
        "POTENTIAL_ALPHA",
    )
    _insert_backtest_metrics(
        migrated_connection,
        "no-validated-alpha",
        "NO_VALIDATED_ALPHA",
    )

    with pytest.raises(duckdb.ConstraintException):
        _insert_backtest_metrics(
            migrated_connection,
            "validated-alpha",
            "VALIDATED_ALPHA",
        )


def test_acceptance_thresholds_are_not_ddl_checks(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_backtest_metrics(
        migrated_connection,
        "below-threshold-evidence",
        "NO_VALIDATED_ALPHA",
        n_sessions=1,
        n_trade_signals=0,
        profit_factor=0.0,
        mean_net_pnl_ci_lower_95=-1.0,
        aggregate_oos_ev=-1.0,
    )

    assert migrated_connection.execute(
        """
        SELECT n_sessions, n_trade_signals, profit_factor,
               mean_net_pnl_ci_lower_95, aggregate_oos_ev,
               acceptance_result
        FROM audit.backtest_metrics
        WHERE run_id = 'below-threshold-evidence'
        """
    ).fetchone() == (
        1,
        0,
        0.0,
        -1.0,
        -1.0,
        "NO_VALIDATED_ALPHA",
    )


def test_failed_run_requires_no_metrics_row(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_backtest_run(
        migrated_connection,
        "failed-without-metrics",
        "FAILED",
        finished_at=None,
    )

    assert migrated_connection.execute(
        """
        SELECT COUNT(*)
        FROM audit.backtest_metrics
        WHERE run_id = 'failed-without-metrics'
        """
    ).fetchone() == (0,)


def test_backtest_metrics_has_no_foreign_key_coupling(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_backtest_metrics(
        migrated_connection,
        "orphan-metrics-contract-test",
        "NO_VALIDATED_ALPHA",
    )

    assert migrated_connection.execute(
        """
        SELECT COUNT(*)
        FROM audit.backtest_metrics
        WHERE run_id = 'orphan-metrics-contract-test'
        """
    ).fetchone() == (1,)


def test_no_unauthorized_audit_tables(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    tables = {
        table_name
        for (table_name,) in migrated_connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'audit'
            """
        ).fetchall()
    }
    forbidden = {
        "dataset_snapshots",
        "dataset_manifests",
        "acceptance_runs",
        "acceptance_results",
        "leakage_results",
        "environment_snapshots",
        "metrics_history",
    }

    assert tables == {"backtest_runs", "backtest_metrics"}
    assert tables.isdisjoint(forbidden)


def test_no_unauthorized_audit_relational_features(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    constraints = migrated_connection.execute(
        """
        SELECT constraint_type, COUNT(*)
        FROM duckdb_constraints()
        WHERE schema_name = 'audit'
        GROUP BY constraint_type
        """
    ).fetchall()
    defaults = migrated_connection.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'audit'
          AND column_default IS NOT NULL
        """
    ).fetchall()
    indexes = migrated_connection.execute(
        """
        SELECT index_name
        FROM duckdb_indexes()
        WHERE schema_name = 'audit'
        """
    ).fetchall()

    constraint_counts = dict(constraints)
    assert set(constraint_counts) == {"PRIMARY KEY", "CHECK", "NOT NULL"}
    assert constraint_counts["PRIMARY KEY"] == 2
    assert constraint_counts["CHECK"] == 2
    assert defaults == []
    assert indexes == []


def test_prior_core_and_research_contracts_are_preserved(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    meta_core_tables = set(
        migrated_connection.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('meta', 'core')
              AND table_type = 'BASE TABLE'
            """
        ).fetchall()
    )
    research_tables = {
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

    assert meta_core_tables == META_CORE_TABLES
    assert research_tables == RESEARCH_TABLES


def test_s1_09a_forecast_neighbor_order_is_preserved(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    assert _column_contract(
        migrated_connection,
        "research",
        "forecast_neighbors",
    ) == [
        ("forecast_id", "VARCHAR", False),
        ("neighbor_rank", "INTEGER", False),
        ("neighbor_session_date", "DATE", False),
        ("distance", "DOUBLE", False),
        ("terminal_return", "DOUBLE", False),
        ("similarity_weight_raw", "DOUBLE", False),
        ("recency_weight", "DOUBLE", False),
        ("combined_weight_raw", "DOUBLE", False),
        ("normalized_weight", "DOUBLE", False),
        ("age_sessions", "INTEGER", False),
    ]


def test_dataset_snapshot_relational_tables_remain_absent(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    forbidden = {
        "dataset_snapshot",
        "dataset_snapshots",
        "dataset_snapshot_manifest",
        "dataset_manifests",
    }
    tables = {
        table_name
        for (table_name,) in migrated_connection.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema IN ('meta', 'core', 'research', 'audit')
            """
        ).fetchall()
    }

    assert tables.isdisjoint(forbidden)
