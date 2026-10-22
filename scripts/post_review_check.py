#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把独立评审官的结论写成 GitHub 检查（agent-review）。

为什么需要它：GitHub 不允许"批准自己的 PR"，单人仓库把 required approvals 设成 1 会死锁。
改为用**必需状态检查**表达评审结论 —— 红灯就合不进去，效果等同否决权，且不需要第二个账号。

用法（在 PR 所在分支上跑）：
    # 结论通过
    python scripts/post_review_check.py --pr 7 --conclusion pass \
        --summary "16/16 AC 覆盖；破坏实验通过；风险低"

    # 结论否决（会阻断合并）
    python scripts/post_review_check.py --pr 7 --conclusion block \
        --summary "AC-04 打桩是假打桩；迁移缺回滚"

    # 只预览不写入
    python scripts/post_review_check.py --pr 7 --conclusion pass --summary "..." --dry-run

凭据（二选一）：
    * 环境变量 GH_TOKEN / GITHUB_TOKEN，需 fine-grained PAT 勾选 Checks: write + Contents: read
    * 已登录的 gh CLI（gh auth login）

注意：**持有该 token 的 Agent 就能伪造通过结论**。所以这个 token 只能交给独立评审官（rev），
开发岗位一律不给 —— 否则独立评审这条线形同虚设。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CHECK_NAME = "agent-review"


def sh(args: list[str], stdin: str | None = None) -> tuple[int, str, str]:
    p = subprocess.run(args, input=stdin, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def api(path: str, method: str = "GET", payload: dict | None = None) -> tuple[int, str]:
    args = ["gh", "api", "--method", method, path, "-H", "Accept: application/vnd.github+json"]
    if payload is not None:
        args += ["--input", "-"]
        return sh(args, json.dumps(payload))[:2]
    return sh(args)[:2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--conclusion", choices=["pass", "block"], required=True)
    ap.add_argument("--summary", required=True, help="一句话结论（会显示在 PR 检查里）")
    ap.add_argument("--details", default="", help="可选：详细说明（Markdown）")
    ap.add_argument("--repo", help="owner/name；省略则用当前仓库")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if sh(["gh", "auth", "status"])[0] != 0 and not os.environ.get("GH_TOKEN"):
        print("[x] 未登录 gh 且没有 GH_TOKEN")
        return 1

    repo = args.repo
    if not repo:
        code, _, err = api("/repos/{owner}/{repo}")
        code, out, err = sh(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"])
        if code != 0:
            print("[x] 无法确定仓库：", err)
            return 1
        repo = out

    code, pr, err = api(f"/repos/{repo}/pulls/{args.pr}")
    if code != 0:
        print(f"[x] 取 PR #{args.pr} 失败：{err}")
        return 1
    pr_data = json.loads(pr)
    head_sha = pr_data["head"]["sha"]
    number = pr_data["number"]

    conclusion = "success" if args.conclusion == "pass" else "failure"
    title = "独立评审：通过" if conclusion == "success" else "独立评审：否决"
    body = args.summary if not args.details else f"{args.summary}\n\n---\n\n{args.details}"

    payload = {
        "name": CHECK_NAME,
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {"title": title, "summary": body[:60000]},
    }

    print(f"仓库   : {repo}")
    print(f"PR     : #{number}  head={head_sha[:10]}")
    print(f"检查   : {CHECK_NAME} → {conclusion}")
    print(f"结论   : {args.summary}")

    if args.dry_run:
        print("\n[dry-run] 未提交")
        return 0

    code, out = api(f"/repos/{repo}/check-runs", "POST", payload)
    if code != 0:
        print("\n[x] 提交检查失败：", out)
        print("    需要 fine-grained PAT 的 Checks: write 权限（classic token 需 repo 范围）")
        return 1
    print("\n✓ 已提交检查（红灯会阻断合并，前提是 agent-review 已设为必需检查）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
