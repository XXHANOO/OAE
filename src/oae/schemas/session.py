"""Canonical SPX session-level state boundary record."""

from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import Field, field_validator, model_validator

from oae.config import StrictModel
from oae.temporal import session_date_et_from_timestamp, to_utc


class IndexSessionRecord(StrictModel):
    """One canonical decision-time SPX index-session state."""

    session_date_et: date
    spx_official_prev_close: Decimal = Field(gt=0, strict=True)
    spx_open: Decimal = Field(gt=0, strict=True)
    spx_decision_px: Decimal = Field(gt=0, strict=True)
    intraday_high_to_t0: Decimal = Field(gt=0, strict=True)
    intraday_low_to_t0: Decimal = Field(gt=0, strict=True)
    is_full_session: bool = Field(strict=True)
    session_open_ts_utc: datetime
    session_close_ts_utc: datetime

    @field_validator("session_open_ts_utc", "session_close_ts_utc")
    @classmethod
    def _canonicalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def _validate_session_state(self) -> Self:
        if self.session_open_ts_utc >= self.session_close_ts_utc:
            raise ValueError(
                "session_open_ts_utc must precede session_close_ts_utc"
            )
        if (
            session_date_et_from_timestamp(self.session_open_ts_utc)
            != self.session_date_et
        ):
            raise ValueError(
                "session_open_ts_utc ET date must equal session_date_et"
            )
        if (
            session_date_et_from_timestamp(self.session_close_ts_utc)
            != self.session_date_et
        ):
            raise ValueError(
                "session_close_ts_utc ET date must equal session_date_et"
            )
        if self.intraday_low_to_t0 > self.intraday_high_to_t0:
            raise ValueError(
                "intraday_low_to_t0 must not exceed intraday_high_to_t0"
            )
        if not (
            self.intraday_low_to_t0
            <= self.spx_open
            <= self.intraday_high_to_t0
        ):
            raise ValueError("spx_open must lie within the intraday range")
        if not (
            self.intraday_low_to_t0
            <= self.spx_decision_px
            <= self.intraday_high_to_t0
        ):
            raise ValueError(
                "spx_decision_px must lie within the intraday range"
            )
        return self
