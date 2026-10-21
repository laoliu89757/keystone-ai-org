# CLAUDE.md

> Claude Code / Claude 系 Agent 从这里进入。**章程唯一真源是 `AGENTS.md`**，本文件只是指针 + Claude 特有的执行注意项。

## 立刻要做的事

1. 读 `AGENTS.md`（章程、通用规则、DoD、升级格式）。
2. 读你的角色卡 `docs/roles/<序号>-<代号>.md`（任务单里会写你是什么岗位；找不到就问 CEO，不要猜）。
3. 读 `docs/02-协作协议.md` 里与你相关的段落。

## 你的岗位与边界

岗位表见 `AGENTS.md` 第 2 节。边界由三样东西决定，不是由你判断：

- **目录白名单**：`scripts/hooks/guard_paths.sh` 按环境变量 `AGENT_ROLE` 执行，越界写入会被 exit 2 拦掉。
- **工具目录**：执行层 Agent 用 `claude-worker` provider，`create_agent` / `respond_to_permission` / `update_agent` 等工具**根本不存在**。
- **平台**：分支保护、CODEOWNERS、production 环境审批。你在本地怎么绕都没用。

## 执行注意（Claude 特有）

- 不要用 `git push` 推受保护分支；不要 `--no-verify`；不要 `git reset --hard` 共享分支。
- 权限请求一律上报：你没有 `respond_to_permission`，让 CEO 或人批。
- 交付前必须按 `templates/status-report.md` 发回执，含命令与输出证据。
- 不要轮询等待结果（`sleep`、`tail -f`、反复读日志）。Paseo 的完成通知会自己到。
- 任务完成后不要主动合并主干；合并是平台门禁的动作。
