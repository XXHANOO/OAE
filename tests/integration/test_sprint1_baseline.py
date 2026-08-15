from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from oae.config import (
    compute_config_sha256,
    load_config,
    validate_frozen_v0_1,
)
from oae.db import open_database
from oae.temporal import (
    DECISION_TIME_ET,
    MARKET_TIMEZONE_NAME,
    UTC,
    bar_is_usable_asof,
    decision_ts_et,
    decision_ts_utc,
    is_available_asof,
    is_fresh_asof,
)


MIGRATION_PATHS = (
    Path("sql/001_core.sql"),
    Path("sql/002_research.sql"),
    Path("sql/003_audit.sql"),
)
CONFIG_PATH = Path("config/oae_v0_1_frozen.yaml")
NORMALIZED_CONFIG_SHA256 = (
    "ece897f1dd038743462322480aec20aba05b219ce7af8b2e4e38f7a013f11044"
)

APPLICATION_TABLES = {
    "meta": {"raw_file_manifest"},
    "core": {
        "trading_sessions",
        "index_bars_1m",
        "index_sessions",
        "option_contracts",
        "option_nbbo",
        "option_settlements",
        "macro_events",
        "fee_schedules",
        "decision_option_snapshots",
    },
    "research": {
        "feature_snapshots",
        "model_samples",
        "model_scaler_snapshots",
        "forecast_runs",
        "forecast_scenarios",
        "forecast_neighbors",
        "forecast_evaluations",
        "option_candidates",
        "daily_decisions",
        "simulated_orders",
        "simulated_fills",
        "trade_results",
    },
    "audit": {"backtest_runs", "backtest_metrics"},
}


@pytest.fixture
def migrated_connection(
    tmp_path: Path,
) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = open_database(tmp_path / "sprint1_baseline.duckdb")
    try:
        for migration_path in MIGRATION_PATHS:
            connection.execute(migration_path.read_text(encoding="utf-8"))
        yield connection
    finally:
        connection.close()


def _column_names(
    connection: duckdb.DuckDBPyConnection,
    schema: str,
    table: str,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        ORDER BY ordinal_position
        """,
        [schema, table],
    ).fetchall()
    return [column_name for (column_name,) in rows]


def test_sprint1_int_001_full_migration_stack(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    schemas = {
        schema_name
        for (schema_name,) in migrated_connection.execute(
            """
            SELECT DISTINCT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('information_schema', 'main', 'pg_catalog')
              AND schema_name NOT LIKE 'pg_%'
            """
        ).fetchall()
    }

    assert schemas == set(APPLICATION_TABLES)


def test_sprint1_int_002_exact_table_counts_and_names(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    rows = migrated_connection.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('meta', 'core', 'research', 'audit')
          AND table_type = 'BASE TABLE'
        """
    ).fetchall()
    actual = {schema: set() for schema in APPLICATION_TABLES}
    for schema, table in rows:
        actual[schema].add(table)

    assert actual == APPLICATION_TABLES
    assert {schema: len(tables) for schema, tables in actual.items()} == {
        "meta": 1,
        "core": 9,
        "research": 12,
        "audit": 2,
    }
    assert sum(len(tables) for tables in actual.values()) == 24


def test_sprint1_int_003_corrected_research_baseline(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    assert _column_names(
        migrated_connection,
        "research",
        "forecast_neighbors",
    ) == [
        "forecast_id",
        "neighbor_rank",
        "neighbor_session_date",
        "distance",
        "terminal_return",
        "similarity_weight_raw",
        "recency_weight",
        "combined_weight_raw",
        "normalized_weight",
        "age_sessions",
    ]


def test_sprint1_int_004_audit_closure_baseline(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    assert {"python_environment_hash", "status"} <= set(
        _column_names(migrated_connection, "audit", "backtest_runs")
    )
    assert {
        "mean_net_pnl_ci_lower_95",
        "aggregate_oos_ev",
        "acceptance_result",
    } <= set(_column_names(migrated_connection, "audit", "backtest_metrics"))


def test_sprint1_int_005_decision_dst_golden_pair() -> None:
    assert decision_ts_utc(date(2026, 1, 15)) == datetime(
        2026,
        1,
        15,
        18,
        30,
        tzinfo=UTC,
    )
    assert decision_ts_utc(date(2026, 7, 15)) == datetime(
        2026,
        7,
        15,
        17,
        30,
        tzinfo=UTC,
    )


def test_sprint1_int_006_point_in_time_golden_boundary() -> None:
    decision = decision_ts_et(date(2026, 7, 15))

    assert is_available_asof(
        decision - timedelta(milliseconds=1),
        decision,
    ) is True
    assert is_available_asof(decision, decision) is True
    assert is_available_asof(
        decision + timedelta(milliseconds=1),
        decision,
    ) is False


def test_sprint1_int_007_quote_freshness_golden_boundary() -> None:
    decision = decision_ts_et(date(2026, 7, 15))
    max_age_seconds = 2.0

    assert is_fresh_asof(
        decision - timedelta(milliseconds=1999),
        decision,
        max_age_seconds,
    ) is True
    assert is_fresh_asof(
        decision - timedelta(milliseconds=2000),
        decision,
        max_age_seconds,
    ) is True
    assert is_fresh_asof(
        decision - timedelta(milliseconds=2001),
        decision,
        max_age_seconds,
    ) is False
    assert is_fresh_asof(
        decision + timedelta(milliseconds=1),
        decision,
        max_age_seconds,
    ) is False


def test_sprint1_int_008_bar_availability_golden_boundary() -> None:
    decision = decision_ts_et(date(2026, 7, 15))

    assert bar_is_usable_asof(
        decision - timedelta(minutes=1),
        decision,
        decision,
    ) is True
    assert bar_is_usable_asof(
        decision,
        decision + timedelta(minutes=1),
        decision,
    ) is False


def test_sprint1_int_009_config_identity() -> None:
    config = load_config(CONFIG_PATH)

    assert compute_config_sha256(config) == NORMALIZED_CONFIG_SHA256
    assert validate_frozen_v0_1(config) is None


def test_sprint1_int_010_config_temporal_alignment() -> None:
    config = load_config(CONFIG_PATH)

    assert config.timezone == MARKET_TIMEZONE_NAME == "America/New_York"
    assert config.decision_time == DECISION_TIME_ET
    assert config.quotes.max_age_seconds == 2.0
