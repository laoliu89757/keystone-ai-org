# T-001 独立评审报告（rev）

评审对象：分支 agent/ai/T-001，提交范围 7207d80..HEAD（2e5085c / 8d9c1d6 / 56d6e8f / 9993340 / 4aae6d9 共 5 个提交，+1523 行）
评审日期：2026-10-21　评审人：独立评审官（rev，GLM 家族，新会话，未参与开发）
规格来源（仅取仓库事实）：docs/board/owner-brief-001.md、docs/requirements/T-001-掌握度规则引擎.md（v1.0）、docs/adr/0001-掌握度规则引擎权重与阈值.md（v1.0）
依据：AGENTS.md §7 评审清单 + §6 领域约束 + docs/roles/09-rev.md。不采信任何会话自述。

## 结论

**通过。**

16 条验收标准逐条有对应测试与实现证据（AC→测试映射见下）；红线（LLM 不参与判定、纯标准库、无副作用）经代码走查与破坏实验双重核验成立；无越界改动、无门禁绕过。测试集具备真实行为锁定的证据：`python -m pytest tests/ -q` → **25 passed**。

### 业主三问逐条核验

**(a) 25 个测试是真覆盖还是凑数 —— 真覆盖。**
- 全绿证据：`python -m pytest tests/ -q` → `25 passed in 0.07s`（本机复跑两次均绿）。
- 破坏实验（恰好一次）：将 `learning-service/learning_service/mastery.py` 的 `pass_threshold` 默认值 80.0 临时改为 70.0 → `2 failed, 23 passed`：`test_threshold_79_9_not_passed`（79.9 在错误阈值下会被放行，方向断言变红）与 `test_ac04_no_llm_no_side_effects`（锁死 `DEFAULT_CONFIG.pass_threshold == 80.0` 的断言变红）。`git checkout -- learning-service/` 恢复后复跑 → 25 passed，工作区 `git diff` 为空。结论：断言锁定的是行为（放行方向、阈值端点、具体分数 80.0/72.0/40.0/50.4/56.0、理由结构），不是恒真式。
- 断言性质抽查：AC-09 递减链断言 `80.0 > 72.0 > 40.0`（mastery.py:247-252 加权公式 + 连错折减两条路径同时被锁）；AC-13 断言 consecutive_miss 条目存在且 contribution == -5.6、50.4 < 56.0；AC-16 参数化 6 种非法难度（0/6/-1/2.5/"3"/True）且难度 6 断言错误信息含 `difficulty_range`。均为行为断言。

**(b) 越界改动 / 受保护路径 —— 无。**
diff 文件清单（7 个）逐个核对：docs/requirements/T-001-掌握度规则引擎.md ✓、docs/adr/0001-掌握度规则引擎权重与阈值.md ✓、learning-service/__init__.py ✓、learning-service/learning_service/__init__.py ✓、learning-service/learning_service/mastery.py ✓、tests/conftest.py ✓、tests/test_mastery_judge.py ✓ —— 全部在 CEO 授权范围内（docs/requirements/、docs/adr/、learning-service/、tests/）。受保护路径（.github/、.paseo/、.claude/、AGENTS.md、CODEOWNERS、evals/baseline/、.env*）无一出现在 diff；无删测试/改断言/降阈值/改快照痕迹；五个提交各自 ≤600 行且单一职责（+243 / +396 / +513 / +324 / +49）。

**(c) AGENTS.md §6 领域约束 —— 逐条满足。**
1. **放行与掌握度判定不由 LLM 决定**：mastery.py 全部 import 为 `math`、`re`、`__future__.annotations`、`collections.abc`、`dataclasses`；函数体内无任何 LLM/模型网关/网络调用；`passed = mastery >= config.pass_threshold` 为纯数值比较（mastery.py:340 附近）。红线成立。
2. **只用 Python 标准库**：实现 5 个 import 全部 stdlib；测试用 `copy`/`random`（stdlib）+ `pytest`（owner-brief §3 明确许可"只用标准库 + 开发期 pytest"）。无第三方依赖引入。
3. **幂等与顺序无关**：纯函数 + 规范排序 `_sort_canonical`（mastery.py:255-268，按 `(submitted_at, kp, difficulty, is_correct, duration)` 全字段元组升序，时序来自入参 `submitted_at`，不读系统时钟）；`test_idempotent_and_order_insensitive` 覆盖同输入 3 次调用 + 随机乱序后深相等（含 reasons 逐条比较）。
4. **边界处理**：79.9 不放行 / 80.0 放行（含端点）/ 80.1 放行（test_threshold_79_9 / 80_0 / 80_1）；0 题与 1 题 → `mastery=None`、`measured=False`、不放行、理由含题量说明（test_zero_records / test_single_record，满足 AC-07 的"可程序区分于已测量结果"）；未知知识点 ID → `UnknownKnowledgePointError` 显式抛出（test_unknown_knowledge_point_rejected）；非法难度 → `InvalidAnswerRecordError` 显式抛出、绝不夹取（test_invalid_difficulty_rejected）。

### AC→测试映射（16/16）

AC-01→test_output_contract_complete；AC-02→test_pass_and_action_consistent（4 组代表性输入）；AC-03→test_reasons_reference_rules（规则名顺序钉死断言）；AC-04/05→test_ac04_no_llm_no_side_effects + 评审走查；AC-06→test_idempotent_and_order_insensitive + test_mutation_of_input_does_not_leak；AC-07→test_zero_records；AC-08→test_single_record；AC-09→test_all_correct_is_highest；AC-10→test_all_wrong_is_lowest_and_not_passed；AC-11→test_threshold_79_9_not_passed / test_threshold_80_0_passed / test_threshold_80_1_passed；AC-12→test_high_difficulty_beats_low_difficulty + test_difficulty_monotonic；AC-13→test_consecutive_wrong_then_recover；AC-14→test_idempotent_and_order_insensitive；AC-15→test_unknown_knowledge_point_rejected；AC-16→test_invalid_difficulty_rejected。测试文件由建议的四个合并为 test_mastery_judge.py —— 需求 §3 明文允许（"QA 可合并或改名，断言性质不得缺失"），断言性质经逐条核对无缺失。

## 阻塞问题

无。

## 建议项

1. **AC-04/05 打桩强度偏弱**（tests/test_mastery_judge.py::test_ac04_no_llm_no_side_effects）：现实现为 sys.modules/模块 `__dict__` 禁用名扫描，可拦 `import socket` 但拦不住 `from urllib.request import urlopen` 这类间接导入。建议后续迭代改用 monkeypatch 对 socket/时间函数真打桩（触发即抛错）。本次不阻塞：红线经评审走查成立（见结论 c-1），且破坏实验证明测试集有真实检测力。
2. **分支总量 1523 行超过"≤600 行/PR"阈值**（AGENTS.md §4.3）：五个提交各自 ≤600 且单一职责、owner-brief §5 明确要求单分支五件套交付，故不判阻塞；建议业主审阅与合并时按提交粒度逐个过，不要整分支 squash。
3. **包名连字符别名机制**（learning-service/__init__.py）：以 `sys.modules` 副作用注册 `learning-service`/`learning_service` 别名才能被正常 import，可行但隐晦；docstring 已说明。建议架构师后续统一目录名与包名（涉及目录归属，需另行派单）。
4. **已知理论边界登记**（ADR §11.6：n ≥ 159 极端分布下"对 1 题"可能舍入为 0.0 与全错同分）：建议评测官在评测集层面登记为已知局限，防止未来被当回归。

## 风险等级

**低。** 理由：纯函数、无 I/O、无存储、无数据库迁移、不涉及权限/支付/学生数据出口；红线上限由规则引擎纯数值比较实现，且有 25 个行为锁定测试与 ADR 数学证明（§5.3/§5.4）双重支撑。唯一残留风险是 AC-04 打桩强度（建议项 1），属测试加固而非行为缺陷。

未完成项：无。
