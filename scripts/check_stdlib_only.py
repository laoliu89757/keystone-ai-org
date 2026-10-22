#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""learning-service/ 只许用 Python 标准库（INTENT-001 硬约束）。

违反即退出码 1。CI 与本地都能跑：
    python scripts/check_stdlib_only.py
"""

from __future__ import annotations

import ast
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "learning-service"

# 允许的例外（开发期工具/本包自身）
ALLOW = {"pytest", "learning_service"}
STDLIB = set(sys.stdlib_module_names) | {"__future__"}


def module_root(name: str) -> str:
    return name.split(".")[0]


def scan(path: Path) -> list[tuple[Path, int, str]]:
    bad: list[tuple[Path, int, str]] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:
        bad.append((path, e.lineno or 0, f"语法错误: {e.msg}"))
        return bad
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = module_root(a.name)
                if root not in STDLIB and root not in ALLOW:
                    bad.append((path, node.lineno, f"import {a.name}"))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            root = module_root(node.module)
            if root not in STDLIB and root not in ALLOW:
                bad.append((path, node.lineno, f"from {node.module} import …"))
    return bad


def main() -> int:
    if not TARGET.exists():
        print(f"[skip] {TARGET} 不存在")
        return 0
    files = sorted(TARGET.rglob("*.py"))
    if not files:
        print("[skip] learning-service/ 下没有 .py")
        return 0

    bad: list[tuple[Path, int, str]] = []
    for f in files:
        if "__pycache__" in f.parts:
            continue
        bad.extend(scan(f))

    print(f"扫描 {len(files)} 个文件（stdlib-only 门禁）")
    if bad:
        for p, ln, msg in bad:
            print(f"✗ {p.relative_to(ROOT)}:{ln}  {msg}")
        print("\nlearning-service/ 只允许标准库。需要第三方库请升级给人决策（AGENTS.md §6 / owner-brief §3）。")
        return 1
    print("✓ 仅使用标准库")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
