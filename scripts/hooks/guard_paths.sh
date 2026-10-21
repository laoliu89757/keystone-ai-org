#!/usr/bin/env bash
# PreToolUse(Edit|Write) 钩子：
#   1) 全局受保护路径：任何 Agent 都不能改（改 = 必须人批）
#   2) 角色目录白名单：按 AGENT_ROLE 限制可写目录
# 退出码 2 = 阻止本次调用。AGENT_ROLE 由启动方注入（岗位代号，见 docs/01-组织架构.md）。

set -uo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
payload=$(cat)

if command -v jq >/dev/null 2>&1; then
  file=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
else
  file=$(printf '%s' "$payload" | python "$HERE/_tool_field.py" tool_input.file_path 2>/dev/null || true)
fi
[ -z "$file" ] && exit 0

# 统一成仓库相对路径，兼容 Windows 反斜杠与盘符
file=${file//\\//}
proj=${CLAUDE_PROJECT_DIR:-$(pwd)}
proj=${proj//\\//}
rel=${file#"$proj"/}
rel=${rel#./}

# ---------- 1) 受保护路径 ----------
case "$rel" in
  .github/*|.claude/*|.paseo/*|CODEOWNERS|AGENTS.md|infra/*|evals/baseline/*|.env*|secrets/*)
    cat >&2 <<'EOF'
被拦截：受保护路径。修改它需要项目负责人批准。
- .github/ infra/ scripts/deploy* scripts/rollback*  → 只有 SRE 能提 PR，且需人批
- evals/baseline/                                    → 只有评测官能提 PR，且需人批
- .claude/ .paseo/ AGENTS.md docs/roles/             → 只有幕僚长能提 PR，且需人批
- .env* secrets/                                     → 任何 Agent 都不得读写
请停止并按五段格式升级给 CEO。
EOF
    exit 2 ;;
esac

# ---------- 2) 角色白名单 ----------
case "${AGENT_ROLE:-}" in
  ceo)      allow="" ;;                      # CEO 不写业务文件
  cos)      allow="docs/roles/ AGENTS.md .paseo/" ;;
  cpo)      allow="docs/requirements/" ;;
  cto)      allow="openapi.yaml schemas/ docs/adr/" ;;
  backend)  allow="backend/" ;;
  ai)       allow="learning-service/" ;;
  fe)       allow="app/" ;;
  dba)      allow="migrations/" ;;
  qa)       allow="tests/" ;;
  eval)     allow="evals/" ;;
  sre)      allow=".github/ infra/ scripts/" ;;
  writer)   allow="docs/ CHANGELOG.md" ;;
  rev|sec|editor|oncall|legal) allow="" ;;   # 只读岗位，任何写入都拦
  *) exit 0 ;;                               # 未声明角色 = 不启用白名单（仅限人手动调试）
esac

if [ -z "$allow" ]; then
  echo "被拦截：${AGENT_ROLE} 是只读岗位，不得修改任何文件。请把建议写进报告。" >&2
  exit 2
fi

for prefix in $allow; do
  case "$rel" in
    "$prefix"*) exit 0 ;;
  esac
done

echo "被拦截：${AGENT_ROLE} 只能修改 [$allow]，本次目标 $rel。跨部门改动请升级给 CEO 派单。" >&2
exit 2
