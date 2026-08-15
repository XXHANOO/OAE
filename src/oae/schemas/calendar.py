"""Canonical application-layer trading-session and macro-event records."""

from datetime import date, datetime
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from oae.config import StrictModel
from oae.temporal import session_date_et_from_timestamp, to_utc


MacroEventType = Literal["FOMC_DECISION", "FOMC_PRESS_CONFERENCE"]


class TradingSessionRecord(StrictModel):
    """One canonical supplied trading-session calendar row."""

    session_date_et: date
    session_seq: int = Field(strict=True)
    open_ts_utc: datetime
    regular_close_ts_utc: datetime
    is_trading_day: bool = Field(strict=True)
    is_full_session: bool = Field(strict=True)
    is_half_day: bool = Field(strict=True)
    xsp_0dte_exists: bool = Field(strict=True)

    @field_validator("open_ts_utc", "regular_close_ts_utc")
    @classmethod
    def _canonicalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def _validate_calendar_row(self) -> Self:
        if self.open_ts_utc >= self.regular_close_ts_utc:
            raise ValueError("open_ts_utc must precede regular_close_ts_utc")
        if session_date_et_from_timestamp(self.open_ts_utc) != self.session_date_et:
            raise ValueError("open_ts_utc ET date must equal session_date_et")
        if session_date_et_from_timestamp(self.regular_close_ts_utc) != self.session_date_et:
            raise ValueError("regular_close_ts_utc ET date must equal session_date_et")
        if self.is_full_session and self.is_half_day:
            raise ValueError("is_full_session and is_half_day cannot both be true")
        if (self.is_full_session or self.is_half_day) and not self.is_trading_day:
            raise ValueError("full or half session must be a trading day")
        return self


class MacroEventRecord(StrictModel):
    """One canonical supplied FOMC calendar event row."""

    event_id: str
    event_date_et: date
    event_start_ts_utc: datetime
    event_end_ts_utc: datetime
    event_type: MacroEventType
    event_name: str
    source: str
    verified: bool = Field(strict=True)

    @field_validator("event_id", "event_name", "source")
    @classmethod
    def _require_non_empty_string(cls, value: str) -> str:
        if value == "":
            raise ValueError("value must be non-empty")
        return value

    @field_validator("event_start_ts_utc", "event_end_ts_utc")
    @classmethod
    def _canonicalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def _validate_event_row(self) -> Self:
        if self.event_start_ts_utc > self.event_end_ts_utc:
            raise ValueError("event_start_ts_utc must not be later than event_end_ts_utc")
        if session_date_et_from_timestamp(self.event_start_ts_utc) != self.event_date_et:
            raise ValueError("event_start_ts_utc ET date must equal event_date_et")
        if session_date_et_from_timestamp(self.event_end_ts_utc) != self.event_date_et:
            raise ValueError("event_end_ts_utc ET date must equal event_date_et")
        return self
