"""Append-only registration of verified raw-file provenance."""

from datetime import datetime, timezone
from pathlib import Path

import duckdb

from oae.data.lineage import (
    RawDataIntegrityError,
    RawFileManifestRecord,
    verify_raw_file,
)
from oae.temporal import to_utc


_MANIFEST_COLUMNS = (
    "raw_file_id",
    "source",
    "source_file_name",
    "ingested_at_utc",
    "sha256",
    "schema_version",
    "min_event_ts",
    "max_event_ts",
    "row_count",
)

_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _manifest_values(manifest: RawFileManifestRecord) -> tuple[object, ...]:
    return tuple(getattr(manifest, column) for column in _MANIFEST_COLUMNS)


def _epoch_microseconds(timestamp: datetime | None) -> int | None:
    if timestamp is None:
        return None
    delta = to_utc(timestamp) - _EPOCH_UTC
    return (
        (delta.days * 86_400 + delta.seconds) * 1_000_000
        + delta.microseconds
    )


def _manifest_comparison_values(
    manifest: RawFileManifestRecord,
) -> tuple[object, ...]:
    return (
        manifest.raw_file_id,
        manifest.source,
        manifest.source_file_name,
        _epoch_microseconds(manifest.ingested_at_utc),
        manifest.sha256,
        manifest.schema_version,
        _epoch_microseconds(manifest.min_event_ts),
        _epoch_microseconds(manifest.max_event_ts),
        manifest.row_count,
    )


def register_raw_file(
    connection: duckdb.DuckDBPyConnection,
    file_path: str | Path,
    manifest: RawFileManifestRecord,
) -> None:
    """Verify and append an immutable raw manifest, or idempotently return."""
    verify_raw_file(file_path, manifest)

    existing_row = connection.execute(
        """
        SELECT
            raw_file_id,
            source,
            source_file_name,
            epoch_us(ingested_at_utc),
            sha256,
            schema_version,
            epoch_us(min_event_ts),
            epoch_us(max_event_ts),
            row_count
        FROM meta.raw_file_manifest
        WHERE raw_file_id = ?
        """,
        [manifest.raw_file_id],
    ).fetchone()

    if existing_row is not None:
        if existing_row == _manifest_comparison_values(manifest):
            return
        raise RawDataIntegrityError(
            "conflicting raw-file manifest for "
            f"raw_file_id={manifest.raw_file_id!r}"
        )

    connection.execute(
        """
        INSERT INTO meta.raw_file_manifest (
            raw_file_id,
            source,
            source_file_name,
            ingested_at_utc,
            sha256,
            schema_version,
            min_event_ts,
            max_event_ts,
            row_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        list(_manifest_values(manifest)),
    )
