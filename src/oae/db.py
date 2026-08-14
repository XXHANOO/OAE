from pathlib import Path

import duckdb


def open_database(path: str | Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(
        database=str(path),
        read_only=False,
    )
