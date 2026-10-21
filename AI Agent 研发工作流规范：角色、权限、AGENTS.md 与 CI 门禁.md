# AI Agent 研发工作流规范：角色、权限、AGENTS.md 与 CI 门禁

版本 v1.0｜2026-10-21｜配套《AI 自适应掌握式教学系统总体设计方案》｜读者：项目负责人（审核人）、DevOps

## 0 使用说明

**目标**：项目负责人只做“必要权限审核”和“标准审核”，其余由 Agent 与 CI 门禁自动完成。

**本文三部分**

- A：每个 Agent 的职责说明与权限矩阵
- B：仓库根目录 AGENTS.md 规范模板（含 PR 模板、子代理示例）
- C：CI 门禁清单与具体配置（分支保护、CODEOWNERS、GitHub Actions、Claude Code 权限与钩子）

**前提假设**：代码托管在 GitHub，CI 使用 GitHub Actions，Agent 执行使用 Claude Code（子代理、钩子、权限配置）。若使用 GitLab 或其他工具，机制相同，配置需自行转换。具体命令与配置语法以所用工具当前版本文档为准，落地前请在测试仓库验证。

**五条总原则**

1. **职责分离**：作者不批准自己的产物；评审、安全、评测使用独立上下文，最好使用不同模型。
2. **权限由平台强制**：分支保护、CODEOWNERS、环境审批、密钥隔离、工具权限，不能只靠提示词约束。
3. **门禁机器可验证**：完成定义是一组可自动检查的条件，Agent 不能修改门禁本身。
4. **超限就升级**：每个任务有 token、时间、重试次数上限，不收敛时停止并升级给人，不空转。
5. **人只在不可逆处签字**：生产发布、生产迁移、密钥与权限、付费、数据外发、合规结论、门禁变更。

## A 角色职责与权限

### A.1 角色总表（共 16 个）

| Agent | 职责与产出 | 完成标准 | 升级给人的条件 |
| --- | --- | --- | --- |
| 编排 Agent | 拆需求为可独立验证的小任务、分派、跟踪进度、处理卡住；产出任务清单与里程碑验收报告 | 任务全部合并，验收报告齐全 | 任务重试超限；需求冲突；需要权限变更 |
| 产品/需求 Agent | 把需求写成用户故事和验收标准；产出 docs/requirements | 每条故事都有可测试的验收标准 | 需求有歧义且影响范围或成本 |
| 架构 Agent | 维护架构、接口契约（openapi、内容块与题目 Schema）、架构决策记录 ADR | 契约校验通过；变更向后兼容或附迁移方案 | 重大技术选型；破坏性接口变更 |
| 后端 Agent（PHP/FastAdmin） | 账号、订单、权益、后台管理 | 通过全部 CI 门禁 | 改权限模型、支付与权益逻辑 |
| 学习服务 Agent（Python） | 学习引擎、AI 编排、RAG、模型网关 | 通过全部门禁，评测集不退化 | 修改掌握判定默认阈值与放行规则 |
| 前端 Agent（uniapp） | 多端 UI、适配层、内容块与题目渲染 | 通过全部门禁，H5 与小程序构建通过 | 涉及支付界面、平台审核相关改动 |
| 数据库 Agent | 迁移脚本、回滚脚本、索引 | 迁移可正向、可回滚，在副本上演练通过 | 任何生产迁移（必批） |
| 测试 Agent | 单测、集成、E2E、契约测试、性能基线 | 覆盖率达标，关键路径有 E2E | 不稳定测试比例超阈值 |
| 评审 Agent（独立） | 代码评审，可否决；风险分级 | 无阻塞问题 | 同一 PR 被否决超过 3 次 |
| 安全 Agent | 依赖漏洞、密钥泄露、注入、权限检查 | 无未处理的高危及以上问题 | 发现高危漏洞或疑似密钥泄露 |
| 评测 Agent | 维护黄金评测集；Prompt、模型、路由变更时跑回归并出对比报告 | 关键指标不低于基线 | 指标下降超阈值；更换模型供应商 |
| 内容质检 Agent | 预检知识点、讲义、题库的语法正确性、答案唯一性、词汇超纲 | 质检通过率达标 | 通过率低于阈值，需人工抽检 |
| DevOps Agent | CI/CD、环境、灰度、监控告警配置 | 测试环境自动部署成功，生产发布包就绪 | 任何生产发布与回滚规则变更 |
| 值守 Agent | 监控线上指标与成本，先诊断，再提修复建议 | 指标在阈值内 | 指标异常；成本超预算；疑似数据事件 |
| 文档 Agent | 文档、接口说明、变更日志与代码同步 | 文档与代码一致 | 无 |
| 合规 Agent | 对照备案、隐私、平台政策清单检查并提醒 | 清单项齐全，待确认项已标记 | 所有合规结论（必批） |

### A.2 权限矩阵

图例：**R** 只读　**W** 可写　**A** 满足门禁后自动通过　**H** 必须人工批准　**X** 禁止

| Agent | 仓库 | 开发分支 | 合并主干 | 测试环境部署 | 生产发布 | 生产数据库 | 密钥 | CI 与门禁配置 | 契约与文档 | 生产指标 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 编排 | R | X（只建任务与分支） | X | X | X | X | X | X | W（任务、报告） | R |
| 产品/需求 | R | X | X | X | X | X | X | X | W（需求文档） | R |
| 架构 | R | X | X | X | X | X | X | X | W（契约、ADR） | R |
| 开发（后端/学习服务/前端） | R | W（仅限本模块目录） | A | X（由流水线触发） | X | X | X | X | W（本模块文档） | X |
| 数据库 | R | W（仅 migrations） | A | X | X | X | X | X | W | X |
| 测试 | R | W（仅 tests） | A | A（仅跑测试环境） | X | X | X | X | W（测试报告） | X |
| 评审 | R | X（只评论） | X（可否决） | X | X | X | X | X | X | X |
| 安全 | R | X | X | X | X | X | X | X | W（报告） | R |
| 评测 | R | W（仅 evals，基准变更为 H） | A | A（仅评测环境） | X | X | X | X | W（评测报告） | X |
| 内容质检 | R | X | X | X | X | X | X | X | W（质检结果） | X |
| DevOps | R | W（仅 .github、infra） | H | A（仅测试环境） | H | X | X（只引用密钥名，不读值） | H | W | R |
| 值守 | R | X | X | X | X | X | X | X | W（报告） | R |
| 文档 | R | W（仅 docs） | A | X | X | X | X | X | W | X |
| 合规 | R | X | X | X | X | X | X | X | W（清单） | X |

**矩阵说明**

- “仅限本模块目录”由 CODEOWNERS、分支保护的路径规则与 Claude Code 的权限配置共同强制。
- 所有 Agent 都没有生产数据库直连权限，生产迁移只能由流水线在你批准后执行。
- Agent 不接触密钥值：CI 通过环境密钥注入，生产密钥只在生产环境可见。
- 修改 CI 与门禁配置只有 DevOps Agent 能提 PR，且 CODEOWNERS 要求你批准。
- 每个 Agent 使用独立的机器人账号（GitHub App 或机器账号），不授予管理员权限。

### A.3 模型搭配建议

| 角色 | 模型选择原则 |
| --- | --- |
| 开发类 | 编码能力强的模型 |
| 评审、安全 | **与开发 Agent 使用不同模型**，避免同源盲点；必要时接入其他厂商模型 |
| 评测、内容质检 | 与被检对象的生成模型不同；批量任务可用低价模型 |
| 编排、架构 | 推理能力强的模型 |
| 值守、文档 | 中小模型即可 |

### A.4 人工审核点清单

**必要权限审核**（任何 Agent 都不能自批）

| 审核点 | 触发 | 你收到的材料 | 强制机制 |
| --- | --- | --- | --- |
| 生产发布 | 每次发布 | 发布说明、测试环境验收结果、回滚方案 | 生产环境的必需审批人 |
| 生产数据库迁移 | 含迁移的发布 | 迁移脚本、回滚脚本、副本演练记录、备份确认 | 同上，迁移随发布流水线执行 |
| 密钥、账号、权限变更 | 开通或调整 | 变更清单与理由 | 仅人工在平台操作，Agent 无权限 |
| 付费服务与预算上调 | 新增或超预算 | 成本估算与用量报告 | 同上 |
| 学生数据外发或更换模型供应商 | 变更 | 数据流向、合规核对结果 | 评测门禁 + CODEOWNERS |
| 删除数据 | 任何删除任务 | 范围与备份 | 工具权限禁止，仅人工执行 |
| 合规结论 | 备案、隐私、平台政策 | 合规 Agent 的清单与待确认项 | 人工确认后才视为完成 |
| 门禁与流水线变更 | 修改 CI、CODEOWNERS、评测基准 | 变更差异与理由 | CODEOWNERS 要求你批准 |

**标准审核**（固定清单，每次一份，由 Agent 事先整理）

| 审核点 | 频率 | 看什么 |
| --- | --- | --- |
| 架构决策记录 | 每个重大选型 | 结论、备选方案、风险 |
| 里程碑验收报告 | 每个里程碑 | 功能完成度、测试与评测指标、遗留问题 |
| 教学内容抽检 | 每批内容发布前，按固定比例抽样 | 讲解与题库的正确性，这是语法教学最大的风险点 |
| 评测对比报告 | 指标变化超阈值时 | 变化原因、影响范围 |
| 高危安全项 | 出现时 | 漏洞详情、修复建议 |

**不需要你处理**：单个 PR 的评审与合并（过门禁即自动）、测试环境部署、依赖小版本升级、文档与变更日志、不触及上述必要权限项的常规缺陷修复。

## B AGENTS.md 规范模板

放在仓库根目录，所有 Agent 每次任务前必读。子目录可放更细的 AGENTS.md（如 backend/AGENTS.md），就近生效。模板中尖括号内容为需替换项。

### B.1 根目录 AGENTS.md

````markdown
# AGENTS.md

## 1. 项目概览
本项目是英语语法 AI 自适应教学系统：FastAdmin(PHP) 业务后台 + Python 学习服务 + uniapp 多端前端。
核心原则：流程由规则引擎决定，AI 只负责讲解、出题、批改、错因诊断；客观题程序判分；服务端为唯一事实来源，客户端是薄壳。

## 2. 必读文档（开始任何任务前）
- docs/design/总体设计方案.md
- docs/adr/ 全部架构决策记录
- openapi.yaml、schemas/（接口、内容块、题目协议中与任务相关的部分）
- 本文件及所在目录的 AGENTS.md

## 3. 目录与归属
```
backend/            PHP / FastAdmin（后端 Agent）
learning-service/   Python 学习服务（学习服务 Agent）
app/                uniapp 多端前端（前端 Agent）
migrations/         数据库迁移（数据库 Agent）
evals/              评测集与基线（评测 Agent）
content/            知识点、讲义、题库（内容质检 Agent 校验）
docs/               文档（文档 Agent）
.github/ infra/     流水线与基础设施（DevOps Agent，需人工批准）
```
只修改自己角色归属的目录；需要改其他目录时，在任务里提出，由编排 Agent 分派。

## 4. 通用规则（所有 Agent）
1. 不确定时先升级，不要猜测需求或擅自扩大范围。
2. 一个 PR 只做一件事；变更行数不超过 600 行，超过需拆分。
3. 分支命名：agent/<角色>/<任务编号>-<简述>；提交信息遵循 Conventional Commits。
4. 所有行为变更必须带测试；修复缺陷必须先有能复现的失败测试。
5. 不得读取、打印、提交任何密钥、令牌、.env 内容；测试只用合成数据，日志不得含学生个人信息。
6. 不得修改：.github/**、CODEOWNERS、评测基线 evals/baseline/**、门禁与覆盖率阈值配置；这类修改只能由 DevOps 或评测 Agent 提 PR 并经人工批准。
7. 不得通过以下方式绕过门禁：跳过或删除测试、降低覆盖率阈值、关闭 lint 规则、改快照使失败通过、使用 --no-verify。
8. 不得执行生产环境命令；不得 force push、对共享分支 reset --hard、批量删除。
9. 新增依赖必须在 PR 描述说明理由，并通过许可证与漏洞扫描。
10. 单任务预算：重试不超过 3 次，时间与 token 不超过任务单设定的上限；超限立即停止并升级。

## 5. 完成定义（DoD）
- [ ] 需求验收标准逐条满足，PR 描述里逐条对应
- [ ] lint、类型检查、单元与集成测试通过
- [ ] 新增或修改的接口已更新 openapi.yaml，契约测试通过
- [ ] 涉及数据库：迁移可回滚，副本演练通过
- [ ] 涉及 Prompt、模型、路由、判定规则：评测集不退化
- [ ] 文档与变更日志已更新
- [ ] 无新增安全告警、无密钥泄露

## 6. 角色专属规则
后端：权限、订单、支付、权益逻辑改动必须升级；所有写接口幂等；掌握度字段对后端只读。
学习服务：放行与路径决策只能由规则引擎产生，不得由 LLM 输出决定；引导阶段标准答案不得放入 Prompt；讲解内容必须来自检索到的课程资料；LLM 输出一律经 Schema 校验，失败重试后降级。
前端：不直接使用 window、document、localStorage，统一走适配层；AI 内容只渲染内容块，不渲染 HTML；新增块类型必须保留“未知类型降级为文本”。
数据库：每个迁移必须有回滚；禁止未经标记的 DROP、TRUNCATE；大表变更说明锁表与耗时评估。
评测：基线只增不减；新增用例须有人工标注依据；评测数据不得写入提示词或训练。
内容质检：客观题答案必须唯一并经程序校验；例句不得超出学段词汇表；发现疑似错误只标记，不自行改写已审核内容。
评审：只评论不改代码；按第 7 节清单逐项评审；高风险改动明确写出风险与建议。

## 7. 评审清单（评审 Agent）
1. 是否满足验收标准，是否超出任务范围
2. 是否绕过门禁或修改了受保护路径
3. 权限、输入校验、注入、越权、敏感信息
4. 幂等、并发、错误处理、降级路径
5. 数据库迁移风险与回滚
6. 测试是否真实覆盖行为，而不是仅凑覆盖率
7. 是否违反本项目领域约束（见第 6 节）

## 8. 升级规则
出现以下情形立即停止并升级给项目负责人：
- 需要修改受保护路径、权限、密钥、付费服务、生产环境
- 需求有歧义且会影响成本、范围或安全
- 同一任务重试超限，或评审被否决超过 3 次
- 发现疑似数据泄露、安全漏洞、教学内容系统性错误
升级格式：【背景】【已尝试】【阻塞点】【可选方案与影响】【建议】

## 9. 编码规范
PHP：PSR-12，phpstan 通过。Python：ruff + mypy 严格。TypeScript：eslint + vue-tsc 严格。提交前本地运行对应检查命令。
````

### B.2 PR 模板（.github/pull\_request\_template.md）

```markdown
## 关联任务
<任务编号与链接>

## 变更说明
<做了什么，为什么>

## 验收标准对应
- [ ] 标准 1：<对应的实现与测试>
- [ ] 标准 2：<...>

## 影响范围
- [ ] 涉及数据库迁移（附回滚说明）
- [ ] 涉及接口契约变更（是否向后兼容）
- [ ] 涉及 Prompt / 模型 / 路由 / 判定规则（附评测对比）
- [ ] 涉及权限、支付、密钥（须人工审核）

## 风险与回滚
<出问题时如何回滚>

## 自检
- [ ] 已通过本地 lint、类型检查、测试
- [ ] 未修改受保护路径（或已说明并等待人工批准）
```

### B.3 任务单模板（编排 Agent 派单用）

```markdown
# 任务 <编号>：<标题>
角色：<后端 / 学习服务 / 前端 / ...>
目标：<一句话>
验收标准：
1. <...>
范围：允许修改 <目录>；禁止修改 <目录>
依赖与契约：<openapi / schema 链接>
预算：重试 ≤ 3 次；时间 ≤ <小时>；token ≤ <上限>
升级条件：见 AGENTS.md 第 8 节
```

### B.4 子代理定义示例（Claude Code，.claude/agents/code-reviewer.md）

```markdown
---
name: code-reviewer
description: 独立代码评审。开发 Agent 提交 PR 后调用。只读，不修改代码，可否决。
tools: Read, Grep, Glob, Bash
model: opus
---
你是独立代码评审员。你没有参与本 PR 的开发，不要假设作者的意图正确。

1. 先阅读 AGENTS.md 与任务单中的验收标准。
2. 用 git diff 查看变更，按 AGENTS.md 第 7 节清单逐项评审。
3. 输出：结论（通过 / 需修改 / 否决）、阻塞问题、建议项、风险等级。
4. 你只能评论，不得修改任何文件，不得运行写操作命令。
```

说明：model 仅为示例，评审 Agent 应与开发 Agent 使用不同模型，必要时通过外部评审服务接入其他厂商模型；Bash 的写操作由 C.5 中的钩子拦截。其他角色的子代理定义结构相同，区别在于 tools 范围与提示词。

## C CI 门禁清单与配置

以下阈值（覆盖率 80%、PR 600 行等）为起步值，按项目实际调整；目录、脚本名与命令均为示例，落地前在测试仓库验证。

### C.1 门禁清单

| 门禁 | 检查内容 | 工具示例 | 阶段 | 失败处理 |
| --- | --- | --- | --- | --- |
| 静态检查 | 格式、lint、类型 | php-cs-fixer + phpstan；ruff + mypy；eslint + vue-tsc | PR | 阻断合并 |
| 单元与集成测试 | 行为正确，覆盖率达标（整体 ≥ 80%，建议改动行 ≥ 90%） | phpunit；pytest-cov；前端测试 | PR | 阻断 |
| 契约校验 | openapi 规范、内容块与题目 Schema、示例数据校验 | spectral；jsonschema 脚本 | PR | 阻断 |
| 迁移检查 | 每个迁移有回滚；无未标记的 DROP、TRUNCATE；临时库 up → down → up | 自写脚本 + MySQL 服务容器 | PR（含迁移时） | 阻断 |
| 密钥扫描 | 仓库与提交历史中的密钥 | gitleaks | PR | 阻断，并通知安全 Agent |
| 依赖漏洞与许可证 | 高危漏洞、禁用许可证 | composer audit；pip-audit；npm audit；trivy | PR + 每日 | 高危阻断 |
| SAST | 注入、不安全用法 | CodeQL | PR + 每周 | 高危阻断 |
| 评测集回归 | 讲解正确性、错因标注、批改一致性、答案泄露与提示词注入攻击集 | evals 套件 | 改动 Prompt、路由、引擎、评测时 | 指标下降超阈值或硬性项失败则阻断 |
| 多端构建 | H5、微信小程序构建与包体积检查 | uniapp 构建脚本 | PR | 阻断 |
| 端到端冒烟 | 登录 → 进入知识点 → 作答 → 判定的主链路 | Playwright（H5） | PR 与测试环境部署后 | 阻断 |
| PR 体量 | 变更行数 ≤ 600 | 脚本 | PR | 阻断，要求拆分 |
| 受保护路径 | 改动流水线、CODEOWNERS、评测基线、支付与权限目录需所有者批准 | CODEOWNERS + 分支保护 | PR | 需人工批准 |
| 独立评审 | 评审 Agent 批准（必需检查 agent-review） | 评审 Agent 通过独立机器人写入检查结果 | PR | 否决则阻断 |
| 灰度指标 | 错误率、延迟、掌握通过率、成本 | 监控 + check\_canary\_metrics 脚本 | 发布 | 超阈值自动回滚 |

### C.2 仓库与环境设置

**主干分支（main）保护规则**

- 禁止直接推送与 force push，所有改动必须经 PR；
- 必需状态检查：backend、learning-service、frontend、contract、migrations、secrets、pr-size、e2e、agent-review，以及路径触发的 eval-gate；
- 必需 1 个审批，受保护路径由 CODEOWNERS 所有者审批；新提交后撤销旧审批；要求对话已解决；要求分支为最新；
- 管理员同样受规则约束，不允许绕过。

**Agent 账号**

- 每个角色使用独立的机器人账号或 GitHub App，仅授予写非保护分支、写 PR、读检查结果；
- 只有评审 Agent 的账号拥有写入 agent-review 检查的权限，开发 Agent 账号没有，避免自己给自己放行；
- 不授予管理员权限，不授予任何 environment 密钥的访问权。

**部署环境（Environments）**

| 环境 | 审批人 | 分支限制 | 密钥 |
| --- | --- | --- | --- |
| eval | 无 | 任意 PR 分支 | 仅放评测专用、有额度上限的模型密钥 |
| staging | 无 | 仅 main | 测试环境密钥 |
| production | **项目负责人（必需）** | 仅 main | 生产密钥，仅此环境可见，管理员不可绕过 |

### C.3 CODEOWNERS

路径为示例，按实际目录调整。

```
# 流水线、门禁、Agent 配置与基础设施：必须项目负责人批准
/.github/                       @project-owner
/.claude/                       @project-owner
/CODEOWNERS                     @project-owner
/infra/                         @project-owner
/scripts/deploy*                @project-owner
/scripts/rollback*              @project-owner

# 评测基线：门禁基准，评测 Agent 不能自批
/evals/baseline/                @project-owner

# 高风险业务：权限、支付、权益
/backend/application/admin/controller/auth/       @project-owner
/backend/application/api/controller/pay/          @project-owner
/backend/application/common/library/entitlement/  @project-owner

# 掌握判定默认阈值与放行规则
/learning-service/engine/mastery_rules/           @project-owner

# 架构决策记录
/docs/adr/                      @project-owner
```

### C.4 GitHub Actions 工作流

**C.4.1 PR 门禁（.github/workflows/ci.yml）**

```yaml
name: ci
on:
  pull_request:
    branches: [main]
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
permissions:
  contents: read

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: root
          MYSQL_DATABASE: test
        ports: ['3306:3306']
        options: >-
          --health-cmd='mysqladmin ping -proot'
          --health-interval=5s --health-timeout=5s --health-retries=10
    steps:
      - uses: actions/checkout@v4
      - uses: shivammathur/setup-php@v2
        with:
          php-version: '7.4'   # 按项目实际版本
          coverage: xdebug
      - run: composer install --no-interaction --prefer-dist
      - run: vendor/bin/php-cs-fixer fix --dry-run --diff
      - run: vendor/bin/phpstan analyse --no-progress
      - run: vendor/bin/phpunit --coverage-clover coverage.xml
      - run: composer audit

  learning-service:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: learning-service
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy .
      - run: pytest --cov=app --cov-fail-under=80
      - run: pip-audit

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: app
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: app/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run type-check
      - run: npm test
      - run: npm run build:h5
      - run: npm run build:mp-weixin
      - run: npm audit --audit-level=high

  contract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npx --yes @stoplight/spectral-cli lint openapi.yaml
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install jsonschema pyyaml
      # 校验内容块、题目、流式事件 Schema 及其示例数据
      - run: python scripts/validate_schemas.py

  migrations:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: root
          MYSQL_DATABASE: test
        ports: ['3306:3306']
        options: >-
          --health-cmd='mysqladmin ping -proot'
          --health-interval=5s --health-timeout=5s --health-retries=10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      # 检查：每个迁移有回滚；无未标记的 DROP/TRUNCATE；在临时库执行 up -> down -> up
      - run: python scripts/check_migrations.py

  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  pr-size:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: |
          changed=$(git diff --numstat origin/${{ github.base_ref }}...HEAD | awk '{s+=$1+$2} END {print s+0}')
          echo changed lines: $changed
          if [ $changed -gt 600 ]; then echo 'PR exceeds 600 lines, please split'; exit 1; fi

  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f docker-compose.ci.yml up -d --wait
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npx playwright install --with-deps chromium
      - run: npx playwright test
```

说明：CodeQL 在仓库的代码安全设置中启用默认配置，并把结果设为必需检查；依赖漏洞每日扫描可另建定时工作流或使用 Dependabot。

**C.4.2 评测集门禁（.github/workflows/eval-gate.yml）**

仅在改动 Prompt、路由、学习引擎或评测集时触发。评测使用独立的 eval 环境密钥，额度有上限。

```yaml
name: eval-gate
on:
  pull_request:
    paths:
      - 'learning-service/prompts/**'
      - 'learning-service/routing/**'
      - 'learning-service/engine/**'
      - 'evals/**'
permissions:
  contents: read

jobs:
  eval:
    runs-on: ubuntu-latest
    environment: eval
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip
      - run: pip install -r learning-service/requirements-dev.txt
      - name: run golden evals
        env:
          LLM_GATEWAY_URL: ${{ secrets.EVAL_GATEWAY_URL }}
          LLM_GATEWAY_KEY: ${{ secrets.EVAL_GATEWAY_KEY }}
        run: python -m evals.run --suite golden --out eval-result.json
      # 自写脚本：核心指标较基线下降超过 max-drop 即失败；
      # hard-fail 列出的指标（答案泄露、提示词注入）任一失败即阻断
      - name: compare with baseline
        run: >-
          python -m evals.compare --result eval-result.json
          --baseline evals/baseline/golden.json
          --max-drop 0.02 --hard-fail answer_leak,prompt_injection
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: eval-result
          path: eval-result.json
```

**C.4.3 发布工作流（.github/workflows/deploy.yml）**

测试环境随 main 合并自动部署；生产只能手动触发，并停在 production 环境的人工审批处。

```yaml
name: deploy
on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      ref:
        description: 要发布的提交或标签
        required: true
permissions:
  contents: read

jobs:
  staging:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - run: scripts/deploy.sh staging
      - run: scripts/smoke_test.sh staging

  production:
    if: github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    environment: production   # 必需审批人：项目负责人
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ inputs.ref }}
      - run: scripts/backup_db.sh production
      - run: scripts/migrate.sh production up
      - run: scripts/deploy.sh production --canary 5
      # 观察窗口内错误率、延迟、掌握通过率、成本任一超阈值则失败
      - run: scripts/check_canary_metrics.sh --window 30m
      - run: scripts/deploy.sh production --full
      - name: auto rollback
        if: failure()
        run: scripts/rollback.sh production
```

注意：

- 自动回滚只回滚应用版本，数据库不自动回退，因此迁移必须向前兼容（先扩展后收缩，旧版本代码仍能运行），破坏性变更拆成多次发布；
- workflow\_dispatch 虽然有写权限的账号都能触发，但会停在 production 环境审批处，审批人只有你，机器人账号不在审批人名单内；
- 部署脚本只引用环境密钥名，脚本本身在 CODEOWNERS 保护之下。

### C.5 Claude Code 权限与钩子

分三道防线：权限配置是第一道，钩子是第二道，平台的分支保护、CODEOWNERS、环境审批是最后一道。本地配置可能被改动，所以最后一道必须放在平台上，.claude 目录本身也列入受保护路径。

**.claude/settings.json**

```json
{
  "permissions": {
    "allow": [
      "Bash(git status)",
      "Bash(git diff:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(pytest:*)",
      "Bash(ruff:*)",
      "Bash(mypy:*)",
      "Bash(npm run lint)",
      "Bash(npm test:*)",
      "Bash(vendor/bin/phpunit:*)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Edit(./.github/**)",
      "Edit(./.claude/**)",
      "Edit(./CODEOWNERS)",
      "Edit(./evals/baseline/**)",
      "Bash(git push --force:*)",
      "Bash(git push -f:*)",
      "Bash(git reset --hard:*)",
      "Bash(rm -rf:*)",
      "Bash(curl:*)",
      "Bash(ssh:*)",
      "Bash(kubectl:*)",
      "Bash(mysql:*)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {"matcher": "Bash", "hooks": [{"type": "command", "command": ".claude/hooks/guard_bash.sh"}]},
      {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": ".claude/hooks/guard_paths.sh"}]}
    ]
  }
}
```

DevOps Agent 使用单独配置，去掉对 .github 的 deny，但其改动仍必须经 CODEOWNERS 批准；.claude 目录对所有 Agent 保持禁止修改。规则语法以所用 Claude Code 版本的文档为准。

**.claude/hooks/guard\_bash.sh**（退出码 2 表示阻止本次调用，stderr 会反馈给 Agent）

```bash
#!/usr/bin/env bash
cmd=$(jq -r '.tool_input.command // empty')
if echo "$cmd" | grep -Eiq 'drop (table|database)|truncate |git push[^|]*( main| master)|--no-verify|chmod -R 777'; then
  echo '被拦截：该操作需要项目负责人批准，请升级。' >&2
  exit 2
fi
exit 0
```

**.claude/hooks/guard\_paths.sh**（受保护路径 + 按角色限制可写目录，角色通过环境变量 AGENT\_ROLE 传入）

```bash
#!/usr/bin/env bash
file=$(jq -r '.tool_input.file_path // empty')
rel=${file#"$CLAUDE_PROJECT_DIR"/}

# 1) 受保护路径：任何 Agent 都不能改
case "$rel" in
  .github/*|.claude/*|CODEOWNERS|infra/*|evals/baseline/*|.env*)
    echo '被拦截：受保护路径，修改需项目负责人批准，请升级。' >&2
    exit 2 ;;
esac

# 2) 角色目录白名单
case "$AGENT_ROLE" in
  backend)  allow='backend/' ;;
  learning) allow='learning-service/' ;;
  frontend) allow='app/' ;;
  database) allow='migrations/' ;;
  test)     allow='tests/' ;;
  docs)     allow='docs/' ;;
  *)        exit 0 ;;
esac
case "$rel" in
  "$allow"*) exit 0 ;;
  *) echo "被拦截：$AGENT_ROLE 角色只能修改 $allow" >&2; exit 2 ;;
esac
```

### C.6 依赖自动升级（.github/dependabot.yml）

```yaml
version: 2
updates:
  - package-ecosystem: composer
    directory: /backend
    schedule:
      interval: weekly
  - package-ecosystem: pip
    directory: /learning-service
    schedule:
      interval: weekly
  - package-ecosystem: npm
    directory: /app
    schedule:
      interval: weekly
```

小版本与补丁升级的 PR 过全部门禁即可自动合并；大版本升级按普通任务走评审与验收。

### C.7 落地顺序与门禁有效性演练

**落地顺序**

1. 建立仓库规范：AGENTS.md、PR 模板、CODEOWNERS、目录结构。
2. 配置分支保护与部署环境，这一步最先做，之后才让 Agent 改代码。
3. 上线 ci.yml 最小集：静态检查、测试、密钥扫描、PR 体量。
4. 配置 Agent 机器人账号与最小权限，配置 Claude Code 权限与钩子。
5. 加契约校验、迁移检查、端到端冒烟。
6. 学习服务开始接入模型后，加 eval-gate 与评测基线。
7. 配置测试环境自动部署与生产审批流程。
8. 做门禁有效性演练。

**门禁有效性演练**（用试验 PR 确认每一道都真的会拦截，每次改动门禁后重做）

| 演练 | 期望结果 |
| --- | --- |
| 提交含失败测试的 PR | CI 阻断合并 |
| 提交含假密钥的提交 | gitleaks 阻断 |
| 开发 Agent 尝试修改 .github 或 CODEOWNERS | 本地钩子拦截；绕过本地后 CODEOWNERS 要求人工批准 |
| 降低覆盖率阈值或删除测试 | 受保护路径或评审阻断 |
| 直接向 main 推送或 force push | 平台拒绝 |
| 开发 Agent 账号尝试写入 agent-review 检查 | 无权限 |
| 修改 Prompt 使答案泄露攻击集失败 | eval-gate 阻断 |
| 触发生产部署但未审批 | 工作流停在待审批 |
| 机器人账号尝试批准生产环境 | 不在审批人名单，无法批准 |
