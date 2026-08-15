"""Immutable raw-file provenance and byte-integrity primitives."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from oae.temporal import to_utc


_SHA256_CHUNK_SIZE = 1024 * 1024


class RawDataIntegrityError(RuntimeError):
    """Raised when raw-file bytes or registered provenance conflict."""


class RawFileManifestRecord(BaseModel):
    """Strict immutable boundary model for ``meta.raw_file_manifest``."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    raw_file_id: str
    source: str
    source_file_name: str
    ingested_at_utc: datetime
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str
    min_event_ts: datetime | None
    max_event_ts: datetime | None
    row_count: int = Field(ge=0, strict=True)

    @field_validator(
        "raw_file_id",
        "source",
        "source_file_name",
        "schema_version",
    )
    @classmethod
    def _require_non_empty_string(cls, value: str) -> str:
        if value == "":
            raise ValueError("value must be non-empty")
        return value

    @field_validator("ingested_at_utc", "min_event_ts", "max_event_ts")
    @classmethod
    def _canonicalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return to_utc(value)

    @model_validator(mode="after")
    def _validate_event_range(self) -> Self:
        if (
            self.min_event_ts is not None
            and self.max_event_ts is not None
            and self.min_event_ts > self.max_event_ts
        ):
            raise ValueError("min_event_ts must not be later than max_event_ts")
        return self


def compute_file_sha256(file_path: str | Path) -> str:
    """Return the SHA-256 digest of a regular file using chunked binary reads."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"raw file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"raw file path is not a regular file: {path}")

    digest = hashlib.sha256()
    with path.open("rb") as raw_file:
        while chunk := raw_file.read(_SHA256_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def build_raw_file_manifest(
    *,
    file_path: str | Path,
    raw_file_id: str,
    source: str,
    source_file_name: str,
    ingested_at_utc: datetime,
    schema_version: str,
    min_event_ts: datetime | None,
    max_event_ts: datetime | None,
    row_count: int,
) -> RawFileManifestRecord:
    """Build strict provenance metadata using the digest of the actual bytes."""
    return RawFileManifestRecord(
        raw_file_id=raw_file_id,
        source=source,
        source_file_name=source_file_name,
        ingested_at_utc=ingested_at_utc,
        sha256=compute_file_sha256(file_path),
        schema_version=schema_version,
        min_event_ts=min_event_ts,
        max_event_ts=max_event_ts,
        row_count=row_count,
    )


def verify_raw_file(
    file_path: str | Path,
    manifest: RawFileManifestRecord,
) -> None:
    """Fail if current raw-file bytes differ from the recorded digest."""
    actual_sha256 = compute_file_sha256(file_path)
    if actual_sha256 != manifest.sha256:
        raise RawDataIntegrityError(
            "raw file SHA-256 mismatch for "
            f"raw_file_id={manifest.raw_file_id!r}: "
            f"expected {manifest.sha256}, actual {actual_sha256}"
        )
