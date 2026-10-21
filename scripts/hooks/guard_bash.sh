#!/usr/bin/env bash
# PreToolUse(Bash) 钩子：拦不可逆 / 越权 / 生产操作。退出码 2 = 阻止本次调用，stderr 反馈给 Agent。
# 用法：.claude/settings.json → {"matcher":"Bash","hooks":[{"command":"bash scripts/hooks/guard_bash.sh"}]}
# 依赖：bash + python3（或 jq）；见同目录 _tool_field.py

set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
payload=$(cat)

if command -v jq >/dev/null 2>&1; then
  cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
else
  cmd=$(printf '%s' "$payload" | python "$HERE/_tool_field.py" tool_input.command 2>/dev/null || true)
fi
[ -z "$cmd" ] && exit 0

block() {
  printf '被拦截：%s\n不要尝试变形绕过；请停止并按五段格式升级给 CEO：\n【背景】【已尝试】【阻塞点】【可选方案与影响】【建议】\n' "$1" >&2
  exit 2
}

# 1) 数据库破坏性操作
echo "$cmd" | grep -Eiq 'drop[[:space:]]+(table|database)|truncate[[:space:]]+table' \
  && block "DROP / TRUNCATE 属于不可逆操作，任何 Agent 都无权执行（生产迁移由流水线在人批准后执行）。"

# 2) 直接连数据库 / 集群 / 远程
echo "$cmd" | grep -Eiq '(^|[;&|][[:space:]]*)(mysql|mysqldump|psql|mongo|redis-cli|kubectl|helm)[[:space:]]' \
  && block "禁止直连数据库 / 集群。需要数据请走平台与流水线，不要在本地连生产。"

# 3) 推主干 / 强推 / 跳过钩子
echo "$cmd" | grep -Eiq 'git[[:space:]]+push[^|;]*(main|master)' \
  && block "禁止直接推 main/master，所有改动必须经 PR 且过门禁。"
echo "$cmd" | grep -Eiq 'git[[:space:]]+push[^|;]*(--force|[[:space:]]-f([[:space:]]|$))' \
  && block "禁止 force push。"
echo "$cmd" | grep -Eiq -- '--no-verify' \
  && block "禁止 --no-verify 跳过钩子。"
echo "$cmd" | grep -Eiq 'git[[:space:]]+reset[[:space:]]+--hard' \
  && block "禁止对共享分支 reset --hard。"

# 4) 危险的文件与权限操作
echo "$cmd" | grep -Eiq 'rm[[:space:]]+-rf[[:space:]]+(/|~|\*)([[:space:]]|$)' \
  && block "禁止批量删除根 / 家目录。"
echo "$cmd" | grep -Eiq 'chmod[[:space:]]+-R[[:space:]]+777' \
  && block "禁止 chmod -R 777。"

# 5) 生产环境操作（部署 / 迁移 / 回滚 / 重启必须由流水线在人批准后执行）
echo "$cmd" | grep -Eiq '(deploy|migrate|rollback|restart|release)[^|;]*(production|--prod([[:space:]]|$)|[[:space:]]prod([[:space:]]|$))' \
  && block "生产环境操作只能由流水线在人工批准后执行，Agent 不得直接执行。"

# 6) 密钥外带
echo "$cmd" | grep -Eiq 'curl[^|;]*(@|--data|-d)[^|;]*(\.env|secrets?/)' \
  && block "疑似外带密钥，禁止。"

exit 0
