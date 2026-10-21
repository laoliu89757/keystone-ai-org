# 任务单 <T-编号>：<标题>

> CEO 派单用模板。填不出来的项 = 这个任务还不该派。

角色：<岗位名>（代号 <code>）
上级：CEO
工作区：<worktree 绝对路径 / 沿用 CEO 工作区>
分支：agent/<code>/<T-编号>-<简述>
依赖任务：<T-编号 或 无>

## 目标（一句话，可验证）

## 验收标准（每条都能被机器或人检查）

1.
2.

## 范围

- 允许修改：<目录/文件>
- 禁止修改：<受保护路径 + 他人目录>

## 依赖与契约

- 接口：`openapi.yaml#<操作>` / `schemas/<x>.json`
- 相关 ADR：`docs/adr/<x>.md`
- 相关需求：`docs/requirements/<x>.md`

## 必须跑通的检查（本地）

```bash
<命令 1>
<命令 2>
```

## 预算

- 返工/重试：≤ 3 轮
- 时间：≤ <N> 小时
- token：≤ <N>

## 升级条件

见 `AGENTS.md` 第 8 节；触发即停，按五段格式回报 CEO。

## 交付方式

1. 提交到本任务分支并 push
2. 开 PR（用 `.github/pull_request_template.md`）
3. 按 `templates/status-report.md` 发回执给 CEO
4. 禁止合并主干、禁止改受保护路径
