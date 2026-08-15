"""Canonical normalized option-data boundary records."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import Field, field_validator

from oae.config import StrictModel
from oae.enums import ExerciseStyle, OptionType, SettlementStyle
from oae.temporal import to_utc


class OptionContractRecord(StrictModel):
    """One canonical option-contract-master record."""

    contract_id: str
    vendor_symbol: str
    product: str
    root_symbol: str
    underlying: str
    option_type: OptionType
    strike: Decimal
    expiration_date: date
    settlement_style: SettlementStyle
    exercise_style: ExerciseStyle
    multiplier: int = Field(gt=0, strict=True)
    series_type: str | None
    expiration_ts_utc: datetime
    first_seen_date: date
    last_seen_date: date
    source: str

    @field_validator(
        "contract_id",
        "vendor_symbol",
        "product",
        "root_symbol",
        "underlying",
        "source",
    )
    @classmethod
    def _require_non_empty_string(cls, value: str) -> str:
        if value == "":
            raise ValueError("value must be non-empty")
        return value

    @field_validator("expiration_ts_utc")
    @classmethod
    def _canonicalize_expiration_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)
