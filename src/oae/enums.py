from enum import StrEnum


class OptionType(StrEnum):
    CALL = "C"
    PUT = "P"


class SettlementStyle(StrEnum):
    AM = "AM"
    PM = "PM"


class ExerciseStyle(StrEnum):
    EUROPEAN = "EUROPEAN"
    AMERICAN = "AMERICAN"


class StrategyType(StrEnum):
    BULL_CALL_DEBIT = "BULL_CALL_DEBIT"
    BEAR_PUT_DEBIT = "BEAR_PUT_DEBIT"


class DecisionType(StrEnum):
    TRADE = "TRADE"
    NO_TRADE = "NO_TRADE"


class QualityStatus(StrEnum):
    VALID = "VALID"
    STALE = "STALE"
    CROSSED = "CROSSED"
    LOCKED = "LOCKED"
    ZERO_BID = "ZERO_BID"
    ZERO_SIZE = "ZERO_SIZE"
    MISSING = "MISSING"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    DUPLICATE = "DUPLICATE"
    HALTED = "HALTED"
    UNKNOWN = "UNKNOWN"
