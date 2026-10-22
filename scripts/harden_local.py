#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受保护文件的完整性校验与只读锁定（防误改 + 留痕，不是安全边界）。

背景：本项目所有规则都住在本地，而约束文件与被约束的 Agent 在同一个 OS 用户下，
因此本地层只能做到"改动可见"，真正的边界在 GitHub（分支保护 / 环境审批）。
详见 docs/06-Agent隔离与凭据.md。

用法：
    python scripts/harden_local.py --baseline   # 记录当前哈希 → .integrity.json
    python scripts/harden_local.py --verify     # 校验（CI 与 gate_drill 都会跑）
    python scripts/harden_local.py --lock       # 设只读属性，减少工具误写
    python scripts/harden_local.py --unlock     # 解除只读
    python scripts/harden_local.py --status     # 看一眼清单与当前状态
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / ".integrity.json"

# 受保护清单（相对仓库根）
PATTERNS = [
    "AGENTS.md",
    "CLAUDE.md",
    "CODEOWNERS",
    "pytest.ini",
    ".claude/settings.json",
    ".paseo/config.patch.json",
    "docs/roles/*.md",
    "scripts/hooks/*",
    ".github/workflows/*.yml",
]


def targets() -> list[Path]:
    found: list[Path] = []
    for pat in PATTERNS:
        if "*" in pat:
            found += [Path(p) for p in sorted(glob.glob(str(ROOT / pat)))]
        else:
            p = ROOT / pat
            if p.exists():
                found.append(p)
    return [p for p in found if p.is_file() and "__pycache__" not in p.parts]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def load_baseline() -> dict[str, str]:
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def cmd_baseline() -> int:
    data = {rel(p): sha(p) for p in targets()}
    BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(f"已记录 {len(data)} 个受保护文件的哈希 → {BASELINE.name}")
    for k in data:
        print("  ·", k)
    return 0


def cmd_verify() -> int:
    base = load_baseline()
    if not base:
        print("[skip] 没有 .integrity.json，先跑 --baseline")
        return 0
    current = {rel(p): sha(p) for p in targets()}
    changed = [k for k in base if k in current and base[k] != current[k]]
    missing = [k for k in base if k not in current]
    added = [k for k in current if k not in base]

    if changed or missing or added:
        print("受保护文件与基线不一致：")
        for k in changed:
            print(f"  ~ 已修改 {k}")
        for k in missing:
            print(f"  - 已删除 {k}")
        for k in added:
            print(f"  + 新增   {k}")
        print("\n如果这些改动是有意的：跑 --baseline 更新基线，并在 PR 里说明理由。")
        print("（本地层只负责让改动可见，真正的边界在 GitHub 分支保护。）")
        return 1
    print(f"✓ {len(current)} 个受保护文件与基线一致")
    return 0


def set_readonly(on: bool) -> int:
    n = 0
    for p in targets():
        mode = p.stat().st_mode
        if on:
            p.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
        else:
            p.chmod(mode | stat.S_IWUSR)
        n += 1
    print(f"{'已设为只读' if on else '已解除只读'}：{n} 个文件")
    print("注意：这只是文件属性，能改文件的进程可以改回来 —— 用于防误写，不防蓄意。")
    return 0


def cmd_status() -> int:
    files = targets()
    print(f"受保护文件 {len(files)} 个：")
    for p in files:
        ro = "只读" if not (p.stat().st_mode & stat.S_IWUSR) else "可写"
        print(f"  [{ro}] {rel(p)}")
    base = load_baseline()
    print(f"\n基线：{len(base)} 条" if base else "\n基线：无（跑 --baseline 建立）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--baseline", action="store_true")
    g.add_argument("--verify", action="store_true")
    g.add_argument("--lock", action="store_true")
    g.add_argument("--unlock", action="store_true")
    g.add_argument("--status", action="store_true")
    args = ap.parse_args()

    if args.baseline:
        return cmd_baseline()
    if args.verify:
        return cmd_verify()
    if args.lock:
        return set_readonly(True)
    if args.unlock:
        return set_readonly(False)
    return cmd_status()


if __name__ == "__main__":
    raise SystemExit(main())
