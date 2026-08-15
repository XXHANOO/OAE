"""Canonical normalized market-data boundary records."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Self

from pydantic import Field, field_validator, model_validator

from oae.config import StrictModel
from oae.enums import QualityStatus
from oae.temporal import to_utc


class IndexBar1mRecord(StrictModel):
    """One canonical SPX one-minute bar represented as a half-open interval."""

    symbol: str
    session_date_et: date
    bar_start_ts_utc: datetime
    bar_end_ts_utc: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    observation_count: int = Field(ge=0, strict=True)
    source: str
    raw_file_id: str
    quality_status: QualityStatus

    @field_validator("symbol")
    @classmethod
    def _require_spx(cls, value: str) -> str:
        if value != "SPX":
            raise ValueError("symbol must be exactly 'SPX'")
        return value

    @field_validator("source", "raw_file_id")
    @classmethod
    def _require_non_empty_string(cls, value: str) -> str:
        if value == "":
            raise ValueError("value must be non-empty")
        return value

    @field_validator("bar_start_ts_utc", "bar_end_ts_utc")
    @classmethod
    def _canonicalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def _validate_one_minute_interval(self) -> Self:
        if self.bar_start_ts_utc >= self.bar_end_ts_utc:
            raise ValueError("bar_start_ts_utc must precede bar_end_ts_utc")
        if self.bar_end_ts_utc - self.bar_start_ts_utc != timedelta(minutes=1):
            raise ValueError("bar interval must be exactly 60 seconds")
        return self
