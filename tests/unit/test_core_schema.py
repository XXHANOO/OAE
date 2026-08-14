from collections.abc import Iterator, Sequence
from pathlib import Path

import duckdb
import pytest

from oae.db import open_database


CORE_SQL_PATH = Path("sql/001_core.sql")


def apply_core_sql(connection: duckdb.DuckDBPyConnection) -> None:
    sql = CORE_SQL_PATH.read_text(encoding="utf-8")
    connection.execute(sql)


@pytest.fixture
def migrated_connection(
    tmp_path: Path,
) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = open_database(tmp_path / "core_schema.duckdb")
    try:
        apply_core_sql(connection)
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
    schema: str,
    table: str,
    expected: Sequence[tuple[str, str, bool]],
) -> None:
    assert _column_contract(connection, schema, table) == list(expected)


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


def _insert_option_contract(
    connection: duckdb.DuckDBPyConnection,
    contract_id: str,
    *,
    option_type: str = "C",
    settlement_style: str = "PM",
    exercise_style: str = "EUROPEAN",
    series_type: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO core.option_contracts (
            contract_id,
            vendor_symbol,
            product,
            root_symbol,
            underlying,
            option_type,
            strike,
            expiration_date,
            settlement_style,
            exercise_style,
            multiplier,
            series_type,
            expiration_ts_utc,
            first_seen_date,
            last_seen_date,
            source
        ) VALUES (
            ?, 'VENDOR', 'XSP', 'XSP', 'XSP', ?, 100.0000,
            DATE '2026-08-14', ?, ?, 100, ?,
            TIMESTAMPTZ '2026-08-14 20:00:00+00',
            DATE '2026-08-01', DATE '2026-08-14', 'TEST'
        )
        """,
        [
            contract_id,
            option_type,
            settlement_style,
            exercise_style,
            series_type,
        ],
    )


def _insert_nbbo(
    connection: duckdb.DuckDBPyConnection,
    *,
    contract_id: str,
    bid_px: float,
    ask_px: float,
    bid_size: int,
    ask_size: int,
    quote_condition: str | None,
) -> None:
    connection.execute(
        """
        INSERT INTO core.option_nbbo (
            contract_id,
            quote_ts_utc,
            session_date_et,
            bid_px,
            ask_px,
            bid_size,
            ask_size,
            bid_exchange,
            ask_exchange,
            quote_condition,
            sequence_no,
            source,
            raw_file_id
        ) VALUES (
            ?, TIMESTAMPTZ '2026-08-14 17:30:00+00', DATE '2026-08-14',
            ?, ?, ?, ?, NULL, NULL, ?, NULL, 'TEST', 'raw-nbbo'
        )
        """,
        [
            contract_id,
            bid_px,
            ask_px,
            bid_size,
            ask_size,
            quote_condition,
        ],
    )


def _insert_macro_event(
    connection: duckdb.DuckDBPyConnection,
    event_id: str,
    event_type: str,
) -> None:
    connection.execute(
        """
        INSERT INTO core.macro_events (
            event_id,
            event_date_et,
            event_start_ts_utc,
            event_end_ts_utc,
            event_type,
            event_name,
            source,
            verified
        ) VALUES (
            ?, DATE '2026-08-14',
            TIMESTAMPTZ '2026-08-14 17:30:00+00',
            TIMESTAMPTZ '2026-08-14 20:00:00+00',
            ?, 'TEST EVENT', 'TEST', false
        )
        """,
        [event_id, event_type],
    )


def _insert_decision_snapshot(
    connection: duckdb.DuckDBPyConnection,
    *,
    contract_id: str,
    quote_age_ms: int = 1000,
    bid_px: float = 1.00,
    ask_px: float = 1.10,
    bid_size: int = 1,
    ask_size: int = 1,
    quote_valid: bool = True,
) -> None:
    connection.execute(
        """
        INSERT INTO core.decision_option_snapshots (
            session_date_et,
            decision_ts_utc,
            contract_id,
            quote_ts_utc,
            quote_age_ms,
            bid_px,
            ask_px,
            bid_size,
            ask_size,
            quote_valid,
            source_quote_id
        ) VALUES (
            DATE '2026-08-14',
            TIMESTAMPTZ '2026-08-14 17:30:00+00',
            ?, TIMESTAMPTZ '2026-08-14 17:29:59+00',
            ?, ?, ?, ?, ?, ?, 'source-quote'
        )
        """,
        [
            contract_id,
            quote_age_ms,
            bid_px,
            ask_px,
            bid_size,
            ask_size,
            quote_valid,
        ],
    )


def test_migration_executes_successfully(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    assert migrated_connection.execute("SELECT 1").fetchone() == (1,)


def test_only_meta_and_core_oae_schemas_are_created(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    schemas = {
        schema_name
        for (schema_name,) in migrated_connection.execute(
            "SELECT schema_name FROM information_schema.schemata"
        ).fetchall()
    }

    assert {"meta", "core"} <= schemas
    assert "research" not in schemas
    assert "audit" not in schemas


def test_exact_application_table_set(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    tables = migrated_connection.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('meta', 'core')
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
        """
    ).fetchall()

    assert tables == [
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
    ]


def test_raw_file_manifest_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "meta",
        "raw_file_manifest",
        [
            ("raw_file_id", "VARCHAR", False),
            ("source", "VARCHAR", False),
            ("source_file_name", "VARCHAR", False),
            ("ingested_at_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("sha256", "VARCHAR", False),
            ("schema_version", "VARCHAR", False),
            ("min_event_ts", "TIMESTAMP WITH TIME ZONE", True),
            ("max_event_ts", "TIMESTAMP WITH TIME ZONE", True),
            ("row_count", "BIGINT", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "meta", "raw_file_manifest"
    ) == ["raw_file_id"]


def test_trading_sessions_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "core",
        "trading_sessions",
        [
            ("session_date_et", "DATE", False),
            ("session_seq", "INTEGER", False),
            ("open_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("regular_close_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("is_trading_day", "BOOLEAN", False),
            ("is_full_session", "BOOLEAN", False),
            ("is_half_day", "BOOLEAN", False),
            ("xsp_0dte_exists", "BOOLEAN", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "core", "trading_sessions"
    ) == ["session_date_et"]


def test_index_bars_1m_contract_and_errata_b1(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "core",
        "index_bars_1m",
        [
            ("symbol", "VARCHAR", False),
            ("session_date_et", "DATE", False),
            ("bar_start_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("bar_end_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("open", "DECIMAL(18,6)", False),
            ("high", "DECIMAL(18,6)", False),
            ("low", "DECIMAL(18,6)", False),
            ("close", "DECIMAL(18,6)", False),
            ("observation_count", "INTEGER", False),
            ("source", "VARCHAR", False),
            ("raw_file_id", "VARCHAR", False),
            ("quality_status", "VARCHAR", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "core", "index_bars_1m"
    ) == ["symbol", "bar_end_ts_utc"]


def test_option_contracts_contract_and_errata_b2(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "core",
        "option_contracts",
        [
            ("contract_id", "VARCHAR", False),
            ("vendor_symbol", "VARCHAR", False),
            ("product", "VARCHAR", False),
            ("root_symbol", "VARCHAR", False),
            ("underlying", "VARCHAR", False),
            ("option_type", "VARCHAR", False),
            ("strike", "DECIMAL(18,4)", False),
            ("expiration_date", "DATE", False),
            ("settlement_style", "VARCHAR", False),
            ("exercise_style", "VARCHAR", False),
            ("multiplier", "INTEGER", False),
            ("series_type", "VARCHAR", True),
            ("expiration_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("first_seen_date", "DATE", False),
            ("last_seen_date", "DATE", False),
            ("source", "VARCHAR", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "core", "option_contracts"
    ) == ["contract_id"]


def test_option_contract_check_constraints(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_option_contract(
        migrated_connection,
        "valid-call",
        option_type="C",
        settlement_style="PM",
        exercise_style="EUROPEAN",
    )
    _insert_option_contract(
        migrated_connection,
        "valid-put",
        option_type="P",
        settlement_style="AM",
        exercise_style="AMERICAN",
    )

    with pytest.raises(duckdb.ConstraintException):
        _insert_option_contract(
            migrated_connection,
            "invalid-option-type",
            option_type="X",
        )

    with pytest.raises(duckdb.ConstraintException):
        _insert_option_contract(
            migrated_connection,
            "invalid-settlement-style",
            settlement_style="INVALID",
        )

    _insert_option_contract(
        migrated_connection,
        "unconstrained-exercise-style",
        exercise_style="VENDOR_STYLE",
    )


def test_option_nbbo_contract_and_errata_b3(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "core",
        "option_nbbo",
        [
            ("contract_id", "VARCHAR", False),
            ("quote_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("session_date_et", "DATE", False),
            ("bid_px", "DECIMAL(18,6)", False),
            ("ask_px", "DECIMAL(18,6)", False),
            ("bid_size", "INTEGER", False),
            ("ask_size", "INTEGER", False),
            ("bid_exchange", "VARCHAR", True),
            ("ask_exchange", "VARCHAR", True),
            ("quote_condition", "VARCHAR", True),
            ("sequence_no", "BIGINT", True),
            ("source", "VARCHAR", False),
            ("raw_file_id", "VARCHAR", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "core", "option_nbbo"
    ) == []


def test_raw_invalid_and_duplicate_like_nbbo_remains_storable(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    for _ in range(2):
        _insert_nbbo(
            migrated_connection,
            contract_id="raw-crossed-zero-size",
            bid_px=2.00,
            ask_px=1.00,
            bid_size=0,
            ask_size=0,
            quote_condition=None,
        )

    count = migrated_connection.execute(
        """
        SELECT COUNT(*)
        FROM core.option_nbbo
        WHERE contract_id = 'raw-crossed-zero-size'
        """
    ).fetchone()
    assert count == (2,)


def test_option_settlements_contract_and_errata_b4(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "core",
        "option_settlements",
        [
            ("product", "VARCHAR", False),
            ("expiration_date", "DATE", False),
            ("settlement_style", "VARCHAR", False),
            ("settlement_value", "DECIMAL(18,6)", False),
            ("effective_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("published_ts_utc", "TIMESTAMP WITH TIME ZONE", True),
            ("source", "VARCHAR", False),
            ("raw_file_id", "VARCHAR", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "core", "option_settlements"
    ) == ["product", "expiration_date", "settlement_style"]


def test_nullable_errata_boundaries(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_option_contract(
        migrated_connection,
        "nullable-series",
        series_type=None,
    )
    _insert_nbbo(
        migrated_connection,
        contract_id="nullable-condition",
        bid_px=1.00,
        ask_px=1.10,
        bid_size=1,
        ask_size=1,
        quote_condition=None,
    )
    migrated_connection.execute(
        """
        INSERT INTO core.option_settlements (
            product,
            expiration_date,
            settlement_style,
            settlement_value,
            effective_ts_utc,
            published_ts_utc,
            source,
            raw_file_id
        ) VALUES (
            'XSP', DATE '2026-08-14', 'PM', 100.250000,
            TIMESTAMPTZ '2026-08-14 20:00:00+00', NULL, 'TEST', 'raw-settle'
        )
        """
    )

    assert migrated_connection.execute(
        """
        SELECT series_type IS NULL
        FROM core.option_contracts
        WHERE contract_id = 'nullable-series'
        """
    ).fetchone() == (True,)
    assert migrated_connection.execute(
        """
        SELECT quote_condition IS NULL
        FROM core.option_nbbo
        WHERE contract_id = 'nullable-condition'
        """
    ).fetchone() == (True,)
    assert migrated_connection.execute(
        """
        SELECT published_ts_utc IS NULL
        FROM core.option_settlements
        WHERE product = 'XSP' AND expiration_date = DATE '2026-08-14'
        """
    ).fetchone() == (True,)


def test_index_sessions_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "core",
        "index_sessions",
        [
            ("session_date_et", "DATE", False),
            ("spx_official_prev_close", "DECIMAL(18,6)", False),
            ("spx_open", "DECIMAL(18,6)", False),
            ("spx_decision_px", "DECIMAL(18,6)", False),
            ("intraday_high_to_t0", "DECIMAL(18,6)", False),
            ("intraday_low_to_t0", "DECIMAL(18,6)", False),
            ("is_full_session", "BOOLEAN", False),
            ("session_open_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("session_close_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "core", "index_sessions"
    ) == ["session_date_et"]


def test_macro_events_contract_and_event_type_check(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "core",
        "macro_events",
        [
            ("event_id", "VARCHAR", False),
            ("event_date_et", "DATE", False),
            ("event_start_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("event_end_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("event_type", "VARCHAR", False),
            ("event_name", "VARCHAR", False),
            ("source", "VARCHAR", False),
            ("verified", "BOOLEAN", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "core", "macro_events"
    ) == ["event_id"]

    _insert_macro_event(
        migrated_connection, "valid-decision", "FOMC_DECISION"
    )
    _insert_macro_event(
        migrated_connection,
        "valid-press-conference",
        "FOMC_PRESS_CONFERENCE",
    )
    with pytest.raises(duckdb.ConstraintException):
        _insert_macro_event(
            migrated_connection, "invalid-event", "CPI_RELEASE"
        )


def test_fee_schedules_contract_and_nullable_effective_to(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "core",
        "fee_schedules",
        [
            ("effective_from", "DATE", False),
            ("effective_to", "DATE", True),
            ("broker", "VARCHAR", False),
            ("product", "VARCHAR", False),
            ("per_contract_fee", "DECIMAL(18,6)", False),
            ("exchange_fee", "DECIMAL(18,6)", False),
            ("regulatory_fee", "DECIMAL(18,6)", False),
            ("settlement_fee", "DECIMAL(18,6)", False),
            ("source", "VARCHAR", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "core", "fee_schedules"
    ) == []

    migrated_connection.execute(
        """
        INSERT INTO core.fee_schedules (
            effective_from,
            effective_to,
            broker,
            product,
            per_contract_fee,
            exchange_fee,
            regulatory_fee,
            settlement_fee,
            source
        ) VALUES (
            DATE '2026-08-14', NULL, 'TEST BROKER', 'XSP',
            0.650000, 0.100000, 0.020000, 0.030000, 'TEST'
        )
        """
    )
    assert migrated_connection.execute(
        """
        SELECT effective_to IS NULL
        FROM core.fee_schedules
        WHERE broker = 'TEST BROKER'
        """
    ).fetchone() == (True,)


def test_decision_option_snapshots_contract(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _assert_column_contract(
        migrated_connection,
        "core",
        "decision_option_snapshots",
        [
            ("session_date_et", "DATE", False),
            ("decision_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("contract_id", "VARCHAR", False),
            ("quote_ts_utc", "TIMESTAMP WITH TIME ZONE", False),
            ("quote_age_ms", "BIGINT", False),
            ("bid_px", "DECIMAL(18,6)", False),
            ("ask_px", "DECIMAL(18,6)", False),
            ("bid_size", "INTEGER", False),
            ("ask_size", "INTEGER", False),
            ("quote_valid", "BOOLEAN", False),
            ("source_quote_id", "VARCHAR", False),
        ],
    )
    assert _primary_key_columns(
        migrated_connection, "core", "decision_option_snapshots"
    ) == ["session_date_et", "contract_id"]


def test_invalid_decision_snapshot_remains_storable(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_decision_snapshot(
        migrated_connection,
        contract_id="invalid-snapshot",
        quote_age_ms=2001,
        bid_px=2.00,
        ask_px=1.00,
        bid_size=0,
        ask_size=0,
        quote_valid=False,
    )

    assert migrated_connection.execute(
        """
        SELECT quote_valid, bid_px, ask_px, bid_size, ask_size, quote_age_ms
        FROM core.decision_option_snapshots
        WHERE contract_id = 'invalid-snapshot'
        """
    ).fetchone() == (False, 2.000000, 1.000000, 0, 0, 2001)


def test_decision_snapshot_primary_key_enforced(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    _insert_decision_snapshot(
        migrated_connection,
        contract_id="duplicate-snapshot",
    )
    with pytest.raises(duckdb.ConstraintException):
        _insert_decision_snapshot(
            migrated_connection,
            contract_id="duplicate-snapshot",
        )


def test_no_research_or_audit_tables(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    forbidden_tables = {
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
        "backtest_runs",
        "backtest_metrics",
    }
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

    assert "research" not in schemas
    assert "audit" not in schemas
    assert tables.isdisjoint(forbidden_tables)


def test_no_foreign_keys_unique_constraints_defaults_or_indexes(
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    unauthorized_constraints = migrated_connection.execute(
        """
        SELECT table_schema, table_name, constraint_type
        FROM information_schema.table_constraints
        WHERE table_schema IN ('meta', 'core')
          AND constraint_type IN ('FOREIGN KEY', 'UNIQUE')
        """
    ).fetchall()
    defaults = migrated_connection.execute(
        """
        SELECT table_schema, table_name, column_name
        FROM information_schema.columns
        WHERE table_schema IN ('meta', 'core')
          AND column_default IS NOT NULL
        """
    ).fetchall()
    indexes = migrated_connection.execute(
        """
        SELECT schema_name, index_name
        FROM duckdb_indexes()
        WHERE schema_name IN ('meta', 'core')
        """
    ).fetchall()

    assert unauthorized_constraints == []
    assert defaults == []
    assert indexes == []
