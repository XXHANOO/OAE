"""Canonical normalized option-quote boundary records."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import field_validator

from oae.config import StrictModel
from oae.temporal import to_utc


class OptionQuoteRecord(StrictModel):
    """One provider-originated option NBBO update in canonical field names."""

    contract_id: str
    quote_ts_utc: datetime
    session_date_et: date
    bid_px: Decimal
    ask_px: Decimal
    bid_size: int
    ask_size: int
    bid_exchange: str | None
    ask_exchange: str | None
    quote_condition: str | None
    sequence_no: int | None
    source: str
    raw_file_id: str

    @field_validator("contract_id", "source", "raw_file_id")
    @classmethod
    def _require_non_empty_string(cls, value: str) -> str:
        if value == "":
            raise ValueError("value must be non-empty")
        return value

    @field_validator("quote_ts_utc")
    @classmethod
    def _canonicalize_quote_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)
