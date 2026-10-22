#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 .github/workflows/*.yml 语法。

工作流文件非法时 GitHub 会"0 秒失败且无任何日志"，极难排查（本项目踩过：
echo 字符串里的 ': ' 破坏了 YAML plain scalar）。所以放进 CI 前置检查。

用法：python scripts/check_workflows.py
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        import yaml
    except ImportError:
        print("[skip] 未安装 pyyaml（CI 里需 pip install pyyaml）")
        return 0

    files = sorted(glob.glob(str(ROOT / ".github" / "workflows" / "*.yml")))
    if not files:
        print("[skip] 没有工作流文件")
        return 0

    bad = 0
    for f in files:
        try:
            yaml.safe_load(Path(f).read_text(encoding="utf-8"))
            print(f"ok   {Path(f).name}")
        except Exception as e:  # noqa: BLE001
            bad += 1
            print(f"BAD  {Path(f).name}: {e}")
    if bad:
        print(f"\n{bad} 个工作流文件语法非法：GitHub 会 0 秒失败且不留日志。")
        return 1
    print(f"\n✓ {len(files)} 个工作流文件语法正常")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
