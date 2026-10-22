# Phase C 推进计划：把平台门禁推到『只剩业主单击』

> 执行人：CEO（编制与文档工作，未派子 Agent）　日期：2026-10-22　预算：40 分钟
> 依据：`docs/05-GitHub-平台门禁配置.md` + `docs/04-落地清单与演练.md` §2/§3

## 0 现状快照（本机已核实）

| 项 | 结果 |
| --- | --- |
| `gh auth status` | **未登录任何 GitHub 主机**（exit=1）→ 建仓/推送/门禁 API 全部卡在这 |
| ci.yml job 名 vs `setup_github.py --checks` | **严格一致** ✅：`org-consistency` / `pytest` / `pr-size` / `secrets`（脚本默认 `REQUIRED_CHECKS` 同名同序）。无需修改，"Expected 永不通过"风险不存在 |
| `python scripts/setup_github.py --dry-run` | 在 gh 登录检查处停下（预期行为），输出：`[x] gh 未登录。先执行：gh auth login` |
| `python scripts/gate_drill.py` | PASS 22 / FAIL 0 / **PENDING 10**（全部指向 GitHub 平台层） |
| 密钥扫描（e 项） | **干净** ✅：无 AKIA+16 位、无 ghp_/gho_、无 PEM 私钥、无 sk-、无被跟踪的 .env/secrets 文件；无 `.gitleaks.toml`（首次推送后 gitleaks 全历史扫描，当前历史未见误报源）。唯一注意：`docs/05` §5 的演练说明里有字面 "AKIA" 但不带 16 位后缀，不触发 gitleaks |

## 1 业主命令清单（按顺序执行）

```powershell
cd G:\latest-projects\ai_agents

# ① 登录 GitHub（浏览器交互一次，只此一步需要人守着）
gh auth login        # 选 GitHub.com → HTTPS → Login with a web browser

# ② 【推送前一次性】把 CODEOWNERS 里的 @project-owner 换成你的真实 GitHub 用户名
#    （CODEOWNERS 是受保护路径，Agent 无权改，必须你手工编辑；不改则 CODEOWNERS 不生效）
#    文件里共 15 处 @project-owner，全部替换为 @<你的用户名>

# ③ 建私有仓库并推送 main（默认私有，符合要求）
gh repo create keystone-ai-org --private --source . --push

# ④ 门禁配置：先预览再应用
python scripts/setup_github.py --dry-run
python scripts/setup_github.py --apply

# ⑤ 建两个机器账号并拉进仓库（网页操作，见 §2），然后跑 8 项演练（见 §3）
```

### 私有仓库 403 备选方案（免费私有仓库不支持分支保护 API）

| 方案 | 操作 | 代价 |
| --- | --- | --- |
| B1（推荐） | GitHub Pro（$4/月）后重跑 `--apply` | 付费 |
| B2（免费） | 用 **Rulesets** 替代分支保护：Settings → Rules → Rulesets → New branch ruleset（free 私有仓库可用，支持 required checks + PR 要求；environment 审批不受影响照常配） | 配置入口不同，脚本须改用 Rulesets API |
| B3（不推荐） | 临时公开 → 配好 → 转私有 | 历史公开暴露，违反默认私有要求 |

选 B2 时告诉我，我改 `setup_github.py` 走 Rulesets API（属 scripts/ 改动，SRE 白名单，需你授权后由我直接改或派 SRE）。

## 2 机器账号最小方案（先只建 2 个）

| 账号 | 授权 | 明确不给 | 用途 |
| --- | --- | --- | --- |
| `keystone-dev` | repo Collaborator（write） | admin、environment 审批人、checks:write | 全部开发线 Agent 推分支/开 PR/读检查 |
| `keystone-rev` | repo Collaborator（write）+ **fine-grained PAT 勾 Checks: Read and write** | admin、environment 审批人 | 只给评审 Agent 写 `agent-review` 检查 |

- 两个账号都**不进** production environment 审批人名单（审批人只有你本人）——这是 production 环境的唯一意义。
- PAT 建法：Settings → Developer settings → Fine-grained tokens → 只选 `keystone-ai-org` 仓库 → Repository permissions：`Contents: Read and write` +（仅 rev）`Checks: Read and write`，有效期设短（90 天）。
- 为什么 rev 必须独立账号：开发账号能写 `agent-review` = 自己给自己放行，独立评审线作废。
- 跑顺后再拆 17 席（docs/05 §4）。

## 3 八项平台演练（配完立刻验，逐项对应 docs/04 PENDING 行）

| # | 具体操作 | 期望结果 | docs/04 PENDING → PASS |
| --- | --- | --- | --- |
| 1 | `git push -u origin test/gate-drill-1` → 开 PR（base main） | `pytest` job 红，PR 标 "merge blocked"，不可合并 | #1（失败测试 PR 被 CI 阻断） |
| 2 | 新分支 `test/gate-drill-2`，提交含 `AKIA`+16 位随机大写字母的假密钥文件，开 PR | `secrets` job 红 | #2（假密钥被 gitleaks 阻断）⚠️**此 PR 验完立即关闭，永不合并**——假密钥一旦进 main 历史将永久触发 gitleaks |
| 3 | 直接 `git push origin main`；再 `git push --force origin main` | 服务器端两次都拒绝（remote: error） | #5e（push/force push 平台拒绝） |
| 4 | 用 `keystone-dev` 开一个改 `.github/workflows/ci.yml` 的 PR | 要求你（CODEOWNERS owner）批准才能合并 | #3d（绕过本地钩子后 CODEOWNERS 仍要人批） |
| 5 | 用 `keystone-dev` 的 PAT 调 checks API 写 `agent-review` | 403 Forbidden | #6（开发账号写 agent-review 无权限） |
| 6 | `gh workflow run deploy.yml`（或 merge 后自动 staging→production 流程）不审批 | 工作流停在 "Waiting for approval" | #8（生产部署停待审批） |
| 7 | 用 `keystone-dev`/`keystone-rev` 尝试批准 production | 无批准按钮/403（不在审批人名单） | #9（机器人账号无法批准生产） |
| 8 | PR 里删一条测试或降覆盖率断言 | `pytest` 红 + 评审（你）拒绝 | #4d（降覆盖率阈值被拦）⚠️ 前提：先有一个阈值配置文件进 CODEOWNERS（当前仓库无独立阈值文件，`pyproject.toml`/`pytest.ini` 尚未建，属 #4d 的前置缺口） |

**8 项之外仍有 2 条 PENDING 不在此列**（需另外准备）：#7（eval-gate：缺 `eval-gate.yml` + `evals/baseline/golden.json`，等学习服务接模型后做）、#10（worker 运行时工具目录：下次派 worker Agent 时顺手查其工具列表即可，本地可验）。

## 4 演练分支 test/gate-drill-1（已备）

- 分支已建（本地，基于 main，未 push）：`git branch test/gate-drill-1`。
- 失败用例文件 `tests/test_gate_drill_failure.py` 由你创建（CEO 角色白名单只有 `docs/board/`，`tests/` 归 QA，hooks 会拦我写）。在 main 仓库执行：

```powershell
git checkout test/gate-drill-1
@'
"""门禁演练 #1 专用：必然失败的测试。验证 ci.yml pytest job 会红。验完关 PR，勿合并。"""
def test_gate_drill_expected_failure():
    assert False, "门禁演练 #1：此测试必然失败，用于验证 pytest 门禁会拦（勿合并）"
'@ | Set-Content tests/test_gate_drill_failure.py -Encoding utf8
git add tests/test_gate_drill_failure.py
git commit -m "test(drill): 门禁演练 #1 必然失败用例（勿合并）"
git checkout main
```

- 验证完成后：关 PR #1、删本地与远端 `test/gate-drill-1`/`test/gate-drill-2` 分支；`docs/04` §3 的 PENDING 行逐行改 PASS，记录写 `docs/board/门禁演练-<日期>.md`。

## 5 结论

- **唯一卡点：`gh auth login`（必须业主浏览器交互，Agent 禁止代办）。** 此外全部就绪：检查名一致、dry-run 预期、演练分支已备、密钥干净、机器账号方案与演练步骤齐备。
- 业主合计只需：1 条交互命令（登录）+ 1 次手工替换 CODEOWNERS + 3 条命令（建仓/预览/应用）+ 网页建 2 个机器账号 + 按表演练。
