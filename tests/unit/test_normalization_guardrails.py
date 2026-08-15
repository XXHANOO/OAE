import inspect
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

import oae.data.normalization as normalization
from oae.data.lineage import RawFileManifestRecord
from oae.data.normalization import (
    NormalizationIntegrityError,
    normalize_index_bar_1m,
    normalize_option_contract,
    normalize_option_quote,
)
from oae.enums import ExerciseStyle, OptionType, QualityStatus, SettlementStyle
from oae.schemas.market import IndexBar1mRecord
from oae.schemas.options import OptionContractRecord
from oae.schemas.quotes import OptionQuoteRecord


UTC = timezone.utc
SOURCE = "TEST_VENDOR"
RAW_FILE_ID = "opaque raw/file:id #not-a-uuid"
RAW_RECORD = object()


def _manifest(**overrides: object) -> RawFileManifestRecord:
    values: dict[str, object] = {
        "raw_file_id": RAW_FILE_ID,
        "source": SOURCE,
        "source_file_name": "provider.raw",
        "ingested_at_utc": datetime(2026, 7, 15, 18, 0, tzinfo=UTC),
        "sha256": "a" * 64,
        "schema_version": "raw-v1",
        "min_event_ts": datetime(2026, 7, 15, 17, 29, tzinfo=UTC),
        "max_event_ts": datetime(2026, 7, 15, 17, 30, tzinfo=UTC),
        "row_count": 1,
    }
    values.update(overrides)
    return RawFileManifestRecord.model_validate(values)


def _bar(**overrides: object) -> IndexBar1mRecord:
    values: dict[str, object] = {
        "symbol": "SPX",
        "session_date_et": date(2026, 7, 15),
        "bar_start_ts_utc": datetime(2026, 7, 15, 17, 29, tzinfo=UTC),
        "bar_end_ts_utc": datetime(2026, 7, 15, 17, 30, tzinfo=UTC),
        "open": Decimal("6375.00"),
        "high": Decimal("6376.00"),
        "low": Decimal("6374.00"),
        "close": Decimal("6375.50"),
        "observation_count": 42,
        "source": SOURCE,
        "raw_file_id": RAW_FILE_ID,
        "quality_status": QualityStatus.VALID,
    }
    values.update(overrides)
    return IndexBar1mRecord.model_validate(values)


def _contract(**overrides: object) -> OptionContractRecord:
    values: dict[str, object] = {
        "contract_id": "opaque-contract-id",
        "vendor_symbol": "VENDOR_SYMBOL",
        "product": "XSP",
        "root_symbol": "XSP",
        "underlying": "XSP",
        "option_type": OptionType.CALL,
        "strike": Decimal("640.00"),
        "expiration_date": date(2026, 7, 15),
        "settlement_style": SettlementStyle.PM,
        "exercise_style": ExerciseStyle.EUROPEAN,
        "multiplier": 100,
        "series_type": "PM_WEEKLY",
        "expiration_ts_utc": datetime(2026, 7, 15, 20, 0, tzinfo=UTC),
        "first_seen_date": date(2026, 7, 1),
        "last_seen_date": date(2026, 7, 15),
        "source": SOURCE,
    }
    values.update(overrides)
    return OptionContractRecord.model_validate(values)


def _quote(**overrides: object) -> OptionQuoteRecord:
    values: dict[str, object] = {
        "contract_id": "opaque-contract-id",
        "quote_ts_utc": datetime(2026, 7, 15, 17, 29, 59, tzinfo=UTC),
        "session_date_et": date(2026, 7, 15),
        "bid_px": Decimal("1.00"),
        "ask_px": Decimal("1.10"),
        "bid_size": 1,
        "ask_size": 1,
        "bid_exchange": None,
        "ask_exchange": None,
        "quote_condition": None,
        "sequence_no": None,
        "source": SOURCE,
        "raw_file_id": RAW_FILE_ID,
    }
    values.update(overrides)
    return OptionQuoteRecord.model_validate(values)


class _AdapterBase:
    def __init__(self, source: object, result: object) -> None:
        self._source = source
        self.result = result
        self.source_reads = 0
        self.call_count = 0
        self.received_raw_file_id: str | None = None
        self.error: Exception | None = None

    @property
    def source(self) -> object:
        self.source_reads += 1
        return self._source

    def _return_or_raise(self) -> object:
        self.call_count += 1
        if self.error is not None:
            raise self.error
        return self.result


class _BarAdapter(_AdapterBase):
    def adapt_index_bar_1m(
        self,
        raw_record: object,
        *,
        raw_file_id: str,
    ) -> object:
        assert raw_record is RAW_RECORD
        self.received_raw_file_id = raw_file_id
        return self._return_or_raise()


class _ContractAdapter(_AdapterBase):
    def adapt_option_contract(self, raw_record: object) -> object:
        assert raw_record is RAW_RECORD
        return self._return_or_raise()


class _QuoteAdapter(_AdapterBase):
    def adapt_option_quote(
        self,
        raw_record: object,
        *,
        raw_file_id: str,
    ) -> object:
        assert raw_record is RAW_RECORD
        self.received_raw_file_id = raw_file_id
        return self._return_or_raise()


def test_norm_lineage_001_public_error_type() -> None:
    assert issubclass(NormalizationIntegrityError, RuntimeError)


def test_norm_lineage_002_public_normalization_api() -> None:
    assert normalization.normalize_index_bar_1m is normalize_index_bar_1m
    assert normalization.normalize_option_contract is normalize_option_contract
    assert normalization.normalize_option_quote is normalize_option_quote


def test_norm_lineage_003_bar_manifest_required_keyword_only() -> None:
    signature = inspect.signature(normalize_index_bar_1m)
    assert list(signature.parameters) == ["adapter", "raw_record", "manifest"]
    manifest = signature.parameters["manifest"]
    assert manifest.kind is inspect.Parameter.KEYWORD_ONLY
    assert manifest.default is inspect.Parameter.empty
    assert "raw_file_id" not in signature.parameters


def test_norm_lineage_004_quote_manifest_required_keyword_only() -> None:
    signature = inspect.signature(normalize_option_quote)
    assert list(signature.parameters) == ["adapter", "raw_record", "manifest"]
    manifest = signature.parameters["manifest"]
    assert manifest.kind is inspect.Parameter.KEYWORD_ONLY
    assert manifest.default is inspect.Parameter.empty
    assert "raw_file_id" not in signature.parameters


def test_norm_lineage_005_contract_has_no_lineage_parameters() -> None:
    signature = inspect.signature(normalize_option_contract)
    assert list(signature.parameters) == ["adapter", "raw_record"]
    assert {"manifest", "raw_file_id", "file_path", "connection"}.isdisjoint(
        signature.parameters
    )


@pytest.mark.parametrize("source", [17, None, object()])
def test_norm_lineage_006_adapter_source_must_be_str(source: object) -> None:
    adapter = _ContractAdapter(source, _contract())

    with pytest.raises(NormalizationIntegrityError, match="adapter source"):
        normalize_option_contract(adapter, RAW_RECORD)  # type: ignore[arg-type]

    assert adapter.call_count == 0


@pytest.mark.parametrize("adapter_kind", ["bar", "contract", "quote"])
def test_norm_lineage_007_empty_source_fails_before_adaptation(
    adapter_kind: str,
) -> None:
    if adapter_kind == "bar":
        adapter = _BarAdapter("", _bar())
        invoke = lambda: normalize_index_bar_1m(  # noqa: E731
            adapter, RAW_RECORD, manifest=_manifest()
        )
    elif adapter_kind == "quote":
        adapter = _QuoteAdapter("", _quote())
        invoke = lambda: normalize_option_quote(  # noqa: E731
            adapter, RAW_RECORD, manifest=_manifest()
        )
    else:
        adapter = _ContractAdapter("", _contract())
        invoke = lambda: normalize_option_contract(  # noqa: E731
            adapter, RAW_RECORD
        )

    with pytest.raises(NormalizationIntegrityError, match="adapter source"):
        invoke()

    assert adapter.call_count == 0


@pytest.mark.parametrize("exact_source", [" Vendor MixedCase ", "   "])
def test_norm_lineage_008_source_is_exact_and_not_normalized(
    exact_source: str,
) -> None:
    adapter = _BarAdapter(exact_source, _bar(source=exact_source))

    result = normalize_index_bar_1m(
        adapter,
        RAW_RECORD,
        manifest=_manifest(source=exact_source),
    )

    assert result.source == exact_source


def test_norm_lineage_009_bar_happy_path_rematerializes() -> None:
    supplied = _bar()
    adapter = _BarAdapter(SOURCE, supplied)

    result = normalize_index_bar_1m(adapter, RAW_RECORD, manifest=_manifest())

    assert type(result) is IndexBar1mRecord
    assert result == supplied
    assert result is not supplied
    assert result.source == SOURCE
    assert result.raw_file_id == RAW_FILE_ID


def test_norm_lineage_010_bar_manifest_source_mismatch_precedes_call() -> None:
    adapter = _BarAdapter("OTHER_VENDOR", _bar(source="OTHER_VENDOR"))

    with pytest.raises(NormalizationIntegrityError, match="manifest source"):
        normalize_index_bar_1m(adapter, RAW_RECORD, manifest=_manifest())

    assert adapter.call_count == 0


def test_norm_lineage_011_bar_raw_file_id_handoff_is_exact() -> None:
    opaque_id = "not a UUID : raw/file #A"
    adapter = _BarAdapter(SOURCE, _bar(raw_file_id=opaque_id))

    normalize_index_bar_1m(
        adapter,
        RAW_RECORD,
        manifest=_manifest(raw_file_id=opaque_id),
    )

    assert adapter.received_raw_file_id == opaque_id


def test_norm_lineage_012_bar_output_source_mismatch_fails() -> None:
    adapter = _BarAdapter(SOURCE, _bar(source="OTHER_VENDOR"))

    with pytest.raises(NormalizationIntegrityError, match="output source"):
        normalize_index_bar_1m(adapter, RAW_RECORD, manifest=_manifest())


def test_norm_lineage_013_bar_output_raw_file_id_mismatch_fails() -> None:
    supplied = _bar(raw_file_id="wrong-id")
    adapter = _BarAdapter(SOURCE, supplied)

    with pytest.raises(NormalizationIntegrityError, match="raw_file_id"):
        normalize_index_bar_1m(adapter, RAW_RECORD, manifest=_manifest())

    assert supplied.raw_file_id == "wrong-id"


@pytest.mark.parametrize("wrong_result", [{"symbol": "SPX"}, _quote()])
def test_norm_lineage_014_bar_wrong_return_type_fails(
    wrong_result: object,
) -> None:
    adapter = _BarAdapter(SOURCE, wrong_result)

    with pytest.raises(NormalizationIntegrityError, match="DTO type"):
        normalize_index_bar_1m(adapter, RAW_RECORD, manifest=_manifest())


def test_norm_lineage_015_bar_subclass_fails() -> None:
    class ShadowBar(IndexBar1mRecord):
        pass

    shadow = ShadowBar.model_validate(_bar().model_dump(mode="python"))
    adapter = _BarAdapter(SOURCE, shadow)

    with pytest.raises(NormalizationIntegrityError, match="DTO type"):
        normalize_index_bar_1m(adapter, RAW_RECORD, manifest=_manifest())


def test_norm_lineage_016_bar_unsafe_construct_is_revalidated() -> None:
    values = _bar().model_dump(mode="python")
    values["bar_end_ts_utc"] = values["bar_start_ts_utc"]
    unsafe = IndexBar1mRecord.model_construct(**values)
    adapter = _BarAdapter(SOURCE, unsafe)

    with pytest.raises(
        NormalizationIntegrityError,
        match="revalidation",
    ) as exc_info:
        normalize_index_bar_1m(adapter, RAW_RECORD, manifest=_manifest())

    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_norm_lineage_017_contract_happy_path_rematerializes() -> None:
    supplied = _contract()
    adapter = _ContractAdapter(SOURCE, supplied)

    result = normalize_option_contract(adapter, RAW_RECORD)

    assert type(result) is OptionContractRecord
    assert result == supplied
    assert result is not supplied


def test_norm_lineage_018_contract_source_mismatch_fails() -> None:
    adapter = _ContractAdapter(SOURCE, _contract(source="OTHER_VENDOR"))

    with pytest.raises(NormalizationIntegrityError, match="output source"):
        normalize_option_contract(adapter, RAW_RECORD)


def test_norm_lineage_019_contract_wrong_return_type_fails() -> None:
    adapter = _ContractAdapter(SOURCE, {"contract_id": "shadow"})

    with pytest.raises(NormalizationIntegrityError, match="DTO type"):
        normalize_option_contract(adapter, RAW_RECORD)


def test_norm_lineage_020_contract_subclass_fails() -> None:
    class ShadowContract(OptionContractRecord):
        pass

    shadow = ShadowContract.model_validate(_contract().model_dump(mode="python"))
    adapter = _ContractAdapter(SOURCE, shadow)

    with pytest.raises(NormalizationIntegrityError, match="DTO type"):
        normalize_option_contract(adapter, RAW_RECORD)


def test_norm_lineage_021_contract_unsafe_construct_is_revalidated() -> None:
    values = _contract().model_dump(mode="python")
    values["multiplier"] = 0
    unsafe = OptionContractRecord.model_construct(**values)
    adapter = _ContractAdapter(SOURCE, unsafe)

    with pytest.raises(
        NormalizationIntegrityError,
        match="revalidation",
    ) as exc_info:
        normalize_option_contract(adapter, RAW_RECORD)

    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_norm_lineage_022_quote_happy_path_rematerializes() -> None:
    supplied = _quote()
    adapter = _QuoteAdapter(SOURCE, supplied)

    result = normalize_option_quote(adapter, RAW_RECORD, manifest=_manifest())

    assert type(result) is OptionQuoteRecord
    assert result == supplied
    assert result is not supplied
    assert result.source == SOURCE
    assert result.raw_file_id == RAW_FILE_ID


def test_norm_lineage_023_quote_manifest_source_mismatch_precedes_call() -> None:
    adapter = _QuoteAdapter("OTHER_VENDOR", _quote(source="OTHER_VENDOR"))

    with pytest.raises(NormalizationIntegrityError, match="manifest source"):
        normalize_option_quote(adapter, RAW_RECORD, manifest=_manifest())

    assert adapter.call_count == 0


def test_norm_lineage_024_quote_raw_file_id_handoff_is_exact() -> None:
    opaque_id = "opaque quote lineage / not-a-uuid"
    adapter = _QuoteAdapter(SOURCE, _quote(raw_file_id=opaque_id))

    normalize_option_quote(
        adapter,
        RAW_RECORD,
        manifest=_manifest(raw_file_id=opaque_id),
    )

    assert adapter.received_raw_file_id == opaque_id


def test_norm_lineage_025_quote_output_source_mismatch_fails() -> None:
    adapter = _QuoteAdapter(SOURCE, _quote(source="OTHER_VENDOR"))

    with pytest.raises(NormalizationIntegrityError, match="output source"):
        normalize_option_quote(adapter, RAW_RECORD, manifest=_manifest())


def test_norm_lineage_026_quote_output_raw_file_id_mismatch_fails() -> None:
    supplied = _quote(raw_file_id="wrong-id")
    adapter = _QuoteAdapter(SOURCE, supplied)

    with pytest.raises(NormalizationIntegrityError, match="raw_file_id"):
        normalize_option_quote(adapter, RAW_RECORD, manifest=_manifest())

    assert supplied.raw_file_id == "wrong-id"


def test_norm_lineage_027_quote_wrong_type_and_subclass_fail() -> None:
    class ShadowQuote(OptionQuoteRecord):
        pass

    wrong_results = [
        {"contract_id": "shadow"},
        ShadowQuote.model_validate(_quote().model_dump(mode="python")),
    ]
    for wrong_result in wrong_results:
        adapter = _QuoteAdapter(SOURCE, wrong_result)
        with pytest.raises(NormalizationIntegrityError, match="DTO type"):
            normalize_option_quote(adapter, RAW_RECORD, manifest=_manifest())


def test_norm_lineage_028_quote_unsafe_construct_is_revalidated() -> None:
    values = _quote().model_dump(mode="python")
    values["quote_ts_utc"] = datetime(2026, 7, 15, 13, 30)
    unsafe = OptionQuoteRecord.model_construct(**values)
    adapter = _QuoteAdapter(SOURCE, unsafe)

    with pytest.raises(
        NormalizationIntegrityError,
        match="revalidation",
    ) as exc_info:
        normalize_option_quote(adapter, RAW_RECORD, manifest=_manifest())

    assert isinstance(exc_info.value.__cause__, ValidationError)


@pytest.mark.parametrize(
    ("bid_px", "ask_px", "bid_size", "ask_size"),
    [
        (Decimal("1.25"), Decimal("1.25"), 1, 1),
        (Decimal("1.50"), Decimal("1.25"), 1, 1),
        (Decimal("0"), Decimal("1.00"), 0, 0),
    ],
)
def test_norm_lineage_029_to_031_raw_quote_states_remain_normalizable(
    bid_px: Decimal,
    ask_px: Decimal,
    bid_size: int,
    ask_size: int,
) -> None:
    supplied = _quote(
        bid_px=bid_px,
        ask_px=ask_px,
        bid_size=bid_size,
        ask_size=ask_size,
    )
    adapter = _QuoteAdapter(SOURCE, supplied)

    result = normalize_option_quote(adapter, RAW_RECORD, manifest=_manifest())

    assert (result.bid_px, result.ask_px) == (bid_px, ask_px)
    assert (result.bid_size, result.ask_size) == (bid_size, ask_size)


@pytest.mark.parametrize(
    "quote_ts",
    [
        datetime(2026, 7, 15, 17, 30, 1, tzinfo=UTC),
        datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
    ],
)
def test_norm_lineage_032_033_no_decision_or_freshness_filter(
    quote_ts: datetime,
) -> None:
    adapter = _QuoteAdapter(SOURCE, _quote(quote_ts_utc=quote_ts))

    result = normalize_option_quote(adapter, RAW_RECORD, manifest=_manifest())

    assert result.quote_ts_utc == quote_ts


@pytest.mark.parametrize("kind", ["bar", "quote"])
def test_norm_lineage_034_fabricated_manifest_is_revalidated(kind: str) -> None:
    values = _manifest().model_dump(mode="python")
    values["sha256"] = "not-a-canonical-digest"
    unsafe_manifest = RawFileManifestRecord.model_construct(**values)
    if kind == "bar":
        adapter = _BarAdapter(SOURCE, _bar())
        invoke = lambda: normalize_index_bar_1m(  # noqa: E731
            adapter, RAW_RECORD, manifest=unsafe_manifest
        )
    else:
        adapter = _QuoteAdapter(SOURCE, _quote())
        invoke = lambda: normalize_option_quote(  # noqa: E731
            adapter, RAW_RECORD, manifest=unsafe_manifest
        )

    with pytest.raises(
        NormalizationIntegrityError,
        match="manifest boundary",
    ) as exc_info:
        invoke()

    assert isinstance(exc_info.value.__cause__, ValidationError)
    assert adapter.source_reads == 0
    assert adapter.call_count == 0


@pytest.mark.parametrize("kind", ["bar", "contract", "quote"])
def test_norm_lineage_035_adapter_exception_propagates_unchanged(
    kind: str,
) -> None:
    class ProviderParseError(Exception):
        pass

    provider_error = ProviderParseError("provider parse failed")
    if kind == "bar":
        adapter = _BarAdapter(SOURCE, _bar())
        invoke = lambda: normalize_index_bar_1m(  # noqa: E731
            adapter, RAW_RECORD, manifest=_manifest()
        )
    elif kind == "quote":
        adapter = _QuoteAdapter(SOURCE, _quote())
        invoke = lambda: normalize_option_quote(  # noqa: E731
            adapter, RAW_RECORD, manifest=_manifest()
        )
    else:
        adapter = _ContractAdapter(SOURCE, _contract())
        invoke = lambda: normalize_option_contract(  # noqa: E731
            adapter, RAW_RECORD
        )
    adapter.error = provider_error

    with pytest.raises(ProviderParseError) as exc_info:
        invoke()

    assert exc_info.value is provider_error


def test_norm_lineage_036_no_db_file_or_network_inputs() -> None:
    forbidden_parameters = {
        "connection",
        "file_path",
        "url",
        "client",
        "session",
        "credentials",
    }
    for function in (
        normalize_index_bar_1m,
        normalize_option_contract,
        normalize_option_quote,
    ):
        assert forbidden_parameters.isdisjoint(inspect.signature(function).parameters)

    forbidden_module_names = {
        "duckdb",
        "Path",
        "open",
        "verify_raw_file",
        "compute_file_sha256",
        "register_raw_file",
        "requests",
        "httpx",
        "socket",
    }
    assert forbidden_module_names.isdisjoint(vars(normalization))


def test_norm_lineage_037_no_downstream_quote_semantics() -> None:
    forbidden = {
        "decision_ts",
        "max_age_seconds",
        "quality_status",
        "quote_age",
        "freshness",
        "asof",
        "tie_break",
    }
    for function in (
        normalize_index_bar_1m,
        normalize_option_contract,
        normalize_option_quote,
    ):
        assert forbidden.isdisjoint(inspect.signature(function).parameters)


def test_norm_lineage_038_source_is_snapshotted_once_per_call() -> None:
    adapters_and_invocations = [
        (
            _BarAdapter(SOURCE, _bar()),
            lambda adapter: normalize_index_bar_1m(
                adapter, RAW_RECORD, manifest=_manifest()
            ),
        ),
        (
            _ContractAdapter(SOURCE, _contract()),
            lambda adapter: normalize_option_contract(adapter, RAW_RECORD),
        ),
        (
            _QuoteAdapter(SOURCE, _quote()),
            lambda adapter: normalize_option_quote(
                adapter, RAW_RECORD, manifest=_manifest()
            ),
        ),
    ]

    for adapter, invoke in adapters_and_invocations:
        invoke(adapter)
        assert adapter.source_reads == 1


@pytest.mark.parametrize(
    "manifest_like",
    [
        {"raw_file_id": RAW_FILE_ID, "source": SOURCE},
        object(),
    ],
)
def test_manifest_like_objects_are_rejected(manifest_like: object) -> None:
    adapter = _BarAdapter(SOURCE, _bar())

    with pytest.raises(NormalizationIntegrityError, match="manifest boundary"):
        normalize_index_bar_1m(
            adapter,
            RAW_RECORD,
            manifest=manifest_like,  # type: ignore[arg-type]
        )

    assert adapter.source_reads == 0
    assert adapter.call_count == 0


def test_manifest_subclass_is_rejected() -> None:
    class ShadowManifest(RawFileManifestRecord):
        pass

    shadow = ShadowManifest.model_validate(_manifest().model_dump(mode="python"))
    adapter = _QuoteAdapter(SOURCE, _quote())

    with pytest.raises(NormalizationIntegrityError, match="manifest boundary"):
        normalize_option_quote(adapter, RAW_RECORD, manifest=shadow)

    assert adapter.source_reads == 0
    assert adapter.call_count == 0
