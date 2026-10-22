"""T-001-D 掌握度规则引擎测试集（CPO 16 条 AC 全覆盖 + owner-brief §4 八个边界情况）。

构造样例全部来自 ADR-0001 §9（已验算）；字段名钉死为 ADR §3.1：
knowledge_point_id / difficulty / is_correct / duration_seconds / submitted_at。
"""

import copy
import random

import pytest

from conftest import KNOWN_KP
from learning_service.mastery import (
    DEFAULT_CONFIG,
    InvalidAnswerRecordError,
    UnknownKnowledgePointError,
    judge_mastery,
)


def _rec(kp="kp_present_simple", difficulty=3, is_correct=True, duration=30, at=0):
    """合成答题记录（无任何真实学生信息）。"""
    return {
        "knowledge_point_id": kp,
        "difficulty": difficulty,
        "is_correct": is_correct,
        "duration_seconds": duration,
        "submitted_at": at,
    }


def _all_correct(n, difficulty, start_at=0):
    """n 题全对、全难 difficulty，submitted_at 递增。"""
    return [_rec(difficulty=difficulty, at=start_at + i) for i in range(n)]


# ---------------------------------------------------------------------------
# AC-07 / AC-08：0 题、1 题 → 数据不足（ADR §4.2）
# ---------------------------------------------------------------------------


def test_zero_records():
    result = judge_mastery([], KNOWN_KP)

    assert result.mastery is None
    assert result.measured is False
    assert result.passed is False
    assert result.action == "review"
    # 理由须说明"题量不足最低要求 10 题"（AC-07）
    assert any("题量" in r.detail and "10" in r.detail for r in result.reasons)


# ---------------------------------------------------------------------------
# AC-09：全对是同条件最高档（ADR §9 递减链：全难3×10 → 80.0 / 72.0 / 40.0）
# ---------------------------------------------------------------------------


def test_all_correct_is_highest():
    all_right = judge_mastery(_all_correct(10, 3), KNOWN_KP)

    # 错 1 题（at=1 保持位置，最长连错 1 < 3）：acc=63 + bon=9 → 72.0
    one_wrong = _all_correct(10, 3)
    one_wrong[1] = _rec(difficulty=3, is_correct=False, at=1)
    r_one = judge_mastery(one_wrong, KNOWN_KP)

    # 错一半（错题保留原时间戳 1,3,5,7,9，相间排列最长连错 1）：
    # acc=35 + bon=5 → 40.0
    half_wrong = _all_correct(10, 3)
    for i in range(1, 10, 2):
        half_wrong[i] = _rec(difficulty=3, is_correct=False, at=i)
    r_half = judge_mastery(half_wrong, KNOWN_KP)

    assert all_right.mastery == 80.0
    assert r_one.mastery == 72.0
    assert r_half.mastery == 40.0
    assert all_right.mastery > r_one.mastery > r_half.mastery  # 严格递减


def test_single_record():
    result = judge_mastery([_rec(at=0)], KNOWN_KP)

    assert result.mastery is None
    assert result.measured is False
    assert result.passed is False
    assert result.action == "review"
    assert any("题量" in r.detail for r in result.reasons)


# ---------------------------------------------------------------------------
# AC-10：全错 → 0.0，不放行（ADR §9：10 题全错全难3 → clamp(0×0.9) = 0.0）
# ---------------------------------------------------------------------------


def test_all_wrong_is_lowest_and_not_passed():
    all_wrong = [_rec(difficulty=3, is_correct=False, at=i) for i in range(10)]
    result = judge_mastery(all_wrong, KNOWN_KP)

    assert result.mastery == 0.0
    assert result.passed is False
    assert result.action in {"consolidate", "review"}

    # 同条件至少对 1 题必须严格更高（AC-10 比较性质）
    one_correct = _all_correct(10, 3)
    one_correct[0] = _rec(difficulty=3, is_correct=False, at=0)
    higher = judge_mastery(one_correct, KNOWN_KP)
    assert result.mastery < higher.mastery


# ---------------------------------------------------------------------------
# AC-11：放行阈值 ≥ 80.0 含端点（ADR §9 三档构造）
# ---------------------------------------------------------------------------


def test_threshold_79_9_not_passed():
    # 12 题全对：难3×5 + 难2×7 → 70 + 5×1.0 + 7×0.7 = 79.9
    records = _all_correct(5, 3) + [_rec(difficulty=2, at=10 + i) for i in range(7)]
    result = judge_mastery(records, KNOWN_KP)

    assert result.mastery == 79.9
    assert result.passed is False


def test_threshold_80_0_passed():
    # 10 题全对，全难3 → 70 + 10×1.0 = 80.0（含端点，必须放行）
    result = judge_mastery(_all_correct(10, 3), KNOWN_KP)

    assert result.mastery == 80.0
    assert result.passed is True
    assert result.action == "promote"


def test_threshold_80_1_passed():
    # 11 题全对：难3×8 + 难2×3 → 70 + 8×1.0 + 3×0.7 = 80.1
    records = _all_correct(8, 3) + [_rec(difficulty=2, at=10 + i) for i in range(3)]
    result = judge_mastery(records, KNOWN_KP)

    assert result.mastery == 80.1
    assert result.passed is True


# ---------------------------------------------------------------------------
# AC-12：难度权重差异（ADR §5.3：n=10 时难5 全对=100.0 严格大于 难1 全对=70.0）
# ---------------------------------------------------------------------------


def test_high_difficulty_beats_low_difficulty():
    high = judge_mastery(_all_correct(10, 5), KNOWN_KP)
    low = judge_mastery(_all_correct(10, 1), KNOWN_KP)

    assert high.mastery == 100.0
    assert low.mastery == 70.0
    assert high.mastery > low.mastery  # 严格大于，不允许相等


def test_difficulty_monotonic():
    # 备注加测：难度 3 > 难度 1、难度 5 > 难度 3（递增性）
    d1 = judge_mastery(_all_correct(10, 1), KNOWN_KP)
    d3 = judge_mastery(_all_correct(10, 3), KNOWN_KP)
    d5 = judge_mastery(_all_correct(10, 5), KNOWN_KP)

    assert d1.mastery < d3.mastery < d5.mastery


# ---------------------------------------------------------------------------
# AC-13：连错 ≥3 后转对（ADR §9 对比样例：全难3×10，7对3错）
# ---------------------------------------------------------------------------


def test_consecutive_wrong_then_recover():
    # 序 A：对对错错错对对对对对 → 最长连错段 3 → 50.4
    seq_a = [
        _rec(at=0), _rec(at=10), _rec(difficulty=3, is_correct=False, at=20),
        _rec(difficulty=3, is_correct=False, at=30), _rec(difficulty=3, is_correct=False, at=40),
        _rec(at=50), _rec(at=60), _rec(at=70), _rec(at=80), _rec(at=90),
    ]
    result_a = judge_mastery(seq_a, KNOWN_KP)

    # (49+7)×0.9 = 50.4；reasons 含 consecutive_miss = −5.6
    assert result_a.mastery == 50.4
    streak_reasons = [r for r in result_a.reasons if r.rule == "consecutive_miss"]
    assert len(streak_reasons) == 1
    assert streak_reasons[0].contribution == -5.6

    # 序 B：对对对对对错对对错错 → 最长连错段 2 → 56.0
    seq_b = [
        _rec(at=0), _rec(at=10), _rec(at=20), _rec(at=30), _rec(at=40),
        _rec(difficulty=3, is_correct=False, at=50), _rec(at=60),
        _rec(difficulty=3, is_correct=False, at=70), _rec(difficulty=3, is_correct=False, at=80),
        _rec(at=100),
    ]
    result_b = judge_mastery(seq_b, KNOWN_KP)

    assert result_b.mastery == 56.0
    assert result_a.mastery < result_b.mastery  # 连错段为负向信号


# ---------------------------------------------------------------------------
# AC-14：幂等与顺序无关（同输入 ≥3 次 + 换序输入深度相等）
# ---------------------------------------------------------------------------


def test_idempotent_and_order_insensitive():
    records = _all_correct(5, 3) + [_rec(difficulty=2, at=10 + i) for i in range(7)]

    runs = [judge_mastery(records, KNOWN_KP) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]

    shuffled = list(records)
    random.Random(42).shuffle(shuffled)
    assert judge_mastery(shuffled, KNOWN_KP) == runs[0]

    # 深度相等：reasons 逐条一致（dataclass frozen eq 已递归比较）
    assert judge_mastery(shuffled, KNOWN_KP).reasons == runs[0].reasons


def test_mutation_of_input_does_not_leak():
    # 输入记录被外部修改不应影响已得到的结果（纯函数，无全局可变状态）
    records = _all_correct(10, 3)
    snapshot = copy.deepcopy(records)
    first = judge_mastery(records, KNOWN_KP)
    records[0]["difficulty"] = 1
    second = judge_mastery(snapshot, KNOWN_KP)

    assert first == second


# ---------------------------------------------------------------------------
# AC-15：未知知识点 ID 显式报错（不许静默当 0 / 照常计算）
# ---------------------------------------------------------------------------


def test_unknown_knowledge_point_rejected():
    records = [_rec(kp="kp_nope", at=i) for i in range(10)]

    with pytest.raises(UnknownKnowledgePointError) as exc_info:
        judge_mastery(records, KNOWN_KP)

    message = str(exc_info.value)
    assert "kp_nope" in message
    assert "unknown knowledge point" in message


# ---------------------------------------------------------------------------
# AC-16：非法难度值显式报错（0/6/负数/非数值，绝不静默夹取）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_difficulty", [0, 6, -1, 2.5, "3", True])
def test_invalid_difficulty_rejected(bad_difficulty):
    records = [_rec(difficulty=bad_difficulty, at=i) for i in range(10)]

    with pytest.raises(InvalidAnswerRecordError):
        judge_mastery(records, KNOWN_KP)

    # 显式报错契约：难度 6 必须带 difficulty_range reason（ADR §3.2）
    if bad_difficulty == 6:
        with pytest.raises(InvalidAnswerRecordError, match="difficulty_range"):
            judge_mastery(records, KNOWN_KP)


# ---------------------------------------------------------------------------
# 钳制分支（ADR §4.3：仅钳制实际生效时 reasons 含 clamping 条目）
# ---------------------------------------------------------------------------


def test_clamping_branch_triggered():
    # 16 题全难4 全对 → 70 + 2.0×16 = 102 → 钳制 100.0
    result = judge_mastery(_all_correct(16, 4), KNOWN_KP)

    assert result.mastery == 100.0
    assert result.passed is True
    clamping = [r for r in result.reasons if r.rule == "clamping"]
    assert len(clamping) == 1
    assert clamping[0].contribution < 0  # 钳制为负贡献


def test_clamping_not_triggered():
    # 10 题全难5 全对 → 恰 100，无越界，reasons 不含 clamping
    result = judge_mastery(_all_correct(10, 5), KNOWN_KP)

    assert result.mastery == 100.0
    assert not any(r.rule == "clamping" for r in result.reasons)


# ---------------------------------------------------------------------------
# AC-01/02/03：输出契约（四要素、一致性、可解释）
# ---------------------------------------------------------------------------


def test_output_contract_complete():
    result = judge_mastery(_all_correct(10, 3), KNOWN_KP)

    assert isinstance(result.mastery, float)
    assert 0.0 <= result.mastery <= 100.0
    assert isinstance(result.passed, bool)
    assert result.action in {"promote", "consolidate", "review"}
    assert len(result.reasons) > 0
    for reason in result.reasons:
        assert isinstance(reason.rule, str) and reason.rule
        assert isinstance(reason.detail, str) and reason.detail
        # contribution 为 1 位小数粒度（ADR §0）
        assert abs(reason.contribution * 10 - round(reason.contribution * 10)) < 1e-9


def test_pass_and_action_consistent():
    sample_sets = [
        _all_correct(10, 3),                      # 80.0 → promote
        _all_correct(10, 1),                      # 70.0 → consolidate
        [_rec(difficulty=3, is_correct=False, at=i) for i in range(10)],  # 全错
        _all_correct(5, 3),                       # 数据不足
    ]
    for records in sample_sets:
        result = judge_mastery(records, KNOWN_KP)
        assert result.passed == (result.action == "promote")
        if not result.passed:
            assert result.action in {"consolidate", "review"}


def test_reasons_reference_rules():
    # AC-03：每个结论都能对应到具体规则条目（顺序钉死 §4.3）
    result = judge_mastery(_all_correct(10, 3), KNOWN_KP)

    rules = [r.rule for r in result.reasons]
    assert rules[0] == "weighted_accuracy"
    assert rules[1] == "difficulty_bonus"
    assert rules[2] == "consecutive_miss"
    assert "threshold_rule" in rules
    assert "action_rule" in rules
    assert all(r.contribution is not None for r in result.reasons)


def test_ac04_no_llm_no_side_effects(monkeypatch):
    """AC-04/05：真打桩版——对被禁资源的真实调用入口打桩（触发即抛错），
    并在测试内自证"打桩后的入口现在调用必抛错"（不允许只 set 不验）；
    打桩生效期间判定照常完成且结果不变。

    mastery 模块 import 区仅依赖 math/re/__future__/collections.abc/
    dataclasses（已核实）。两道防线：
    - 静态扫描：import 期插入的 ``import time`` / ``time.time()`` 等在
      导入期执行、打桩拦不到，靠模块命名空间扫描兜底（故 banned 含 time）；
    - 真打桩：判定期间任何对 socket / 时钟的调用立即抛 AssertionError。
    """
    import datetime as _dt
    import socket as _socket
    import sys
    import time as _time

    import learning_service.mastery as mastery_mod

    # --- 0) 静态扫描（保留原测试的依赖检查，补 time：导入期插入靠它兜底）---
    banned = ("socket", "http", "urllib.request", "requests", "sqlite3", "datetime", "time")
    for name in banned:
        assert name not in sys.modules or name not in mastery_mod.__dict__, (
            f"mastery 不应依赖 {name}"
        )

    # --- 1) 真打桩：对真实调用入口打桩，触发即抛错 ---
    def _boom(what):
        def _raise(*_args, **_kwargs):
            raise AssertionError(f"side effect detected: {what}")

        return _raise

    # datetime.datetime 是 C 类型，直接 setattr 其 now 会 TypeError——
    # 正确做法是替换 datetime 模块命名空间里的类（用子类保持 isinstance 语义）。
    class _BoomDT(_dt.datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            raise AssertionError("side effect detected: datetime.datetime.now")

        @classmethod
        def utcnow(cls, *args, **kwargs):
            raise AssertionError("side effect detected: datetime.datetime.utcnow")

    monkeypatch.setattr(_socket, "socket", _boom("socket.socket"))
    monkeypatch.setattr(_socket, "create_connection", _boom("socket.create_connection"))
    monkeypatch.setattr(_time, "time", _boom("time.time"))
    monkeypatch.setattr(_time, "monotonic", _boom("time.monotonic"))
    monkeypatch.setattr(_dt, "datetime", _BoomDT)

    # --- 2) 自证打桩有效：现在调用这些入口必抛错（不许只 set 不验）---
    with pytest.raises(AssertionError, match="side effect detected: socket.socket"):
        _socket.socket()
    # 127.0.0.1 为数字 IP，getaddrinfo 走纯解析路径，绝不会真连网络——
    # 若打桩失效这里才会出现真实连接行为。
    with pytest.raises(
        AssertionError, match="side effect detected: socket.create_connection"
    ):
        _socket.create_connection(("127.0.0.1", 80), timeout=0.01)
    with pytest.raises(AssertionError, match="side effect detected: time.time"):
        _time.time()
    with pytest.raises(AssertionError, match="side effect detected: time.monotonic"):
        _time.monotonic()
    with pytest.raises(
        AssertionError, match="side effect detected: datetime.datetime.now"
    ):
        _dt.datetime.now()
    with pytest.raises(
        AssertionError, match="side effect detected: datetime.datetime.utcnow"
    ):
        _dt.datetime.utcnow()

    # --- 3) 打桩生效期间判定照常完成，结果不变（AC-04 原行为断言保留）---
    result = judge_mastery(_all_correct(10, 3), KNOWN_KP)
    again = judge_mastery(_all_correct(10, 3), KNOWN_KP)

    assert result == again
    assert result.mastery == 80.0

    # --- 4) 默认值锁定（AC-05 原断言保留）---
    assert DEFAULT_CONFIG.pass_threshold == 80.0
    assert DEFAULT_CONFIG.min_questions == 10
    assert DEFAULT_CONFIG.streak_critical == 3
