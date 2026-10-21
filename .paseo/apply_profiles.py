#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 .paseo/config.patch.json 合并进 Paseo 的 ~/.paseo/config.json。

用法:
    python .paseo/apply_profiles.py --dry-run     # 只看会改什么
    python .paseo/apply_profiles.py               # 真写（自动备份）
    python .paseo/apply_profiles.py --prune-legacy # 额外归档旧的非本编制 profile

规则:
  * agents.providers       按 key 深合并（不会删掉你已有的其它 Provider）
  * daemon.agentProfiles   按 name 幂等 upsert（同一个名字重复执行不会产生重复项）
  * 写入前把原文件备份成 config.json.bak-YYYYmmdd-HHMMSS
  * 写完提示执行 `paseo reload`，并强调必须新开/重载 Agent 才生效
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

try:  # Windows 控制台中文输出
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
PATCH = ROOT / ".paseo" / "config.patch.json"
CONFIG = Path(os.environ.get("PASEO_HOME", Path.home() / ".paseo")) / "config.json"

# 本编制之外的旧 profile 名（--prune-legacy 会删除；--dry-run 时只提示）
LEGACY_HINT = ("码农", "负责制作UI", "出题小能手", "CEO")


def deep_merge(base: dict, patch: dict) -> dict:
    """patch 覆盖 base；dict 递归合并，list 与标量整体替换。"""
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def upsert_profiles(cfg: dict, incoming: list[dict]) -> tuple[list[str], list[str]]:
    profiles = cfg.setdefault("daemon", {}).setdefault("agentProfiles", [])
    added, updated = [], []
    for prof in incoming:
        idx = next((i for i, p in enumerate(profiles) if p.get("name") == prof.get("name")), None)
        if idx is None:
            idx = next((i for i, p in enumerate(profiles) if p.get("id") == prof.get("id")), None)
        if idx is None:
            profiles.append(copy.deepcopy(prof))
            added.append(prof["name"])
        else:
            profiles[idx] = deep_merge(profiles[idx], prof)
            updated.append(prof["name"])
    return added, updated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune-legacy", action="store_true", help="删除旧的手工 profile（按 LEGACY_HINT 精确匹配名字）")
    ap.add_argument("--config", default=str(CONFIG))
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not PATCH.exists():
        print(f"[x] 找不到补丁文件: {PATCH}")
        return 1
    patch = json.loads(PATCH.read_text(encoding="utf-8"))

    if cfg_path.exists():
        raw = cfg_path.read_text(encoding="utf-8")
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[x] {cfg_path} 不是合法 JSON，先修好它: {e}")
            return 1
    else:
        print(f"[!] {cfg_path} 不存在，将新建（Paseo 首次运行也会生成）")
        cfg = {"version": 1, "daemon": {}, "agents": {"providers": {}}}

    before_providers = set(cfg.get("agents", {}).get("providers", {}).keys())
    merged = deep_merge(cfg, {"agents": patch.get("agents", {})})
    incoming_profiles = patch.get("daemon", {}).get("agentProfiles", [])
    added, updated = upsert_profiles(merged, incoming_profiles)
    new_providers = sorted(set(merged.get("agents", {}).get("providers", {}).keys()) - before_providers)

    # 旧 profile：精确名字匹配（新编制名形如 `CEO 首席执行官（ceo）`，不会误删）
    keep_names = {p.get("name") for p in incoming_profiles}
    legacy = [
        p for p in merged["daemon"]["agentProfiles"]
        if p.get("name") in LEGACY_HINT and p.get("name") not in keep_names
    ]

    print("=" * 62)
    print("磐石软件 Agent 编制 · 合并计划")
    print("=" * 62)
    print(f"配置路径     : {cfg_path}")
    print(f"新增 Provider: {', '.join(new_providers) if new_providers else '（无）'}")
    print(f"新增 Profile : {len(added)} 个")
    for n in added:
        print(f"   + {n}")
    if updated:
        print(f"更新 Profile : {len(updated)} 个")
        for n in updated:
            print(f"   ~ {n}")
    if legacy:
        print(f"\n旧 profile（{'将删除' if (args.prune_legacy and not args.dry_run) else '可删除，加 --prune-legacy'}）: {len(legacy)} 个")
        for p in legacy:
            print(f"   - {p.get('name')}  provider={p.get('provider')} model={p.get('model')}")
        if args.prune_legacy:
            merged["daemon"]["agentProfiles"] = [
                p for p in merged["daemon"]["agentProfiles"]
                if not (p.get("name") in LEGACY_HINT and p.get("name") not in keep_names)
            ]

    if args.dry_run:
        print("\n[dry-run] 未写入。")
        return 0

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    if cfg_path.exists():
        bak = cfg_path.with_suffix(f".json.bak-{dt.datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(cfg_path, bak)
        print(f"\n已备份 → {bak.name}")

    cfg_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 → {cfg_path}")
    print("\n下一步：")
    print("  1) paseo reload                 # 让 daemon 重新读配置")
    print("  2) 新开 Agent 或重载已有 Agent   # 运行中的会话保留启动时的工具目录")
    print("  3) 在 设置 → 主机 → Agents → Agent 配置 里核对岗位名与‘适用场景’")
    print("\n如果 create_agent 报 provider 不存在，把 profile 的 provider 从")
    print("claude-lead/claude-worker/pi-worker 改回 claude/pi 即可（工具裁剪会失效，")
    print("此时必须依赖本地钩子 + GitHub 平台两层门禁）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
