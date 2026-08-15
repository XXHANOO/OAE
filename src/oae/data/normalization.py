"""Fail-closed canonical normalization and lineage guardrails."""

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from oae.data.adapters import (
    IndexBar1mAdapter,
    OptionContractAdapter,
    OptionQuoteAdapter,
    ProviderAdapter,
    RawIndexBarT,
    RawOptionContractT,
    RawOptionQuoteT,
)
from oae.data.lineage import RawFileManifestRecord
from oae.schemas.market import IndexBar1mRecord
from oae.schemas.options import OptionContractRecord
from oae.schemas.quotes import OptionQuoteRecord


_CanonicalRecordT = TypeVar("_CanonicalRecordT", bound=BaseModel)


class NormalizationIntegrityError(RuntimeError):
    """Raised when guarded normalization detects an integrity violation."""


def _revalidate_manifest(
    manifest: RawFileManifestRecord,
) -> RawFileManifestRecord:
    if type(manifest) is not RawFileManifestRecord:
        raise NormalizationIntegrityError("invalid manifest boundary")

    try:
        return RawFileManifestRecord.model_validate(
            manifest.model_dump(mode="python")
        )
    except ValidationError as exc:
        raise NormalizationIntegrityError(
            "invalid manifest boundary: canonical revalidation failed"
        ) from exc


def _snapshot_adapter_source(adapter: ProviderAdapter) -> str:
    source = adapter.source
    if not isinstance(source, str) or source == "":
        raise NormalizationIntegrityError("invalid adapter source")
    return source


def _revalidate_canonical_record(
    record: object,
    expected_type: type[_CanonicalRecordT],
) -> _CanonicalRecordT:
    if type(record) is not expected_type:
        raise NormalizationIntegrityError(
            "unexpected canonical DTO type: "
            f"expected {expected_type.__name__}, got {type(record).__name__}"
        )

    try:
        return expected_type.model_validate(record.model_dump(mode="python"))
    except ValidationError as exc:
        raise NormalizationIntegrityError(
            "canonical DTO revalidation failed"
        ) from exc


def _require_output_source(record_source: str, adapter_source: str) -> None:
    if record_source != adapter_source:
        raise NormalizationIntegrityError("output source mismatch")


def _require_output_raw_file_id(
    record_raw_file_id: str,
    manifest_raw_file_id: str,
) -> None:
    if record_raw_file_id != manifest_raw_file_id:
        raise NormalizationIntegrityError("raw_file_id mismatch")


def normalize_index_bar_1m(
    adapter: IndexBar1mAdapter[RawIndexBarT],
    raw_record: RawIndexBarT,
    *,
    manifest: RawFileManifestRecord,
) -> IndexBar1mRecord:
    """Adapt and verify one canonical index bar against raw-file lineage."""
    canonical_manifest = _revalidate_manifest(manifest)
    adapter_source = _snapshot_adapter_source(adapter)
    if adapter_source != canonical_manifest.source:
        raise NormalizationIntegrityError("manifest source mismatch")

    record = adapter.adapt_index_bar_1m(
        raw_record,
        raw_file_id=canonical_manifest.raw_file_id,
    )
    canonical_record = _revalidate_canonical_record(record, IndexBar1mRecord)
    _require_output_source(canonical_record.source, adapter_source)
    _require_output_raw_file_id(
        canonical_record.raw_file_id,
        canonical_manifest.raw_file_id,
    )
    return canonical_record


def normalize_option_contract(
    adapter: OptionContractAdapter[RawOptionContractT],
    raw_record: RawOptionContractT,
) -> OptionContractRecord:
    """Adapt and verify one canonical option contract."""
    adapter_source = _snapshot_adapter_source(adapter)
    record = adapter.adapt_option_contract(raw_record)
    canonical_record = _revalidate_canonical_record(
        record,
        OptionContractRecord,
    )
    _require_output_source(canonical_record.source, adapter_source)
    return canonical_record


def normalize_option_quote(
    adapter: OptionQuoteAdapter[RawOptionQuoteT],
    raw_record: RawOptionQuoteT,
    *,
    manifest: RawFileManifestRecord,
) -> OptionQuoteRecord:
    """Adapt and verify one canonical option quote against raw-file lineage."""
    canonical_manifest = _revalidate_manifest(manifest)
    adapter_source = _snapshot_adapter_source(adapter)
    if adapter_source != canonical_manifest.source:
        raise NormalizationIntegrityError("manifest source mismatch")

    record = adapter.adapt_option_quote(
        raw_record,
        raw_file_id=canonical_manifest.raw_file_id,
    )
    canonical_record = _revalidate_canonical_record(record, OptionQuoteRecord)
    _require_output_source(canonical_record.source, adapter_source)
    _require_output_raw_file_id(
        canonical_record.raw_file_id,
        canonical_manifest.raw_file_id,
    )
    return canonical_record
