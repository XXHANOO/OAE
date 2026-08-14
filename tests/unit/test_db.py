from pathlib import Path

import duckdb

from oae.db import open_database


def test_path_opens_and_creates_database(tmp_path: Path) -> None:
    database_path = tmp_path / "oae_test.duckdb"
    assert not database_path.exists()

    connection = open_database(database_path)
    try:
        assert isinstance(connection, duckdb.DuckDBPyConnection)
        assert database_path.exists()
    finally:
        connection.close()


def test_connection_executes_trivial_query(tmp_path: Path) -> None:
    connection = open_database(tmp_path / "query_test.duckdb")
    try:
        assert connection.execute("SELECT 42").fetchone() == (42,)
    finally:
        connection.close()


def test_fresh_database_contains_no_application_tables(tmp_path: Path) -> None:
    connection = open_database(tmp_path / "empty_test.duckdb")
    try:
        assert connection.execute("SHOW TABLES").fetchall() == []
    finally:
        connection.close()


def test_close_and_reopen_persistent_database(tmp_path: Path) -> None:
    database_path = tmp_path / "persistence_test.duckdb"

    connection = open_database(database_path)
    try:
        connection.execute("CREATE TABLE persistence_probe (value INTEGER)")
        connection.execute("INSERT INTO persistence_probe VALUES (42)")
    finally:
        connection.close()

    reopened_connection = open_database(database_path)
    try:
        row = reopened_connection.execute(
            "SELECT value FROM persistence_probe"
        ).fetchone()
        assert row == (42,)
    finally:
        reopened_connection.close()


def test_string_path_is_accepted(tmp_path: Path) -> None:
    database_path = str(tmp_path / "string_path.duckdb")

    connection = open_database(database_path)
    try:
        assert connection.execute("SELECT 42").fetchone() == (42,)
    finally:
        connection.close()


def test_exact_connection_call_contract(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    sentinel = object()

    def fake_connect(*, database: str, read_only: bool) -> object:
        calls.append({"database": database, "read_only": read_only})
        return sentinel

    monkeypatch.setattr(duckdb, "connect", fake_connect)

    result = open_database(Path("/tmp/example.duckdb"))

    assert result is sentinel
    assert calls == [
        {
            "database": "/tmp/example.duckdb",
            "read_only": False,
        }
    ]
