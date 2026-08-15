import inspect
from typing import Protocol, TypeVar, get_type_hints

import pytest

import oae.data.adapters as adapters
from oae.data.adapters import (
    IndexBar1mAdapter,
    OptionContractAdapter,
    OptionQuoteAdapter,
    ProviderAdapter,
    RawIndexBarT,
    RawOptionContractT,
    RawOptionQuoteT,
)
from oae.schemas.market import IndexBar1mRecord
from oae.schemas.options import OptionContractRecord
from oae.schemas.quotes import OptionQuoteRecord


ADAPTATION_METHODS = (
    IndexBar1mAdapter.adapt_index_bar_1m,
    OptionContractAdapter.adapt_option_contract,
    OptionQuoteAdapter.adapt_option_quote,
)


def _assert_protocol(contract: type[object]) -> None:
    assert getattr(contract, "_is_protocol", False) is True


def _assert_independent_contravariant_typevar(
    contract: type[object],
    raw_type: TypeVar,
) -> None:
    assert contract.__parameters__ == (raw_type,)
    assert raw_type.__contravariant__ is True
    assert raw_type.__covariant__ is False


def test_adapter_contract_001_provider_adapter_protocol_and_source() -> None:
    _assert_protocol(ProviderAdapter)
    assert ProviderAdapter.__bases__ == (Protocol,)

    source = inspect.getattr_static(ProviderAdapter, "source")
    assert isinstance(source, property)
    assert source.fget is not None
    assert source.fset is None
    assert list(inspect.signature(source.fget).parameters) == ["self"]
    assert get_type_hints(source.fget)["return"] is str


def test_adapter_contract_002_provider_protocol_is_not_concrete() -> None:
    with pytest.raises(TypeError, match="Protocols cannot be instantiated"):
        ProviderAdapter()


def test_adapter_contract_003_index_method_surface() -> None:
    _assert_protocol(IndexBar1mAdapter)
    signature = inspect.signature(IndexBar1mAdapter.adapt_index_bar_1m)

    assert list(signature.parameters) == ["self", "raw_record", "raw_file_id"]


def test_adapter_contract_004_index_raw_file_id_is_required_keyword_only(
) -> None:
    parameter = inspect.signature(
        IndexBar1mAdapter.adapt_index_bar_1m
    ).parameters["raw_file_id"]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


def test_adapter_contract_005_index_return_boundary() -> None:
    hints = get_type_hints(IndexBar1mAdapter.adapt_index_bar_1m)

    assert hints["return"] is IndexBar1mRecord


def test_adapter_contract_006_index_raw_type_is_contravariant_generic() -> None:
    _assert_independent_contravariant_typevar(IndexBar1mAdapter, RawIndexBarT)
    hints = get_type_hints(IndexBar1mAdapter.adapt_index_bar_1m)

    assert hints["raw_record"] is RawIndexBarT


def test_adapter_contract_007_option_contract_method_surface() -> None:
    _assert_protocol(OptionContractAdapter)
    signature = inspect.signature(OptionContractAdapter.adapt_option_contract)

    assert list(signature.parameters) == ["self", "raw_record"]
    assert "raw_file_id" not in signature.parameters


def test_adapter_contract_008_option_contract_return_boundary() -> None:
    hints = get_type_hints(OptionContractAdapter.adapt_option_contract)

    assert hints["return"] is OptionContractRecord


def test_adapter_contract_009_contract_raw_type_is_independent_generic() -> None:
    _assert_independent_contravariant_typevar(
        OptionContractAdapter,
        RawOptionContractT,
    )
    hints = get_type_hints(OptionContractAdapter.adapt_option_contract)

    assert hints["raw_record"] is RawOptionContractT
    assert RawOptionContractT is not RawIndexBarT
    assert RawOptionContractT is not RawOptionQuoteT


def test_adapter_contract_010_quote_method_surface() -> None:
    _assert_protocol(OptionQuoteAdapter)
    signature = inspect.signature(OptionQuoteAdapter.adapt_option_quote)

    assert list(signature.parameters) == ["self", "raw_record", "raw_file_id"]


def test_adapter_contract_011_quote_raw_file_id_is_required_keyword_only(
) -> None:
    parameter = inspect.signature(
        OptionQuoteAdapter.adapt_option_quote
    ).parameters["raw_file_id"]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


def test_adapter_contract_012_quote_return_boundary() -> None:
    hints = get_type_hints(OptionQuoteAdapter.adapt_option_quote)

    assert hints["return"] is OptionQuoteRecord


def test_adapter_contract_013_quote_raw_type_is_independent_generic() -> None:
    _assert_independent_contravariant_typevar(OptionQuoteAdapter, RawOptionQuoteT)
    hints = get_type_hints(OptionQuoteAdapter.adapt_option_quote)

    assert hints["raw_record"] is RawOptionQuoteT
    assert RawOptionQuoteT is not RawIndexBarT
    assert RawOptionQuoteT is not RawOptionContractT


def test_adapter_contract_014_no_downstream_decision_parameters() -> None:
    forbidden = {
        "decision_ts",
        "max_age_seconds",
        "quality_status",
        "quote_age",
        "freshness",
        "asof",
        "tie_break",
    }

    for method in ADAPTATION_METHODS:
        assert forbidden.isdisjoint(inspect.signature(method).parameters)


def test_adapter_contract_015_no_batch_or_transport_api() -> None:
    forbidden = {
        "fetch",
        "download",
        "load_all",
        "adapt_many",
        "stream",
        "request",
        "authenticate",
    }

    assert forbidden.isdisjoint(vars(adapters))
    for contract in (
        ProviderAdapter,
        IndexBar1mAdapter,
        OptionContractAdapter,
        OptionQuoteAdapter,
    ):
        assert forbidden.isdisjoint(vars(contract))


def test_adapter_contract_016_no_settlement_capability() -> None:
    assert "SettlementRecord" not in vars(adapters)
    assert "SettlementAdapter" not in vars(adapters)
    assert all("settlement" not in method.__name__ for method in ADAPTATION_METHODS)


def test_adapter_contract_017_approved_dto_classes_are_used_directly() -> None:
    assert adapters.IndexBar1mRecord is IndexBar1mRecord
    assert adapters.OptionContractRecord is OptionContractRecord
    assert adapters.OptionQuoteRecord is OptionQuoteRecord


def test_adapter_contract_018_module_defines_protocols_only() -> None:
    declared_classes = {
        name: value
        for name, value in vars(adapters).items()
        if inspect.isclass(value) and value.__module__ == adapters.__name__
    }

    assert declared_classes == {
        "ProviderAdapter": ProviderAdapter,
        "IndexBar1mAdapter": IndexBar1mAdapter,
        "OptionContractAdapter": OptionContractAdapter,
        "OptionQuoteAdapter": OptionQuoteAdapter,
    }
    assert all(
        getattr(contract, "_is_protocol", False)
        for contract in declared_classes.values()
    )


def test_capabilities_do_not_require_one_monolithic_adapter() -> None:
    assert "adapt_option_contract" not in vars(IndexBar1mAdapter)
    assert "adapt_option_quote" not in vars(IndexBar1mAdapter)
    assert "adapt_index_bar_1m" not in vars(OptionContractAdapter)
    assert "adapt_option_quote" not in vars(OptionContractAdapter)
    assert "adapt_index_bar_1m" not in vars(OptionQuoteAdapter)
    assert "adapt_option_contract" not in vars(OptionQuoteAdapter)
