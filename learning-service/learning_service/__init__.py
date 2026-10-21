"""learning_service：掌握度规则引擎包（ADR-0001；T-001-C）。

公共接口见 mastery 模块：validate_records / judge_mastery / MasteryConfig /
MasteryResult / Reason / MasteryInputError 及其子类。
"""

from .mastery import (
    DEFAULT_CONFIG,
    InvalidAnswerRecordError,
    MasteryConfig,
    MasteryInputError,
    MasteryResult,
    Reason,
    UnknownKnowledgePointError,
    judge_mastery,
    validate_records,
)

__all__ = [
    "DEFAULT_CONFIG",
    "InvalidAnswerRecordError",
    "MasteryConfig",
    "MasteryInputError",
    "MasteryResult",
    "Reason",
    "UnknownKnowledgePointError",
    "judge_mastery",
    "validate_records",
]
