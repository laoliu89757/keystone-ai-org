"""掌握度规则引擎 —— ADR-0001 的纯函数实现。

红线（INTENT-001 §1 / AGENTS.md §1）：放行与掌握度判定只来自规则引擎，
LLM 一律不参与。本模块只依赖 Python 3.11 标准库；无 I/O、无网络、
不读系统时钟（时序只来自入参 ``submitted_at``）、无随机、无全局可变状态；
同一输入重复调用 / 换序调用结果深度相等（规范排序见 :func:`_sort_canonical`）。

规格来源（唯一）：
- docs/adr/0001-掌握度规则引擎权重与阈值.md
  （§3 输入 Schema、§4 输出 Schema、§5 计分公式、§6 连错规则、
  §7 动作规则、§8 接口签名）
- docs/requirements/T-001-掌握度规则引擎.md（AC-01～AC-16）
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

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


# ---------------------------------------------------------------------------
# 异常（ADR-0001 §3.2 / §4.4：全部继承 ValueError，fail-fast，绝不静默当 0）
# ---------------------------------------------------------------------------


class MasteryInputError(ValueError):
    """掌握度判定输入非法的基类异常。"""


class InvalidAnswerRecordError(MasteryInputError):
    """单条答题记录字段级非法（类型 / 格式 / 取值范围）。"""


class UnknownKnowledgePointError(MasteryInputError):
    """知识点 ID 未在已登记集合中。"""


# ---------------------------------------------------------------------------
# 配置与结果结构（ADR-0001 §2 / §4 / §8：参数集中于 MasteryConfig，无散落魔法数字）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MasteryConfig:
    """掌握度规则引擎全部参数（默认值 = 产品默认，ADR-0001 §2 参数总表）。"""

    pass_threshold: float = 80.0  # 放行阈值，含端点（≥ 80.0 放行）
    min_questions: int = 10  # 最低题量，不足 → measured=False
    streak_critical: int = 3  # 连错临界段长
    accuracy_weight: float = 70.0  # 加权正确率项满分
    difficulty_weights: tuple[int, ...] = (1, 2, 3, 5, 8)  # 索引 d-1，加权正确率用
    difficulty_bonus: tuple[float, ...] = (0.0, 0.7, 1.0, 2.0, 3.0)  # 索引 d-1，答对加成
    streak_factor: float = 0.10  # 连错折减系数（有段时 ×(1-0.10)）
    review_threshold: float = 60.0  # 巩固/复习分界（< 60 → review）
    mastery_decimals: int = 1  # 掌握度小数位（ADR §0 裁决：1 位小数）
    knowledge_point_id_pattern: str = r"^[a-z][a-z0-9_]{2,31}$"
    duration_seconds_max: float = 7200.0


DEFAULT_CONFIG = MasteryConfig()


@dataclass(frozen=True)
class Reason:
    """一条判定理由（ADR-0001 §4.1）：规则名 + 贡献值（1 位小数）+ 非空说明。"""

    rule: str  # §4.3 规则名枚举
    contribution: float  # 1 位小数粒度（可为 0.0、负数）
    detail: str  # 非空，含关键数值的可读说明


@dataclass(frozen=True)
class MasteryResult:
    """判定输出（ADR-0001 §4.1）。"""

    mastery: float | None  # None 当 measured=False（数据不足）
    measured: bool  # False = 题量 < min_questions
    passed: bool  # passed == (measured and mastery >= pass_threshold)
    action: str  # "promote" | "consolidate" | "review"
    reasons: tuple[Reason, ...]  # 非空，顺序钉死（§4.3）


# 理由规则名枚举（ADR-0001 §4.3，顺序即正常测量时 reasons 的输出顺序）
RULE_WEIGHTED_ACCURACY = "weighted_accuracy"
RULE_DIFFICULTY_BONUS = "difficulty_bonus"
RULE_CONSECUTIVE_MISS = "consecutive_miss"
RULE_CLAMPING = "clamping"  # 仅当钳制实际生效时出现
RULE_THRESHOLD = "threshold_rule"
RULE_ACTION = "action_rule"
RULE_INSUFFICIENT_DATA = "insufficient_data"  # 仅数据不足分支

_ACTION_PROMOTE = "promote"
_ACTION_CONSOLIDATE = "consolidate"
_ACTION_REVIEW = "review"

_MISSING = object()  # 字段缺失哨兵


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _round_half_up(value: float, decimals: int) -> float:
    """四舍五入（half-up）自实现；不得用内置 round（银行家舍入破坏 80.0 端点）。

    采用 ADR-0001 §5.1 的安全式：``floor(x*10^d + 0.5) / 10^d``。
    """
    scale = 10**decimals
    return math.floor(value * scale + 0.5) / scale


def _invalid(
    index: int, field: str, reason: str, value: object
) -> InvalidAnswerRecordError:
    """构造字段级错误（错误信息格式钉死于 ADR-0001 §3.2，只含字段值）。"""
    shown = "<missing>" if value is _MISSING else value
    return InvalidAnswerRecordError(
        f"invalid answer record [index={index}] field={field}: {reason} (got {shown!r})"
    )


def _coerce_known_set(known_knowledge_points: Collection[str]) -> frozenset[str]:
    """已知知识点集合必填（ADR §8）；空集合法但会使所有记录报未知知识点。"""
    if isinstance(known_knowledge_points, (str, bytes)):
        raise MasteryInputError(
            "known_knowledge_points must be a collection of str, got str/bytes"
        )
    try:
        known = frozenset(known_knowledge_points)
    except TypeError as exc:
        raise MasteryInputError(
            "known_knowledge_points must be a collection of str, got "
            f"{type(known_knowledge_points).__name__}"
        ) from exc
    for item in known:
        if not isinstance(item, str):
            raise MasteryInputError(
                "known_knowledge_points must contain only str, got "
                f"{type(item).__name__}"
            )
    return known


# ---------------------------------------------------------------------------
# 输入校验（ADR-0001 §3.2 逐字段判定表，fail-fast：首条非法记录即抛出）
# ---------------------------------------------------------------------------


def _validate_record(
    index: int,
    record: object,
    known: frozenset[str],
    config: MasteryConfig,
    pattern: re.Pattern[str],
) -> None:
    if not isinstance(record, Mapping):
        raise _invalid(index, "record", "type_mismatch", record)

    # knowledge_point_id：str → 正则 → 已登记（ADR §3.1/§3.2）
    kp = record.get("knowledge_point_id", _MISSING)
    if kp is _MISSING or not isinstance(kp, str):
        raise _invalid(index, "knowledge_point_id", "type_mismatch", kp)
    if pattern.match(kp) is None:
        raise _invalid(index, "knowledge_point_id", "id_format", kp)
    if kp not in known:
        raise UnknownKnowledgePointError(
            f"unknown knowledge point [index={index}]: {kp!r} not in known set "
            f"(size={len(known)})"
        )

    # difficulty：非 bool 的 int（bool 是 int 子类，须显式排除），1..5
    difficulty = record.get("difficulty", _MISSING)
    if (
        difficulty is _MISSING
        or isinstance(difficulty, bool)
        or not isinstance(difficulty, int)
    ):
        raise _invalid(index, "difficulty", "type_mismatch", difficulty)
    if not 1 <= difficulty <= 5:
        raise _invalid(index, "difficulty", "difficulty_range", difficulty)

    # is_correct：严格 bool
    is_correct = record.get("is_correct", _MISSING)
    if is_correct is _MISSING or not isinstance(is_correct, bool):
        raise _invalid(index, "is_correct", "type_mismatch", is_correct)

    # duration_seconds：非 bool 的有限 int/float，[0, duration_seconds_max]；
    # 只做记录与校验，不参与计分（ADR §3.4）
    duration = record.get("duration_seconds", _MISSING)
    if (
        duration is _MISSING
        or isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
    ):
        raise _invalid(index, "duration_seconds", "type_mismatch", duration)
    if duration < 0 or duration > config.duration_seconds_max:
        raise _invalid(index, "duration_seconds", "duration_range", duration)

    # submitted_at：非 bool 的 int，≥ 0；时序唯一事实来源（ADR §3.1/§3.3）
    submitted_at = record.get("submitted_at", _MISSING)
    if (
        submitted_at is _MISSING
        or isinstance(submitted_at, bool)
        or not isinstance(submitted_at, int)
    ):
        raise _invalid(index, "submitted_at", "type_mismatch", submitted_at)
    if submitted_at < 0:
        raise _invalid(index, "submitted_at", "submitted_at_range", submitted_at)


def _validate(
    records: object,
    known_knowledge_points: Collection[str],
    config: MasteryConfig,
) -> frozenset[str]:
    known = _coerce_known_set(known_knowledge_points)
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise _invalid(-1, "records", "type_mismatch", records)
    pattern = re.compile(config.knowledge_point_id_pattern)
    for index, record in enumerate(records):
        _validate_record(index, record, known, config, pattern)
    return known


def validate_records(
    records: Sequence[Mapping[str, object]],
    known_knowledge_points: Collection[str],
) -> None:
    """校验 ADR-0001 §3.2 全部规则；非法即抛 MasteryInputError 子类（fail-fast）。

    按记录顺序逐条校验，遇到第一条非法记录立即抛出。本公开接口按
    DEFAULT_CONFIG 的约束校验；judge_mastery 内部按其传入 config 校验。
    """
    _validate(records, known_knowledge_points, DEFAULT_CONFIG)


# ---------------------------------------------------------------------------
# 判定（ADR-0001 §3.3 规范排序 + §5 六步公式 + §7 动作规则）
# ---------------------------------------------------------------------------


def _sort_canonical(
    records: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    """规范排序（ADR §3.3）：全字段元组升序作为唯一计算顺序（AC-14 顺序无关）。"""
    return sorted(
        records,
        key=lambda r: (
            r["submitted_at"],
            r["knowledge_point_id"],
            r["difficulty"],
            r["is_correct"],
            r["duration_seconds"],
        ),
    )


def _wrong_runs(canonical: Sequence[Mapping[str, object]]) -> list[int]:
    """规范序中每个极长连续错误段（maximal run）的段长（ADR §6.1）。"""
    runs: list[int] = []
    current = 0
    for record in canonical:
        if record["is_correct"]:
            if current:
                runs.append(current)
            current = 0
        else:
            current += 1
    if current:
        runs.append(current)
    return runs


def _insufficient_result(n: int, config: MasteryConfig) -> MasteryResult:
    """数据不足形态（ADR §4.2）：mastery=None、不放行、action=review。"""
    return MasteryResult(
        mastery=None,
        measured=False,
        passed=False,
        action=_ACTION_REVIEW,
        reasons=(
            Reason(
                RULE_INSUFFICIENT_DATA,
                0.0,
                f"题量 {n} < 最低要求 {config.min_questions}，无法测量掌握度",
            ),
            Reason(RULE_ACTION, 0.0, "action = review：数据不足，先补足题量"),
        ),
    )


def judge_mastery(
    records: Sequence[Mapping[str, object]],
    known_knowledge_points: Collection[str],
    *,
    config: MasteryConfig = DEFAULT_CONFIG,
) -> MasteryResult:
    """对单个知识点的一组答题记录判定（ADR-0001 §5 六步公式 + §7 动作规则）。

    纯函数：内部先校验（§3.2），再规范排序（§3.3）、计分（§5.1 ①②）、
    连错折减（③）、钳制（④）、half-up 舍入（⑤）、放行与动作判定（⑥/§7）。
    数据不足（n < min_questions）走 §4.2 分支正常返回；非法输入抛
    MasteryInputError 子类。同一输入重复 / 换序调用结果深度相等。
    """
    known = _validate(records, known_knowledge_points, config)

    n = len(records)
    if n < config.min_questions:
        return _insufficient_result(n, config)

    canonical = _sort_canonical(records)

    # ① 加权正确率项 + ② 难度加成项（加成只发给答对的题，ADR §5.2）
    total_weight = 0
    correct_weight = 0
    bonus = 0.0
    n_correct = 0
    correct_bonus_dist = [0] * len(config.difficulty_bonus)
    for record in canonical:
        d = record["difficulty"]
        weight = config.difficulty_weights[d - 1]
        total_weight += weight
        if record["is_correct"]:
            correct_weight += weight
            n_correct += 1
            bonus += config.difficulty_bonus[d - 1]
            correct_bonus_dist[d - 1] += 1
    accuracy = config.accuracy_weight * correct_weight / total_weight  # ∈ [0, 70]

    # ③ 连错折减（乘法、flat 制：段数与段长不加重折减，ADR §6.2）
    runs = _wrong_runs(canonical)
    max_run = max(runs) if runs else 0
    valid_segments = sum(1 for length in runs if length >= config.streak_critical)
    has_streak = valid_segments >= 1
    base = accuracy + bonus
    m1 = base * (1.0 - config.streak_factor if has_streak else 1.0)

    # ④ 边界钳制（记录是否实际生效，仅生效时出 clamping 理由，ADR §4.3）
    m2 = m1
    clamped = False
    if m1 > 100.0:
        m2, clamped = 100.0, True
    elif m1 < 0.0:
        m2, clamped = 0.0, True

    # ⑤ 舍入（half-up）＋ ⑥ 放行判定基于舍入后的 mastery（ADR §5.1）
    decimals = config.mastery_decimals
    mastery = _round_half_up(m2, decimals)
    passed = mastery >= config.pass_threshold

    # 动作判定（ADR §7，分支顺序钉死）
    if passed:
        action = _ACTION_PROMOTE
    elif has_streak:
        action = _ACTION_REVIEW
    elif mastery < config.review_threshold:
        action = _ACTION_REVIEW
    else:
        action = _ACTION_CONSOLIDATE

    # 理由列表（ADR §4.3 顺序钉死）
    accuracy_contrib = _round_half_up(accuracy, decimals)
    bonus_contrib = _round_half_up(bonus, decimals)
    dist_text = "、".join(
        f"难度{d + 1}×{count}" for d, count in enumerate(correct_bonus_dist) if count
    )
    reasons: list[Reason] = [
        Reason(
            RULE_WEIGHTED_ACCURACY,
            accuracy_contrib,
            f"加权正确率 {correct_weight / total_weight:.4f}"
            f"（答对权重 {correct_weight} / 总权重 {total_weight}），"
            f"计 {accuracy_contrib:.1f} / {config.accuracy_weight:.1f} 分",
        ),
        Reason(
            RULE_DIFFICULTY_BONUS,
            bonus_contrib,
            f"答对 {n_correct} 题的难度加成合计 {bonus_contrib:.1f}"
            + (f"（{dist_text}）" if dist_text else "（无答对题）"),
        ),
    ]
    if has_streak:
        reduction = _round_half_up(base * config.streak_factor, decimals)
        reasons.append(
            Reason(
                RULE_CONSECUTIVE_MISS,
                -reduction,
                f"最长连错段长 {max_run}，有效段 {valid_segments} 段"
                f"（段长 ≥ {config.streak_critical}），"
                f"整体 ×{1.0 - config.streak_factor:.2f} 折减",
            )
        )
    else:
        reasons.append(
            Reason(
                RULE_CONSECUTIVE_MISS,
                0.0,
                f"最长连错 {max_run} < 临界 {config.streak_critical}，不折减",
            )
        )
    if clamped:
        reasons.append(
            Reason(
                RULE_CLAMPING,
                _round_half_up(m2 - m1, decimals),
                f"钳制生效：钳制前 {m1:.1f} → 钳制后 {m2:.1f}（限 [0.0, 100.0]）",
            )
        )
    comparison = ">=" if passed else "<"
    reasons.append(
        Reason(
            RULE_THRESHOLD,
            0.0,
            f"mastery {mastery:.1f} {comparison} 放行阈值 "
            f"{config.pass_threshold:.1f}，passed={passed}",
        )
    )
    if passed:
        action_detail = (
            f"action = promote：mastery {mastery:.1f} ≥ 放行阈值 "
            f"{config.pass_threshold:.1f}"
        )
    elif has_streak:
        action_detail = (
            f"action = review：触发连错段（最长 {max_run} ≥ "
            f"{config.streak_critical}），强制复习"
        )
    elif mastery < config.review_threshold:
        action_detail = (
            f"action = review：mastery {mastery:.1f} < 巩固线 "
            f"{config.review_threshold:.1f}"
        )
    else:
        action_detail = (
            f"action = consolidate：{config.review_threshold:.1f} ≤ mastery "
            f"{mastery:.1f} < 放行阈值 {config.pass_threshold:.1f} 且无连错段"
        )
    reasons.append(Reason(RULE_ACTION, 0.0, action_detail))

    return MasteryResult(
        mastery=mastery,
        measured=True,
        passed=passed,
        action=action,
        reasons=tuple(reasons),
    )
