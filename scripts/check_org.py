#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编制一致性审计（幕僚长的每月例行，也可进 CI）。

检查「五处一致」：
  1. docs/01-组织架构.md 的岗位表   —— 事实源
  2. docs/roles/<序号>-<代号>.md     —— 角色卡存在，且第 1 节写了正确代号
  3. .paseo/config.patch.json        —— profile 名与 provider/模型
  4. scripts/hooks/guard_paths.sh    —— 每个代号都有白名单分支
  5. AGENTS.md 第 2 节岗位表          —— 代号与角色卡路径

用法：python scripts/check_org.py        （退出码非 0 = 有差异）
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
ORG = ROOT / "docs" / "01-组织架构.md"
AGENTS = ROOT / "AGENTS.md"
PATCH = ROOT / ".paseo" / "config.patch.json"
GUARD = ROOT / "scripts" / "hooks" / "guard_paths.sh"
ROLES = ROOT / "docs" / "roles"

problems: list[str] = []
notes: list[str] = []


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def org_roles() -> dict[str, dict[str, str]]:
    """从组织表解析：代号 -> {岗位, 模型, 目录, 角色卡序号}"""
    rows: dict[str, dict[str, str]] = {}
    for line in read(ORG).splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7:
            continue
        m = re.search(r"`([a-z]+)`", cells[1])
        if not m:
            continue
        code = m.group(1)
        name = re.sub(r"（.*?）", "", cells[1]).replace("**", "").strip()
        rows[code] = {
            "name": name,
            "model": cells[4].strip("` "),
            "dirs": cells[6],
            "num": cells[0].replace("*", "").strip(),
        }
    return rows


def profile_map() -> dict[str, dict]:
    patch = json.loads(read(PATCH) or "{}")
    out = {}
    for p in patch.get("daemon", {}).get("agentProfiles", []):
        out[p.get("name", "")] = p
    # 建立 “代号 -> profile” 的映射：profile 名里带（code）
    by_code = {}
    for name, p in out.items():
        m = re.search(r"（([a-z]+)）", name)
        if m:
            by_code[m.group(1)] = p
    return by_code


def main() -> int:
    roles = org_roles()
    if not roles:
        problems.append("无法从 docs/01-组织架构.md 解析岗位表")
    profiles = profile_map()
    guard = read(GUARD)
    agent_md = read(AGENTS)

    for code, info in roles.items():
        num = info["num"].zfill(2)
        card = ROLES / f"{num}-{code}.md"
        if not card.exists():
            problems.append(f"[角色卡缺失] {card.relative_to(ROOT)}（代号 {code}）")
        else:
            head = "\n".join(card.read_text(encoding="utf-8").splitlines()[:14])
            if code not in head:
                problems.append(f"[代号不符] {card.name} 第 1 节未出现代号 `{code}`")
            for sec in ("## 13", "## 11", "## 8"):
                if sec not in card.read_text(encoding="utf-8"):
                    problems.append(f"[角色卡缺节] {card.name} 缺少 {sec} 开头的节")

        prof = profiles.get(code)
        if not prof:
            problems.append(f"[缺 profile] 代号 {code} 在 .paseo/config.patch.json 里没有对应 profile")
        else:
            provider = str(prof.get("provider", ""))
            for suffix in ("-lead", "-worker"):
                if provider.endswith(suffix):
                    provider = provider[: -len(suffix)]
            model = f"{provider}/{prof.get('model')}"
            if info["model"] and info["model"] != model:
                problems.append(
                    f"[模型不一致] {code}: 组织表={info['model']} / profile={model}"
                )
            if not prof.get("notes"):
                problems.append(f"[notes 为空] {code} 的 profile 没有'适用场景'")

        if not re.search(rf"(^|[|\s(]){re.escape(code)}([|)\s])", guard, re.M):
            problems.append(f"[钩子缺分支] guard_paths.sh 没有处理 AGENT_ROLE={code}")

        if f"`{code}`" not in agent_md:
            problems.append(f"[章程缺行] AGENTS.md 第 2 节没有 `{code}`")

    # 反向：profile 有但组织表没有
    for code in profiles:
        if code not in roles:
            notes.append(f"[多余 profile] {code} 有 profile 但不在组织表")

    # 角色卡数量
    cards = sorted(p.name for p in ROLES.glob("[0-9][0-9]-*.md"))
    print(f"组织表岗位: {len(roles)}　角色卡: {len(cards)}　profile: {len(profiles)}")
    print("角色卡: " + ", ".join(cards))
    if notes:
        print("\n提示:")
        for n in notes:
            print("  · " + n)
    if problems:
        print("\n发现差异:")
        for p in problems:
            print("  ✗ " + p)
        return 1
    print("\n✓ 五处一致：组织表 / 角色卡 / profile / 钩子白名单 / AGENTS.md 岗位表")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
