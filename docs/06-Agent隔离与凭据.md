# Agent 隔离与凭据分级

版本 v1.0｜2026-10-22｜读者：项目负责人、SRE、幕僚长

> 本文回答一个容易被忽略的问题：**规则写在本地，为什么还要平台？**
> 结论先说：**本地层是"防手滑"，平台层才是"边界"**。凡是 Agent 能读到凭据的地方，规则都不算数。

---

## 1 一个必须承认的事实

本仓库的规则全部住在本地：

| 载体 | 谁能改 |
| --- | --- |
| `AGENTS.md`、`docs/roles/*.md` | 任何有本机写权限的进程（`guard_paths.sh` 只拦 Claude 的 `Edit/Write` 工具调用） |
| `scripts/hooks/*.sh` | 同上 |
| `.claude/settings.json`（allow/deny） | 同上 |
| `~/.paseo/config.json`（`paseoTools` 裁剪、17 个 profile） | 同上，一条 `python -c "…open(…,'w')"` 就能改 |

也就是说：**约束文件和被约束对象在同一台机器、同一个 OS 用户下。**

本项目真实发生过：编写本套编制期间，`AGENTS.md`、`.claude/settings.json`、`.paseo/config.json` 被改了十几次，**钩子一次都没触发** —— 因为改它们的进程不走 Claude 的工具调用通道。

## 2 所以三层各自负责什么

| 层 | 定位 | 能拦住 | 拦不住 |
| --- | --- | --- | --- |
| 提示词（章程、角色卡） | 让 Agent **知道**规矩 | 听话的模型 | 忘了 / 被说服 / 判断失误 |
| 本地钩子 + `paseoTools` | **防手滑与幻觉**，毫秒级反馈 | 改错目录、误跑 `DROP`、`--no-verify` | 能跑任意命令、能改文件的进程 |
| GitHub 分支保护 / 环境审批 | **唯一的边界** | 所有人，包括管理员 | 拿到你凭据的 Agent |

**推论（写进纪律）**：

1. 不要继续在本地堆规则来追求安全，收益递减、维护成本递增。
2. 判断"某个限制是否有效"的唯一标准：**它是否落在 Agent 拿不到凭据的地方**。
3. 本地层仍然值得做，理由是可读的错误信息、极低成本、拦截高频误操作。

## 3 凭据分级（当前最重要的一张表）

本机上的敏感凭据与暴露面：

| 凭据 | 位置 | Agent 能读到吗 | 允许谁用 |
| --- | --- | --- | --- |
| GitHub 登录态（`gh auth`） | `~/.config/gh/hosts.yml` | **能**（同一个 OS 用户） | **只有人**。Agent 不该用它 |
| `agent-review` 状态写入 token | 环境变量 / 密钥库 | 取决于注入方式 | **只有 rev**（权限只到 commit status） |
| 部署密钥 / SSH key | `~/.ssh` | **能** | **没有人以外的任何角色** |
| 生产环境 secrets | GitHub `production` environment | 不能（GitHub 侧隔离） | 只有流水线，且需人审批 |
| 模型 API key（DeepSeek/GLM/…） | `~/.pi/agent/models.json`、Paseo 配置 | **能** | 各岗位模型调用；**不得出现在代码/日志/提示词** |
| 学生真实数据 | 生产库 | 不能（Agent 无直连权限） | 只有人 |

**硬规则（违反即重大事故）**：

1. **任何 Agent 不得持有 GitHub 写凭据**（`gh` 登录态、含 `repo` 范围的 PAT、SSH key）。
2. 唯一例外：**rev 的 `agent-review` 写入凭据**，且必须是 fine-grained / 最小权限（只写 commit status，不能推代码）。
3. 该凭据**只注入 rev 会话**，不写进仓库、不写进 `.env`、不进其他岗位的环境。
4. 部署密钥与生产 secrets 一律不进 Agent 环境。

> 为什么第 2 条要给例外：如果没有它，"评审否决"就只能靠 Agent 自觉；有了它，评审结论会变成 `BLOCKED`。代价是持有者能伪造通过 —— 所以它只能给独立评委本身。

## 4 本机硬化（已实现）

`scripts/harden_local.py` 做两件事，都不假装是安全边界，只做"防误改 + 留痕"：

```bash
python scripts/harden_local.py --baseline   # 记录受保护文件的 sha256 → .integrity.json
python scripts/harden_local.py --verify     # 校验是否被改动（CI 也跑）
python scripts/harden_local.py --lock       # 设为只读属性（防工具误写）
python scripts/harden_local.py --unlock     # 解除只读（要改之前先解锁）
```

受保护清单：`AGENTS.md`、`CLAUDE.md`、`CODEOWNERS`、`pytest.ini`、`.claude/settings.json`、`.paseo/config.patch.json`、`docs/roles/*.md`、`scripts/hooks/*`、`.github/workflows/*.yml`。

**局限（必须知道）**：`--lock` 只是文件只读属性，能改文件的进程可以再改回来；`.integrity.json` 也在本地。这一步的价值是**让改动可见**：任何未声明的改动会被 `gate_drill` 与 CI 抓出来。

## 5 真正的本地隔离（按成本排序，做到哪档看风险）

| 档 | 做法 | 效果 | 成本 |
| --- | --- | --- | --- |
| A | 凭据最小化 + 完整性校验（**本仓库现状**） | 评审有强制力；本地改动可见 | 已完成 |
| B1 | 独立 OS 用户跑 Agent（Windows：standard user + 仓库目录 ACL） | 改不了钩子、读不到 `~/.ssh` 与 `gh` 登录态 | 1–2 小时 |
| B2 | WSL2 / 容器内跑 Agent，仓库可写挂载、其余只读 | 最干净、可复现、可随手重建 | 半天 |
| C | 专用机器 / 云上沙箱跑 Agent | 与本机彻底分离 | 高 |

**B1 的最小做法**（Windows）：

```powershell
# 管理员 PowerShell 一次
net user keystone-agent "复杂密码" /add
icacls "G:\latest-projects\ai_agents" /grant "keystone-agent:(OI)(CI)M"
# 之后让 Paseo daemon / Agent 以该用户身份运行（计划任务或 runas 包装）
# 注意：Agent 用户对 ~/.ssh、~/.config/gh、凭据管理器无访问权
```

**判断要不要做到 B 档**：如果 Agent 只做"写代码 + 开 PR"，A 档够；如果 Agent 会跑部署、碰生产、接触学生数据，**必须** B 档以上。

## 6 检查清单（每次改编制后过一遍）

- [ ] 受保护文件改了之后，`python scripts/harden_local.py --verify` 会红；已跑 `--baseline` 并说明理由
- [ ] 新增凭据没有进仓库、没有进 `.env`、没有进提示词
- [ ] 唯一持有 GitHub 写凭据的是 rev（且只到 commit status）
- [ ] `agent-review` 是必需检查，且有人能提交它
- [ ] `docs/03` 的三层表述没有把本地层说成安全边界
