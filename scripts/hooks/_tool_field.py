#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""钩子用的 JSON 取值小工具（无 jq 的 Windows 环境兜底）。

用法：echo '<hook json>' | python scripts/hooks/_tool_field.py tool_input.command
     echo '<hook json>' | python scripts/hooks/_tool_field.py tool_input.file_path
读不到或解析失败时输出空字符串并以 0 退出（由调用方决定如何兜底）。
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    raw = ""
    try:
        raw = sys.stdin.read()
    except Exception:
        pass
    try:
        data = json.loads(raw or "{}")
    except Exception:
        print("")
        return 0
    cur = data
    for part in [p for p in path.split(".") if p]:
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = ""
            break
    print("" if cur is None else cur)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
