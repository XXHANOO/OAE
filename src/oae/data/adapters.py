"""Provider-neutral single-record market-data adapter contracts."""

from typing import Protocol, TypeVar

from oae.schemas.market import IndexBar1mRecord
from oae.schemas.options import OptionContractRecord
from oae.schemas.quotes import OptionQuoteRecord


RawIndexBarT = TypeVar("RawIndexBarT", contravariant=True)
RawOptionContractT = TypeVar("RawOptionContractT", contravariant=True)
RawOptionQuoteT = TypeVar("RawOptionQuoteT", contravariant=True)


class ProviderAdapter(Protocol):
    """Shared provider-identity capability."""

    @property
    def source(self) -> str:
        ...


class IndexBar1mAdapter(ProviderAdapter, Protocol[RawIndexBarT]):
    """Adapt one provider-native index bar to the canonical boundary."""

    def adapt_index_bar_1m(
        self,
        raw_record: RawIndexBarT,
        *,
        raw_file_id: str,
    ) -> IndexBar1mRecord:
        ...


class OptionContractAdapter(ProviderAdapter, Protocol[RawOptionContractT]):
    """Adapt one provider-native option contract to the canonical boundary."""

    def adapt_option_contract(
        self,
        raw_record: RawOptionContractT,
    ) -> OptionContractRecord:
        ...


class OptionQuoteAdapter(ProviderAdapter, Protocol[RawOptionQuoteT]):
    """Adapt one provider-native option quote to the canonical boundary."""

    def adapt_option_quote(
        self,
        raw_record: RawOptionQuoteT,
        *,
        raw_file_id: str,
    ) -> OptionQuoteRecord:
        ...
