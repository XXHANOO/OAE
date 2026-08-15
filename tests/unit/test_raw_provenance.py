import hashlib
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import duckdb
import pytest
from pydantic import ValidationError

from oae.data.ingest import register_raw_file
from oae.data.lineage import (
    RawDataIntegrityError,
    RawFileManifestRecord,
    build_raw_file_manifest,
    compute_file_sha256,
    verify_raw_file,
)
from oae.db import open_database


CORE_SQL_PATH = Path("sql/001_core.sql")
UTC = timezone.utc
INGESTED_AT = datetime(2026, 7, 15, 18, 0, tzinfo=UTC)
MIN_EVENT_TS = datetime(2026, 7, 15, 17, 29, tzinfo=UTC)
MAX_EVENT_TS = datetime(2026, 7, 15, 17, 30, tzinfo=UTC)


def _write_raw_file(tmp_path: Path, data: bytes = b"OAE raw fixture\n") -> Path:
    file_path = tmp_path / "vendor-file.bin"
    file_path.write_bytes(data)
    return file_path


def _build_manifest(
    file_path: Path,
    **overrides: object,
) -> RawFileManifestRecord:
    values: dict[str, object] = {
        "file_path": file_path,
        "raw_file_id": "vendor:opaque/raw-id#001",
        "source": "TEST_VENDOR",
        "source_file_name": "explicit-vendor-name.bin",
        "ingested_at_utc": INGESTED_AT,
        "schema_version": "raw-v1",
        "min_event_ts": MIN_EVENT_TS,
        "max_event_ts": MAX_EVENT_TS,
        "row_count": 2,
    }
    values.update(overrides)
    return build_raw_file_manifest(**values)  # type: ignore[arg-type]


def _manifest_data(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "raw_file_id": "opaque-id",
        "source": "TEST_VENDOR",
        "source_file_name": "raw.bin",
        "ingested_at_utc": INGESTED_AT,
        "sha256": hashlib.sha256(b"raw").hexdigest(),
        "schema_version": "raw-v1",
        "min_event_ts": MIN_EVENT_TS,
        "max_event_ts": MAX_EVENT_TS,
        "row_count": 1,
    }
    values.update(overrides)
    return values


@pytest.fixture
def migrated_connection(
    tmp_path: Path,
) -> Iterator[duckdb.DuckDBPyConnection]:
    connection = open_database(tmp_path / "raw_provenance.duckdb")
    try:
        connection.execute(CORE_SQL_PATH.read_text(encoding="utf-8"))
        yield connection
    finally:
        connection.close()


def _fetch_manifest_row(
    connection: duckdb.DuckDBPyConnection,
    raw_file_id: str,
) -> tuple[object, ...] | None:
    return connection.execute(
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
        [raw_file_id],
    ).fetchone()


def test_raw_prov_001_known_byte_sha256(tmp_path: Path) -> None:
    file_path = _write_raw_file(tmp_path, b"abc")

    assert compute_file_sha256(file_path) == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )


def test_raw_prov_002_streaming_file_interface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = b"0123456789abcdef" * (1024 * 192)
    file_path = _write_raw_file(tmp_path, data)

    def reject_full_file_read(self: Path) -> bytes:
        raise AssertionError(f"full-file read forbidden for {self}")

    monkeypatch.setattr(Path, "read_bytes", reject_full_file_read)

    assert compute_file_sha256(file_path) == hashlib.sha256(data).hexdigest()


def test_raw_prov_003_missing_path_fails(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        compute_file_sha256(tmp_path / "missing.bin")


def test_raw_prov_004_directory_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a regular file"):
        compute_file_sha256(tmp_path)


def test_raw_prov_005_manifest_digest_comes_from_bytes(tmp_path: Path) -> None:
    data = b"digest must come from these bytes"
    file_path = _write_raw_file(tmp_path, data)

    manifest = _build_manifest(
        file_path,
        source_file_name="caller-supplied-name.parquet",
    )

    assert manifest.sha256 == hashlib.sha256(data).hexdigest()
    assert manifest.source_file_name == "caller-supplied-name.parquet"


def test_raw_prov_006_strict_frozen_model() -> None:
    with pytest.raises(ValidationError):
        RawFileManifestRecord.model_validate(
            {**_manifest_data(), "unexpected": "forbidden"}
        )

    manifest = RawFileManifestRecord.model_validate(_manifest_data())
    with pytest.raises(ValidationError):
        manifest.source = "MUTATED"  # type: ignore[misc]


def test_raw_prov_007_naive_ingested_timestamp_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        RawFileManifestRecord.model_validate(
            _manifest_data(ingested_at_utc=datetime(2026, 7, 15, 13, 30))
        )


def test_raw_prov_008_aware_timestamp_canonicalized_to_utc() -> None:
    new_york = ZoneInfo("America/New_York")
    manifest = RawFileManifestRecord.model_validate(
        _manifest_data(
            ingested_at_utc=datetime(2026, 7, 15, 13, 30, tzinfo=new_york)
        )
    )

    assert manifest.ingested_at_utc == datetime(
        2026,
        7,
        15,
        17,
        30,
        tzinfo=UTC,
    )
    assert manifest.ingested_at_utc.tzinfo is UTC


def test_raw_prov_009_min_max_timestamps() -> None:
    new_york = ZoneInfo("America/New_York")
    manifest = RawFileManifestRecord.model_validate(
        _manifest_data(
            min_event_ts=datetime(2026, 7, 15, 13, 29, tzinfo=new_york),
            max_event_ts=datetime(2026, 7, 15, 13, 30, tzinfo=new_york),
        )
    )

    assert manifest.min_event_ts == MIN_EVENT_TS
    assert manifest.max_event_ts == MAX_EVENT_TS
    assert manifest.min_event_ts is not None
    assert manifest.min_event_ts.tzinfo is UTC

    with pytest.raises(ValidationError, match="min_event_ts"):
        RawFileManifestRecord.model_validate(
            _manifest_data(
                min_event_ts=MAX_EVENT_TS,
                max_event_ts=MIN_EVENT_TS,
            )
        )


def test_raw_prov_010_row_count_integrity() -> None:
    with pytest.raises(ValidationError):
        RawFileManifestRecord.model_validate(_manifest_data(row_count=-1))

    manifest = RawFileManifestRecord.model_validate(_manifest_data(row_count=0))
    assert manifest.row_count == 0


@pytest.mark.parametrize(
    "invalid_sha256",
    [
        "A" * 64,
        "a" * 63,
        "a" * 65,
        "g" * 64,
        "0" * 63 + " ",
    ],
)
def test_raw_prov_011_sha_format(invalid_sha256: str) -> None:
    with pytest.raises(ValidationError):
        RawFileManifestRecord.model_validate(
            _manifest_data(sha256=invalid_sha256)
        )


def test_raw_prov_012_byte_mutation_detected(tmp_path: Path) -> None:
    file_path = _write_raw_file(tmp_path, b"original")
    manifest = _build_manifest(file_path)
    file_path.write_bytes(b"mutated")

    with pytest.raises(RawDataIntegrityError, match="SHA-256 mismatch"):
        verify_raw_file(file_path, manifest)


def test_raw_prov_013_clean_verification(tmp_path: Path) -> None:
    file_path = _write_raw_file(tmp_path)
    manifest = _build_manifest(file_path)

    assert verify_raw_file(file_path, manifest) is None


def test_raw_prov_014_insert_into_real_canonical_table(
    tmp_path: Path,
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    file_path = _write_raw_file(tmp_path)
    manifest = _build_manifest(file_path)

    register_raw_file(migrated_connection, file_path, manifest)

    assert _fetch_manifest_row(migrated_connection, manifest.raw_file_id) == (
        manifest.raw_file_id,
        manifest.source,
        manifest.source_file_name,
        int(manifest.ingested_at_utc.timestamp() * 1_000_000),
        manifest.sha256,
        manifest.schema_version,
        int(MIN_EVENT_TS.timestamp() * 1_000_000),
        int(MAX_EVENT_TS.timestamp() * 1_000_000),
        manifest.row_count,
    )


def test_raw_prov_015_idempotent_reregistration(
    tmp_path: Path,
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    file_path = _write_raw_file(tmp_path)
    manifest = _build_manifest(file_path)

    register_raw_file(migrated_connection, file_path, manifest)
    assert register_raw_file(migrated_connection, file_path, manifest) is None

    count = migrated_connection.execute(
        "SELECT COUNT(*) FROM meta.raw_file_manifest WHERE raw_file_id = ?",
        [manifest.raw_file_id],
    ).fetchone()
    assert count == (1,)


def test_raw_prov_016_conflicting_raw_file_id_rejected(
    tmp_path: Path,
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    file_path = _write_raw_file(tmp_path)
    original = _build_manifest(file_path)
    conflicting = _build_manifest(file_path, source="DIFFERENT_VENDOR")
    register_raw_file(migrated_connection, file_path, original)
    original_row = _fetch_manifest_row(migrated_connection, original.raw_file_id)

    with pytest.raises(RawDataIntegrityError, match="conflicting"):
        register_raw_file(migrated_connection, file_path, conflicting)

    assert _fetch_manifest_row(
        migrated_connection,
        original.raw_file_id,
    ) == original_row


def test_raw_prov_017_mutation_before_registration_rejected(
    tmp_path: Path,
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    file_path = _write_raw_file(tmp_path, b"original")
    manifest = _build_manifest(file_path)
    file_path.write_bytes(b"changed before registration")

    with pytest.raises(RawDataIntegrityError):
        register_raw_file(migrated_connection, file_path, manifest)

    assert _fetch_manifest_row(migrated_connection, manifest.raw_file_id) is None


def test_raw_prov_018_idempotent_path_still_verifies_bytes(
    tmp_path: Path,
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    file_path = _write_raw_file(tmp_path, b"original")
    manifest = _build_manifest(file_path)
    register_raw_file(migrated_connection, file_path, manifest)
    original_row = _fetch_manifest_row(migrated_connection, manifest.raw_file_id)
    file_path.write_bytes(b"mutated after registration")

    with pytest.raises(RawDataIntegrityError):
        register_raw_file(migrated_connection, file_path, manifest)

    assert _fetch_manifest_row(
        migrated_connection,
        manifest.raw_file_id,
    ) == original_row


def test_raw_prov_019_same_digest_different_ids_not_forbidden(
    tmp_path: Path,
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    file_path = _write_raw_file(tmp_path, b"shared deterministic bytes")
    first = _build_manifest(file_path, raw_file_id="raw-id-one")
    second = _build_manifest(file_path, raw_file_id="raw-id-two")

    register_raw_file(migrated_connection, file_path, first)
    register_raw_file(migrated_connection, file_path, second)

    rows = migrated_connection.execute(
        """
        SELECT raw_file_id, sha256
        FROM meta.raw_file_manifest
        ORDER BY raw_file_id
        """
    ).fetchall()
    assert rows == [
        ("raw-id-one", first.sha256),
        ("raw-id-two", second.sha256),
    ]


def test_raw_prov_020_opaque_raw_file_id(
    tmp_path: Path,
    migrated_connection: duckdb.DuckDBPyConnection,
) -> None:
    file_path = _write_raw_file(tmp_path)
    opaque_id = "vendor:2026/07/15 file#part-A"
    manifest = _build_manifest(file_path, raw_file_id=opaque_id)

    register_raw_file(migrated_connection, file_path, manifest)

    assert _fetch_manifest_row(migrated_connection, opaque_id) is not None


@pytest.mark.parametrize(
    "field_name",
    ["raw_file_id", "source", "source_file_name", "schema_version"],
)
def test_required_identity_strings_must_be_non_empty(field_name: str) -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        RawFileManifestRecord.model_validate(_manifest_data(**{field_name: ""}))
