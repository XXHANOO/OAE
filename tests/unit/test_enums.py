from enum import StrEnum

import pytest

from oae.enums import (
    DecisionType,
    ExerciseStyle,
    OptionType,
    QualityStatus,
    SettlementStyle,
    StrategyType,
)


OPTION_TYPE_CONTRACT = (
    ("CALL", "C"),
    ("PUT", "P"),
)
SETTLEMENT_STYLE_CONTRACT = (
    ("AM", "AM"),
    ("PM", "PM"),
)
EXERCISE_STYLE_CONTRACT = (
    ("EUROPEAN", "EUROPEAN"),
    ("AMERICAN", "AMERICAN"),
)
STRATEGY_TYPE_CONTRACT = (
    ("BULL_CALL_DEBIT", "BULL_CALL_DEBIT"),
    ("BEAR_PUT_DEBIT", "BEAR_PUT_DEBIT"),
)
DECISION_TYPE_CONTRACT = (
    ("TRADE", "TRADE"),
    ("NO_TRADE", "NO_TRADE"),
)
QUALITY_STATUS_CONTRACT = (
    ("VALID", "VALID"),
    ("STALE", "STALE"),
    ("CROSSED", "CROSSED"),
    ("LOCKED", "LOCKED"),
    ("ZERO_BID", "ZERO_BID"),
    ("ZERO_SIZE", "ZERO_SIZE"),
    ("MISSING", "MISSING"),
    ("OUT_OF_ORDER", "OUT_OF_ORDER"),
    ("DUPLICATE", "DUPLICATE"),
    ("HALTED", "HALTED"),
    ("UNKNOWN", "UNKNOWN"),
)

ENUM_CONTRACTS = (
    (OptionType, OPTION_TYPE_CONTRACT),
    (SettlementStyle, SETTLEMENT_STYLE_CONTRACT),
    (ExerciseStyle, EXERCISE_STYLE_CONTRACT),
    (StrategyType, STRATEGY_TYPE_CONTRACT),
    (DecisionType, DECISION_TYPE_CONTRACT),
    (QualityStatus, QUALITY_STATUS_CONTRACT),
)


def enum_pairs(enum_type: type[StrEnum]) -> tuple[tuple[str, str], ...]:
    return tuple((member.name, member.value) for member in enum_type)


def logical_contract_bytes(enum_type: type[StrEnum]) -> bytes:
    pairs = "|".join(f"{member.name}={member.value}" for member in enum_type)
    return f"{enum_type.__name__}|{pairs}".encode("ascii")


def test_enum_001_option_type_exact_frozen_contract() -> None:
    assert enum_pairs(OptionType) == OPTION_TYPE_CONTRACT


def test_enum_002_settlement_style_exact_frozen_contract() -> None:
    assert enum_pairs(SettlementStyle) == SETTLEMENT_STYLE_CONTRACT


def test_enum_003_exercise_style_exact_frozen_contract() -> None:
    assert enum_pairs(ExerciseStyle) == EXERCISE_STYLE_CONTRACT


def test_enum_004_strategy_type_exact_frozen_contract() -> None:
    assert enum_pairs(StrategyType) == STRATEGY_TYPE_CONTRACT


def test_enum_005_decision_type_exact_frozen_contract() -> None:
    assert enum_pairs(DecisionType) == DECISION_TYPE_CONTRACT


def test_enum_006_quality_status_exact_frozen_contract() -> None:
    assert enum_pairs(QualityStatus) == QUALITY_STATUS_CONTRACT


def test_enum_007_all_six_classes_subclass_strenum() -> None:
    assert all(issubclass(enum_type, StrEnum) for enum_type, _ in ENUM_CONTRACTS)


def test_enum_008_all_member_values_are_strings() -> None:
    assert all(
        isinstance(member.value, str)
        for enum_type, _ in ENUM_CONTRACTS
        for member in enum_type
    )


def test_enum_009_no_aliases_exist() -> None:
    for enum_type, _ in ENUM_CONTRACTS:
        assert len(enum_type.__members__) == len(list(enum_type))


def test_enum_010_member_iteration_order_is_frozen() -> None:
    for enum_type, expected_contract in ENUM_CONTRACTS:
        assert tuple(member.name for member in enum_type) == tuple(
            name for name, _ in expected_contract
        )


@pytest.mark.parametrize(
    ("enum_type", "serialized_value", "expected_member"),
    tuple(
        (enum_type, value, enum_type[name])
        for enum_type, contract in ENUM_CONTRACTS
        for name, value in contract
    ),
)
def test_enum_011_string_construction_uses_frozen_values(
    enum_type: type[StrEnum],
    serialized_value: str,
    expected_member: StrEnum,
) -> None:
    assert enum_type(serialized_value) is expected_member


@pytest.mark.parametrize(
    "enum_type",
    tuple(enum_type for enum_type, _ in ENUM_CONTRACTS),
)
def test_enum_012_invalid_values_raise_value_error(
    enum_type: type[StrEnum],
) -> None:
    with pytest.raises(ValueError):
        enum_type("__INVALID__")


def test_enum_013_settlement_style_logical_contract_is_unchanged() -> None:
    assert logical_contract_bytes(SettlementStyle) == b"SettlementStyle|AM=AM|PM=PM"


def test_enum_014_strategy_type_logical_contract_is_unchanged() -> None:
    assert logical_contract_bytes(StrategyType) == (
        b"StrategyType|BULL_CALL_DEBIT=BULL_CALL_DEBIT|"
        b"BEAR_PUT_DEBIT=BEAR_PUT_DEBIT"
    )
