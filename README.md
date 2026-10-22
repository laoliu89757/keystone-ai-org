# 磐石软件（Keystone Software）

> 一个把 AI 编程拆成**公司岗位**来运转的研发编排模板。CEO 派单，质量部独立否决，平台门禁合并，人只批不可逆的事。
> 运行在 [Paseo](https://paseo.sh) 上：一个岗位 = 一个 Agent 配置，一个任务 = 一个 worktree，一次交付 = 一条带证据的回执。

## 这是什么

不是一个框架，是一套**可落地的人机协作编制**：

- **17 个岗位**（CEO + 16 个执行席），每个岗位有名字、角色卡、Paseo 配置、权限边界、验收标准
- **三层强制**：Paseo 工具裁剪 → 本地钩子 → GitHub 分支保护 / CODEOWNERS / 环境审批
- **一套协议**：派单模板、回执模板、评审循环、升级五段式、预算熔断
- 依据：Paseo 官方编排文档 + 《AI Agent 研发工作流规范：角色、权限、AGENTS.md 与 CI 门禁》v1.0

## 5 分钟上手

```bash
# 1) 装编制（幂等，自动备份）
python .paseo/apply_profiles.py --dry-run   # 先看会改什么
python .paseo/apply_profiles.py --prune-legacy   # --prune-legacy 顺便删旧的手工 profile
paseo reload                                # 必须；然后新开/重载 Agent 才生效

# 1.5) 验围栏（秒级）
python scripts/gate_drill.py                # 本机已过 20 项；平台 10 项待 GitHub

# 2) 打开 Paseo，新建会话，选配置「CEO 首席执行官（ceo）」
# 3) 对 CEO 说：
#    做一个 XX 功能。先立项拆任务，按流程派单，把需要我批的列出来。
```

## 目录导航

| 文件 | 内容 |
| --- | --- |
| `AGENTS.md` | **章程**（所有 Agent 必读）：公司做什么、你是谁、规则、DoD、升级格式 |
| `CLAUDE.md` | Claude 系 Agent 的入口指针 + 执行注意 |
| `docs/00-paseo-编排原理.md` | Paseo 编排机制研究笔记（工具、profile、worktree、通信、权限收缩） |
| `docs/01-组织架构.md` | 组织图、17 席岗位总表、模型分工、目录归属 |
| `docs/02-协作协议.md` | 状态机、派单协议、回执协议、worktree 规则、评审循环、通信矩阵、熔断、仲裁 |
| `docs/03-权限矩阵与强制手段.md` | R/W/A/H/X 矩阵、三层门禁、人工审核点 |
| `docs/04-落地清单与演练.md` | 八步落地、平台配置清单、10 项门禁演练、日常节奏、移植步骤 |
| `docs/05-GitHub-平台门禁配置.md` | **Phase C**：三步命令、必需检查、分支保护参数、机器账号、8 项平台演练 |
| `docs/roles/` | **17 张角色卡**（每个岗位的详细设置方法与提示词） |
| `templates/` | 任务单、回执、里程碑报告、PR 模板 |
| `.paseo/config.patch.json` | 岗位 profile 与降权 provider 变体（可手工合并） |
| `.paseo/apply_profiles.py` | 幂等合并脚本（备份 + dry-run） |
| `scripts/hooks/` | `guard_bash.sh`、`guard_paths.sh` 本地钩子（无 jq 时用 `_tool_field.py` 兜底） |
| `scripts/check_org.py` | 五处一致性审计（组织表 / 角色卡 / profile / 钩子 / 章程） |
| `scripts/gate_drill.py` | **门禁演练自动化**（PASS/FAIL/PENDING） |
| `scripts/setup_github.py` | 一键配置分支保护与环境审批（默认 dry-run） |
| `scripts/check_stdlib_only.py` | 产品红线：`learning-service/` 只许标准库 |
| `.github/workflows/ci.yml` | 本仓库 CI：一致性 + 演练 + gitleaks + PR 体量 |
| `docs/board/` | 任务看板、里程碑报告、**门禁演练记录** |
| `CODEOWNERS` | 受保护路径与审批人 |

## 公司花名册

| 代号 | 岗位 | 模型家族 | 一句话 |
| --- | --- | --- | --- |
| `ceo` | CEO 首席执行官 | Claude · high | 唯一派单者，不写代码 |
| `cos` | 幕僚长 ★ | Gemini | 维护章程/角色卡/配置一致性 |
| `cpo` | CPO 首席产品官 | Claude | 可测的验收标准 |
| `cto` | 首席架构师 | Claude · high | 契约、Schema、ADR |
| `backend` | 后端工程师 | Claude | FastAdmin 业务底座 |
| `ai` | 算法工程师 | Claude | 规则引擎 + AI 编排 |
| `fe` | 前端工程师 | Claude | uniapp 多端薄壳 |
| `dba` | DBA 数据库管理员 | Claude | 迁移必可回滚 |
| `qa` | QA 测试工程师 | Claude | 真覆盖，不凑数 |
| `rev` | 独立评审官 | **GLM** | 可否决，跨家族对抗 |
| `sec` | 安全官 CISO | **DeepSeek** | 高危即阻断 |
| `eval` | 评测官 | **Gemini** | 基线只增不减 |
| `editor` | 内容质检总监 | **Gemini** | 教错了比崩了更贵 |
| `sre` | SRE 运维工程师 | GLM | 门禁必须真会拦人 |
| `oncall` | 值班工程师 | Gemini | 只诊断，不热修 |
| `writer` | 技术文档工程师 | Gemini | 文档只写已合并的事 |
| `legal` | 合规官 | Claude | 只出清单，结论人批 |

★ = 可选席。质量部四个岗位（rev/sec/eval/editor）与开发线**不同模型家族**，这是设计而非巧合。

## 为什么这样设计

1. **职责分离**：作者不批准自己的产物；评审、安全、评测换模型家族，避免同源盲点。
2. **权限由平台强制**：工具裁剪只是减少误操作，分支保护 / CODEOWNERS / 环境审批才是边界。
3. **门禁机器可验证**：完成定义是可自动检查的条件，Agent 不能改门禁本身。
4. **超限就升级**：重试 ≤3、否决 ≤3、超预算即停，用五段格式交给人。
5. **人只在不可逆处签字**：生产发布、生产迁移、密钥权限、付费、数据外发、合规结论、门禁变更。

## 已知坑（Windows / Paseo）

- 改完 `~/.paseo/config.json` 必须 `paseo reload`，且**新开或重载 Agent** 才拿到新工具目录。
- 若 `create_agent` 报 provider 不存在：把 profile 的 `provider` 从 `claude-lead/claude-worker/pi-worker` 改回 `claude`/`pi`（工具裁剪会失效，此时必须依赖钩子 + 平台两层）。
- 传 worktree 路径用绝对路径；不要给子 Agent 传与父会话相同的 cwd。
- `paseoTools` 只裁剪工具目录，**不是安全边界**（对有 shell 的 Agent）。
- 模型额度是消耗品：派单前先查 `docs/01-组织架构.md` 的**模型可用性台账**（2026-10-21 实测：`codecraft/deepseek-v4-pro`、`cbcn/deepseek-v4-flash`、`tokenrouter/z-ai/glm-5.3-free`、`agnes/*` 均不可用）。降级顺序：同岗位备选 → gemini-3.8-flash → 升级给人，**不得降级门禁**。
- **pi 系岗位没有本地钩子**（钩子由 `.claude/settings.json` 驱动，只对 claude 系生效）。pi 岗位的目录边界靠 Paseo 工具裁剪 + 评审 + CODEOWNERS 兜底，派单时必须把可写目录写进 prompt。

## 维护

- 编制审计（五处一致性：组织表 / 角色卡 / profile / 钩子白名单 / CODEOWNERS）由幕僚长每月做一次，脚本：`python scripts/check_org.py`（退出码非 0 = 有差异）。
- 任何门禁改动后重跑 `docs/04-落地清单与演练.md` 的 10 项演练。
- 章程变更写入 `AGENTS.md` 第 12 节变更记录。
