# GitHub 平台门禁配置（Phase C）

版本 v1.0｜2026-10-21｜读者：项目负责人、SRE
目标：把 `docs/04` 里 9 项 PENDING 变成真的会拦人的门禁。**这是三层防线里唯一不可绕过的一层。**

---

## 0 三步走（你只需要执行，不需要读完全文）

```powershell
cd G:\latest-projects\ai_agents

# ① 登录 GitHub（浏览器一次）
gh auth login

# ② 建仓库并推送（二选一）
gh repo create keystone-ai-org --private --source . --push
#   ← 私有仓库的分支保护需要 GitHub Pro/Team；免费也能保护公开仓库
#   或者：git remote add origin git@github.com:<你>/keystone-ai-org.git; git push -u origin main

# ③ 一键配置分支保护 + 环境审批（默认 dry-run，看清楚再 --apply）
python scripts/setup_github.py --dry-run
python scripts/setup_github.py --apply
```

脚本会做：main 分支保护（强制 PR / 1 审批 / CODEOWNERS / 必需检查 / 禁强推 / 管理员受限）+ `staging`·`production`·`eval` 三个环境（production 审批人=你）。脚本做完会回读校验并打印结果。

---

## 1 必需检查清单（必须与 ci.yml 的 job 名一致）

| 检查名 | 来自 | 作用 |
| --- | --- | --- |
| `org-consistency` | `ci.yml` | 五处一致（组织表/角色卡/profile/钩子/章程）+ 门禁演练 + 钩子语法 |
| `pytest` | `ci.yml` | `learning-service/` 标准库门禁 + 全部测试 |
| `pr-size` | `ci.yml` | 单 PR ≤600 行 |
| `secrets` | `ci.yml` | gitleaks 密钥扫描（含历史） |

> 产品仓库接管后追加：`backend`、`frontend`、`contract`、`migrations`、`e2e`、路径触发的 `eval-gate`（见 docs/04 §2.4）。

## 2 分支保护参数（脚本里的真实取值）

| 参数 | 值 | 为什么 |
| --- | --- | --- |
| Require a pull request | ✅ | 禁止直推 main |
| Required approvals | 1 | 人是最终审批者 |
| Dismiss stale approvals | ✅ | 新提交后旧批准作废 |
| Require review from Code Owners | ✅ | 受保护路径必须你批 |
| Require status checks (strict) | ✅ | 必须绿 + 分支最新 |
| Require conversation resolution | ✅ | 评审意见不能装作没看到 |
| Enforce for administrators | ✅ | **管理员也不能绕过** |
| Allow force pushes | ❌ | 防改写历史 |
| Allow deletions | ❌ | 防误删 main |

## 3 Environments

| 环境 | 审批人 | 分支限制 | 密钥 |
| --- | --- | --- | --- |
| `eval` | 无 | 任意 | 只放有额度上限的评测密钥 |
| `staging` | 无 | 仅 main（受保护分支） | 测试密钥 |
| `production` | **你（必需）** | 仅 main | 生产密钥，只有此环境可见 |

**机器账号一律不进审批人名单** —— 这是 `production` 唯一的意义。

## 4 机器账号（脚本无权代做，必须你手工）

| 岗位 | 需要 | 不需要 |
| --- | --- | --- |
| 全部 17 席 | 写非保护分支、开 PR、读检查结果、读代码 | 管理员、environment 密钥 |
| **仅 `rev`** | **checks:write**（写 `agent-review` 检查） | push |
| 全部 | — | force push、直推 main、删除环境 |

最小可行做法：先只建两个账号跑通流程 —— `keystone-dev`（开发线共用）、`keystone-rev`（评审专用，带 checks:write）。跑顺了再拆成 17 个。

> 为什么评审必须单独账号：如果开发账号也能写 `agent-review`，就等于自己给自己放行，独立评审整条线作废。

## 5 平台门禁演练（配完立刻验，10 分钟）

| # | 动作 | 期望 |
| --- | --- | --- |
| 1 | 提一个含失败测试的 PR | `pytest` 红 → 不可合并 |
| 2 | 提一个含假密钥的提交（`AKIAIOSFODNN7EXAMPLE`） | `secrets` 红 |
| 3 | 直推 main / force push | 被拒绝（服务器端） |
| 4 | 改 `.github/workflows/ci.yml` 的 PR | 要求 CODEOWNERS 批准（你） |
| 5 | 用 `keystone-dev` 账号写 `agent-review` | 403 |
| 6 | 触发 production 部署但不审批 | 工作流停在待审批 |
| 7 | 用机器账号批 production | 不在名单，无法批准 |
| 8 | 降覆盖率/删测试 | `pytest` 或评审阻断 |

演练结果记入 `docs/board/门禁演练-<日期>.md`，把 `docs/04` §3 的 PENDING 逐行改 PASS。

## 6 常见失败

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| 分支保护 API 403 `Upgrade to GitHub Pro` | 私有仓库免费版不支持 | 升级 / 改公开仓库 / 用 Rulesets（部分功能免费） |
| 必需检查显示 "Expected" 永不通过 | 检查名与 job 名不一致 | 对齐 `ci.yml` 的 `name:` 与脚本 `--checks` |
| `secrets` 检查不给 PR 跑 | 私有仓库 fork PR 无 secrets | 改为 `pull_request_target` 或只在同仓 PR 上跑 |
| gitleaks 报了历史里的假密钥 | 历史提交含示例密钥 | 用 `.gitleaks.toml` 加 allowlist，**不要**改写历史 |
| CODEOWNERS 不生效 | 文件路径或用户名错、不在 main 上 | 确认 `CODEOWNERS` 已合并到 main 且 `@project-owner` 换成真实账号 |

## 7 与三层防线的关系

```
① Paseo paseoTools 裁剪    → 少给工具（防误操作）
② 本地 hooks               → 拦危险命令与越界路径（防手滑）
③ GitHub 分支保护/CODEOWNERS/环境审批 → 不可绕过（唯一的真边界）
```

前两层 Agent 都能想办法绕（改配置、换模式），**只有第三层绕不过**。所以：
- 平台门禁没配完之前，不要让 Agent 合并任何东西；
- 每次改门禁后，重跑第 5 节的 8 项演练；
- `.github/` 与 `CODEOWNERS` 本身列入受保护路径。
