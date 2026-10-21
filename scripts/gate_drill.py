#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docs/04 §3 门禁演练的可执行本地子集。

能自动判定的（本地层）：编制完整性、Provider 工具裁剪、钩子拦截行为。
需要 GitHub 平台的（CI/分支保护/Environments/账号权限）：标 PENDING 并给出落地步骤。

用法：python scripts/gate_drill.py            # 退出码 1 = 有 FAIL
     python scripts/gate_drill.py --json    # 机器可读
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
PASEO_CFG = Path(os.path.expanduser("~/.paseo/config.json"))
HOOKS = ROOT / "scripts" / "hooks"
WORKER_BANNED = [
    "create_agent", "create_schedule", "create_heartbeat", "kill_agent",
    "archive_agent", "archive_workspace", "respond_to_permission",
    "update_agent", "set_agent_mode", "create_terminal",
]
LEGACY = ("码农", "负责制作UI", "出题小能手", "CEO")

results: list[dict] = []


def add(no: str, name: str, status: str, evidence: str, fix: str = "") -> None:
    results.append({"no": no, "name": name, "status": status, "evidence": evidence, "fix": fix})


def bash_path() -> str | None:
    for cand in (shutil.which("bash"), r"D:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\bin\bash.exe"):
        if cand and Path(cand).exists():
            return cand
    return None


def run_hook(script: str, payload: dict, role: str | None) -> tuple[int, str]:
    b = bash_path()
    if not b:
        return -1, "bash 不可用"
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(ROOT).replace("\\", "/"))
    if role:
        env["AGENT_ROLE"] = role
    else:
        env.pop("AGENT_ROLE", None)
    p = subprocess.run([b, str(HOOKS / script)], input=json.dumps(payload, ensure_ascii=False),
                       capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    return p.returncode, (p.stderr or p.stdout or "").strip().splitlines()[0] if (p.stderr or p.stdout) else ""


def load_cfg() -> dict:
    if not PASEO_CFG.exists():
        return {}
    return json.loads(PASEO_CFG.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- A 编制完整性
def drill_setup(cfg: dict) -> None:
    profiles = {p.get("name"): p for p in cfg.get("daemon", {}).get("agentProfiles", [])}
    legacy = [n for n in profiles if n in LEGACY]
    if legacy:
        add("A1", "旧 profile 已清除", "FAIL", f"仍存在: {legacy}", "运行 python .paseo/apply_profiles.py --prune-legacy")
    else:
        add("A1", "旧 profile 已清除", "PASS", f"共 {len(profiles)} 个 profile，无遗留")

    if len(profiles) == 17:
        add("A2", "17 席编制齐备", "PASS", "17/17")
    else:
        add("A2", "17 席编制齐备", "FAIL", f"实际 {len(profiles)} 个", "重跑 apply_profiles.py")

    provs = cfg.get("agents", {}).get("providers", {})
    lead = provs.get("claude-lead", {})
    if lead and not lead.get("paseoTools"):
        add("A3", "CEO 变体保留全量工具", "PASS", "claude-lead 无 paseoTools 限制")
    else:
        add("A3", "CEO 变体保留全量工具", "FAIL", "claude-lead 缺失或被限制")

    for name in ("claude-worker", "pi-worker"):
        banned = set(provs.get(name, {}).get("paseoTools", {}).get("disabledTools", []))
        missing = [t for t in WORKER_BANNED if t not in banned]
        if missing:
            add(f"A4-{name}", f"{name} 禁用危险工具", "FAIL", f"缺: {missing}", "补 paseoTools.disabledTools")
        else:
            add(f"A4-{name}", f"{name} 禁用危险工具", "PASS", f"已禁 {len(banned)}/10")

    wrong = [n for n, p in profiles.items() if "ceo" not in n and not str(p.get("provider", "")).endswith("-worker")]
    if wrong:
        add("A5", "执行岗都跑在降权变体上", "FAIL", f"未用 worker 变体: {wrong}", "改 profile.provider")
    else:
        add("A5", "执行岗都跑在降权变体上", "PASS", "16/16 执行岗 = *-worker")

    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_org.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    add("A6", "五处一致性审计", "PASS" if p.returncode == 0 else "FAIL",
        (p.stdout or "").strip().splitlines()[-1] if p.stdout else "无输出",
        "" if p.returncode == 0 else "看 check_org.py 输出逐项修")

    b = bash_path()
    if not b:
        add("A7", "钩子依赖可用", "FAIL", "找不到 bash", "装 Git for Windows 或配 shellPath")
    else:
        ok = all(subprocess.run([b, "-n", str(HOOKS / f)], capture_output=True).returncode == 0
                 for f in ("guard_bash.sh", "guard_paths.sh"))
        has_jq = shutil.which("jq") is not None
        add("A7", "钩子依赖可用", "PASS" if ok else "FAIL",
            f"bash -n OK；jq {'有' if has_jq else '无 → 走 _tool_field.py 兜底'}")


# ---------------------------------------------------------------- B 门禁演练
def drill_hooks() -> None:
    cases = [
        ("3a", "改 .github/ 被拦", "guard_paths.sh", {"tool_input": {"file_path": str(ROOT / ".github/workflows/ci.yml").replace("\\", "/")}}, "sre", 2),
        ("3b", "改 CODEOWNERS 被拦", "guard_paths.sh", {"tool_input": {"file_path": str(ROOT / "CODEOWNERS").replace("\\", "/")}}, "cos", 2),
        ("3c", "改 AGENTS.md 被拦", "guard_paths.sh", {"tool_input": {"file_path": str(ROOT / "AGENTS.md").replace("\\", "/")}}, "cos", 2),
        ("4a", "只读岗(rev)写入被拦", "guard_paths.sh", {"tool_input": {"file_path": str(ROOT / "docs/review.md").replace("\\", "/")}}, "rev", 2),
        ("4b", "后端写前端目录被拦", "guard_paths.sh", {"tool_input": {"file_path": str(ROOT / "app/pages/x.vue").replace("\\", "/")}}, "backend", 2),
        ("4c", "后端写本模块放行", "guard_paths.sh", {"tool_input": {"file_path": str(ROOT / "backend/app/x.php").replace("\\", "/")}}, "backend", 0),
        ("5a", "git push main 被拦", "guard_bash.sh", {"tool_input": {"command": "git push origin main"}}, None, 2),
        ("5b", "force push 被拦", "guard_bash.sh", {"tool_input": {"command": "git push -f origin feature"}}, None, 2),
        ("5c", "--no-verify 被拦", "guard_bash.sh", {"tool_input": {"command": "git commit -m x --no-verify"}}, None, 2),
        ("2a", "DROP TABLE 被拦", "guard_bash.sh", {"tool_input": {"command": "mysql -e 'DROP TABLE users'"}}, None, 2),
        ("2b", "生产部署被拦", "guard_bash.sh", {"tool_input": {"command": "scripts/deploy.sh production --canary 5"}}, None, 2),
        ("5d", "正常命令放行", "guard_bash.sh", {"tool_input": {"command": "pytest -q"}}, None, 0),
    ]
    for no, name, script, payload, role, expect in cases:
        rc, msg = run_hook(script, payload, role)
        add(no, name, "PASS" if rc == expect else "FAIL",
            f"exit={rc}（期望 {expect}）{('：' + msg) if msg else ''}",
            "检查钩子脚本与 AGENT_ROLE 注入" if rc != expect else "")


def drill_platform() -> None:
    pending = [
        ("1", "失败测试的 PR 被 CI 阻断", "需要 git 仓库 + GitHub Actions（本机无 .github/workflows、无 remote）"),
        ("2", "假密钥被 gitleaks 阻断", "gitleaks 未安装，且无 CI 运行 secrets 检查"),
        ("6", "开发账号写 agent-review 无权限", "需要为 17 个岗位建 GitHub App / 机器账号"),
        ("7", "答案泄露攻击集失败 → eval-gate 阻断", "需要 eval-gate.yml + evals/baseline/golden.json"),
        ("8", "生产部署停在待审批", "需要 production environment + 审批人"),
        ("9", "机器人账号无法批准生产", "同上，需把机器账号排除在审批人外"),
        ("3d", "绕过本地钩子后 CODEOWNERS 仍要人批", "需要远端分支保护生效"),
        ("5e", "直接 push / force push 被平台拒绝", "需要远端分支保护（本地钩子只能管本地）"),
        ("4d", "降覆盖率阈值被受保护路径拦", "需要阈值配置文件 + CODEOWNERS 加路径"),
        ("10", "worker 运行时看不到 create_agent", "配置已 PASS（A4/A5）；运行时验证需起一个 worker Agent，查其工具目录"),
    ]
    for no, name, why in pending:
        add(no, name, "PENDING", why, "按 docs/04 §2 完成平台配置后重跑本演练")


def main() -> int:
    cfg = load_cfg()
    drill_setup(cfg)
    drill_hooks()
    drill_platform()

    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0 if not any(r["status"] == "FAIL" for r in results) else 1

    icon = {"PASS": "✓", "FAIL": "✗", "PENDING": "·"}
    print("=" * 78)
    print("磐石软件 · 门禁演练（docs/04 §3 本地可验证部分）")
    print("=" * 78)
    for r in results:
        print(f"{icon[r['status']]} {r['no']:<4} {r['status']:<8} {r['name']}")
        if r["status"] != "PASS":
            print(f"        └ {r['evidence']}")
            if r["fix"]:
                print(f"        └ 修复：{r['fix']}")
    p = sum(1 for r in results if r["status"] == "PASS")
    f = sum(1 for r in results if r["status"] == "FAIL")
    d = sum(1 for r in results if r["status"] == "PENDING")
    print("-" * 78)
    print(f"PASS {p}　FAIL {f}　PENDING(需 GitHub 平台) {d}")
    return 1 if f else 0


if __name__ == "__main__":
    raise SystemExit(main())
