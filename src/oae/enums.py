from enum import StrEnum


class SettlementStyle(StrEnum):
    AM = "AM"
    PM = "PM"


class StrategyType(StrEnum):
    BULL_CALL_DEBIT = "BULL_CALL_DEBIT"
    BEAR_PUT_DEBIT = "BEAR_PUT_DEBIT"
