#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase C：用 gh CLI 一键落地 GitHub 平台门禁（分支保护 + 环境审批）。

前置：gh 已登录（gh auth status 通过）、仓库已推送到 GitHub、main 分支已存在。

用法：
    python scripts/setup_github.py --dry-run          # 只打印将要执行的请求（默认就是 dry-run）
    python scripts/setup_github.py --apply            # 真正写入
    python scripts/setup_github.py --apply --repo owner/name

做的事：
  1. main 分支保护：禁止直推/强推/删除、必须 PR、1 个审批、CODEOWNERS 审批、
     新提交撤销旧审批、对话必须解决、分支必须最新、管理员同样受限、要求下列必需检查。
  2. Environments：staging（无审批）、production（必需审批人=当前 gh 用户）、eval（无审批）。
  3. 打印需要人工完成的事项（机器账号、Agent 权限）。

不做的事（故意）：创建仓库、推送代码、创建机器账号 —— 前者需要你授权，后者需要你的组织策略。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REQUIRED_CHECKS = ["org-consistency", "pytest", "pr-size", "secrets"]


def sh(args: list[str], stdin: str | None = None) -> tuple[int, str, str]:
    p = subprocess.run(args, input=stdin, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def gh_json(args: list[str], stdin: str | None = None) -> tuple[int, dict | list | None, str]:
    code, out, err = sh(["gh"] + args, stdin)
    if code != 0:
        return code, None, err or out
    try:
        return 0, json.loads(out), ""
    except json.JSONDecodeError:
        return 0, None, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="owner/name；省略则用当前目录的仓库")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--apply", action="store_true", help="真正写入（默认 dry-run）")
    ap.add_argument("--dry-run", action="store_true", help="显式声明只预览（默认行为）")
    ap.add_argument("--checks", default=",".join(REQUIRED_CHECKS))
    args = ap.parse_args()

    if args.dry_run:
        args.apply = False
    mode = "APPLY" if args.apply else "DRY-RUN"
    print("=" * 66)
    print(f"GitHub 平台门禁配置 · {mode}")
    print("=" * 66)

    # 0) gh 可用性与登录
    code, out, err = sh(["gh", "auth", "status"])
    if code != 0:
        print("[x] gh 未登录。先执行：gh auth login")
        print(err or out)
        return 1

    # 1) 解析仓库
    repo = args.repo
    if not repo:
        code, data, err = gh_json(["repo", "view", "--json", "nameWithOwner"])
        if code != 0 or not isinstance(data, dict):
            print("[x] 无法确定仓库（当前目录可能还不是 GitHub 仓库）：", err)
            print("    请先 git remote add origin … && git push -u origin main，或显式传 --repo owner/name")
            return 1
        repo = data["nameWithOwner"]
    print(f"仓库      : {repo}")
    print(f"分支      : {args.branch}")
    print(f"必需检查  : {args.checks}")

    checks = [c.strip() for c in args.checks.split(",") if c.strip()]

    # 2) 当前用户 id（production 审批人）
    code, user, err = gh_json(["api", "user"])
    user_id = user.get("id") if isinstance(user, dict) else None
    user_login = user.get("login") if isinstance(user, dict) else None
    if user_id is None:
        print("[!] 取不到当前用户 id，production 环境审批人将跳过（可稍后手动设置）")

    # 3) 分支保护
    protection = {
        "required_status_checks": {"strict": True, "contexts": checks},
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "required_approving_review_count": 1,
        },
        "restrictions": None,
        "required_conversation_resolution": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "allow_linear_history": False,
    }
    print("\n[1] 分支保护 PUT /repos/%s/branches/%s/protection" % (repo, args.branch))
    print(json.dumps(protection, ensure_ascii=False, indent=2))
    if args.apply:
        code, data, err = gh_json(
            ["api", "--method", "PUT",
             f"/repos/{repo}/branches/{args.branch}/protection",
             "-H", "Accept: application/vnd.github+json",
             "--input", "-"],
            stdin=json.dumps(protection),
        )
        print("    →", "OK" if code == 0 else f"失败: {err}")
        if code != 0 and "Upgrade to GitHub Pro" in err:
            print("    提示：私有仓库的分支保护需要 GitHub Pro/Team；公开仓库免费可用。")
    else:
        print("    （dry-run 未写入）")

    # 4) Environments
    envs = [
        ("staging", None),
        ("production", user_id),
        ("eval", None),
    ]
    for name, reviewer_id in envs:
        payload: dict = {}
        if reviewer_id:
            payload["reviewers"] = [{"type": "User", "id": reviewer_id}]
            payload["deployment_branch_policy"] = {
                "protected_branches": True,
                "custom_branch_policies": False,
            }
        print(f"\n[2] 环境 PUT /repos/{repo}/environments/{name}")
        print(json.dumps(payload if payload else {"note": "无审批人，仅分支限制缺失"}, ensure_ascii=False))
        if args.apply:
            code, _, err = gh_json(
                ["api", "--method", "PUT", f"/repos/{repo}/environments/{name}",
                 "-H", "Accept: application/vnd.github+json", "--input", "-"],
                stdin=json.dumps(payload),
            )
            suffix = f"（审批人 {user_login}）" if reviewer_id else ""
            print("    →", ("OK" if code == 0 else f"失败: {err}") + suffix)

    # 5) 校验
    if args.apply:
        print("\n[3] 回读校验")
        code, data, err = gh_json(["api", f"/repos/{repo}/branches/{args.branch}/protection"])
        if code == 0 and isinstance(data, dict):
            print("    强制 PR      :", "on" if data.get("required_pull_request_reviews") else "off")
            print("    管理员受限    :", data.get("enforce_admins", {}).get("enabled"))
            print("    必需检查      :", (data.get("required_status_checks") or {}).get("contexts"))
            print("    允许强推      :", data.get("allow_force_pushes", {}).get("enabled"))
        else:
            print("    回读失败：", err)

    print("\n" + "-" * 66)
    print("还需要你手工做的（脚本无权代做）：")
    print("  1) 给 17 个岗位建 GitHub App / 机器账号，只授予：写非保护分支、开 PR、读检查结果；")
    print("     只有 rev 的账号授予 checks:write（能写 agent-review 检查）。")
    print("  2) 在仓库 Settings → Actions 里确认工作流有权限（默认 GITHUB_TOKEN 只读即可）。")
    print("  3) 推送代码后，提一个故意的失败 PR 验证门禁真的会拦（docs/04 §3 演练 1/2/5e/3d）。")
    print("  4) 若仓库是私有的且没有 GitHub Pro：分支保护 API 会返回 403，需升级或改公开仓库。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
