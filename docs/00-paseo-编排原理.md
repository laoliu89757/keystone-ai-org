# Paseo 编排原理（研究笔记）

来源：https://paseo.sh/zh-CN/docs/orchestration 及其子页（orchestration-workflows、agent-profiles、mcp、worktrees、skills、cli）
整理日期：2026-10-21　用途：本仓库所有编排设计的事实依据。凡与官方文档冲突，以官方文档为准。

---

## 1 一句话结论

Paseo 把「一个 Agent 指挥多个 Agent」做成了一等公民：**工作区决定活在哪干，父子关系决定活归谁**。
编排者（本仓库称 CEO）通过 MCP 工具或 CLI 启停下级、选择 Provider/模型、分配 worktree、按 agentId 收发提示词；完成/报错/要权限会自动通知父 Agent，因此不需要轮询。

## 2 五个原语

| 原语 | 机制 | 本仓库用法 |
| --- | --- | --- |
| **Provider** | 每台主机配置多个 Provider（claude、pi、codex…），各自有模型、模式、思考级别、feature | CEO=claude 高推理；评审/安全/评测=pi 上的**不同模型家族** |
| **Agent 配置（profile）** | 一组保存好的启动设置 + `notes`（适用场景说明）。`list_profiles` 会把 notes 暴露给编排者 | 一个岗位 = 一个 profile，profile.notes 就是"招聘说明书"，CEO 据此选人 |
| **工作区 / worktree** | 顶层调用者新建工作区；worktree 隔离可分支出新分支、检出分支或 PR。每个 worktree 是独立检出 | 每个写代码的任务一个 worktree，互不踩踏；只读任务共用一个工作区 |
| **父子关系** | 不带 `workspaceId` 创建的 Agent 是调用者的子 Agent；带 `workspaceId` 只改变位置，**不改变归属** | 下级永远是 CEO 的子 Agent，工作区只是它的座位 |
| **通知** | 子 Agent 完成/错误/请求权限时父 Agent 自动收到通知（`notifyOnFinish` 默认 true） | CEO 收通知推进流程，**禁止轮询**（官方明确不要 poll） |

## 3 工具目录（编排者实际能调用的东西）

**Agent**
`create_agent`（title、provider（`provider/model`）、initialPrompt、workspaceId、settings.modeId/thinkingOptionId/features、notifyOnFinish、labels）
`send_agent_prompt`（agentId、prompt、activeTurnBehavior=steer|interrupt）
`get_agent_status` / `get_agent_activity` / `list_agents`
`cancel_agent`（停当前轮，保留 Agent）/ `archive_agent`（软删）/ `kill_agent`（终止会话）
`update_agent`（改名、标签、运行时换模型/模式/思考级别）`set_agent_mode`

**工作区**
`create_workspace`（isolation=local|worktree；mode=branch-off|checkout-branch|checkout-pr；branchName/baseBranch|branch|prNumber）`list_workspaces` `rename_workspace` `archive_workspace`
`list/start/stop_workspace_script`（配合 `paseo.json` 起开发服务、端口、健康检查）

**发现**
`list_profiles`（含 notes）`list_providers` `list_models` `inspect_provider`

**权限**
`list_pending_permissions` `respond_to_permission`（父 Agent 可代批——本仓库禁止下级拥有此工具）

**定时**
`create_schedule`（每次新 Agent）/ `create_heartbeat`（给同一个 Agent 续命，保留上下文）/ 全套 schedule 管理工具

**终端 / 浏览器** `create_terminal` `capture_terminal` `send_terminal_keys`；`browser_*`（需显式开启）

## 4 常用编排工作流（官方给的四种骨架）

1. **跨模型委派**：主会话继续规划，把实现丢给另一个 Provider 的工作区。
2. **分头调研（fan-out）**：三个子 Agent 分别查调用链/测试/回归，都回报后主 Agent 综合。共享同一份文件，不开 worktree。
3. **并行编辑不冲突**：两个 issue → 两个 worktree → 各自跑检查 → 主 Agent 汇总两份 diff。
4. **先实现再评审**：实现者与评审者用不同配置（最好不同 Provider），评审者在同工作区的新会话里看 diff。

## 5 通信

- **自动上行**：完成/错误/权限请求 → 父 Agent 收到通知。
- **横向**：`send_agent_prompt` + 对方 `agentId`（跨工作区、跨是否自己启动都行；用户可在 UI 右键「复制 Agent ID」）。由 Agent 发起的发送默认 `steer`（引导当前轮），不可引导时退回 `interrupt`。
- **下行控制**：`send_agent_prompt` 续派、`cancel_agent` 停当前轮保留上下文、`update_agent` 换模型/模式。
- **交接**：`/paseo-handoff` 技能按"接收方要能独立开工"的简报格式移交（文件、进展、决策、约束、验收标准）。

## 6 权限收缩（本仓库最依赖的一条）

`agents.providers.<id>.paseoTools` 可按 **Provider ID** 裁剪工具目录：

```json
{ "paseoTools": { "disabledTools": ["create_agent", "kill_agent"] } }
{ "paseoTools": { "enabled": false } }
```

配合 `extends` 可以造出 `claude-worker`、`pi-worker` 这类**同一 Provider 的降权变体**，从而做到「执行者不能自己派单、不能给自己批权限、不能给自己换更贵的模型」。

⚠️ 官方明示：这只裁剪了工具目录，**对有 shell 权限的 Agent 不是安全边界**。真正的边界必须在 GitHub（分支保护 / CODEOWNERS / environment 审批）+ 本地钩子。

## 7 由此得出的 8 条设计结论

1. **岗位 = profile**：不写死"谁是谁"，而是把岗位固化成 profile，CEO 用 `list_profiles` 读 notes 选人 — 换模型不用改流程。
2. **角色卡靠 initialPrompt 注入**：`create_agent` 没有"角色"参数，所以派单时必须显式写「你是哪个岗位、先读本仓库哪张角色卡」。
3. **编排者只做编排**：CEO 拿全量工具；执行者用 `*-worker` 降权 Provider，禁用 `create_agent / respond_to_permission / update_agent`。
4. **写并发靠 worktree，不靠自律**：写代码任务一个 worktree 一个分支；只读任务共用工作区。
5. **走通知不走轮询**：`notifyOnFinish` 默认开，CEO 靠通知推进；长任务用 `create_heartbeat` 定期自我推进，禁止 sleep 轮询。
6. **评审必须换家族**：用 pi 上的 DeepSeek/GLM/Gemini 与 claude 开发线形成跨家族对抗；同一个 worktree、新会话、只读。
7. **修复用 steer，不用重开**：评审要改时 `send_agent_prompt` 回给原实现者，保留上下文更省；重试 ≤3 轮后升级。
8. **平台是最后一道门**：Paseo 工具裁剪 → 本地钩子 → 分支保护/CODEOWNERS/Environment 审批，三层缺一不可。
