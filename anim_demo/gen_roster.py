# -*- coding: utf-8 -*-
"""
全花名册美术批量驱动：统一编排 13 植物 + 8 敌人的立绘/动作帧/拼表。

特性：
- 断点续跑：底层 gen_plant/gen_enemy 对已存在的 base/帧自动 skip，重复运行只补缺口；
- 失败不中断：单个单位/单帧的 SystemExit 被捕获并记录，最后统一汇总，可删坏帧后重跑；
- 状态落盘：assets/art_build_status.json 记录每个单位各阶段完成情况，方便核对 21 个单位进度。

用法（在项目根或 anim_demo 下均可，脚本按自身路径定位）：
  python gen_roster.py --phase base                 # 先出全部立绘
  python gen_roster.py --phase frames               # 立绘确认后批量出动作帧
  python gen_roster.py --phase sheet                # 去背拼 4x4 精灵表
  python gen_roster.py --phase all                  # base+frames+sheet 一条龙（后台长任务）
  python gen_roster.py --phase base --kind plant    # 只跑植物
"""
import os
import sys
import json
import argparse
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gen_plant as GP
import gen_enemy as GE
from build_spritesheet import build_dir

STATUS_PATH = os.path.join(HERE, "assets", "art_build_status.json")
SPRITE_ROOT = os.path.join(HERE, "assets", "sprites")


def roster(kind):
    items = []  # (kind, key, module, frames_maker)
    if kind in ("plant", "all"):
        for k in GP.PLANTS:
            items.append(("plant", k, GP))
    if kind in ("enemy", "all"):
        for k in GE.ENEMIES:
            items.append(("enemy", k, GE))
    return items


def asset_paths(kind, key, mod):
    root, base, frames_dir = mod.paths(key)
    dst_dir = SPRITE_ROOT if kind == "plant" else os.path.join(SPRITE_ROOT, "enemies")
    sheet = os.path.join(dst_dir, key + ".png")
    return root, base, frames_dir, sheet


def load_status():
    if os.path.exists(STATUS_PATH):
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_status(st):
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def run_phase(phase, kind, only_keys=None):
    st = load_status()
    failures = {}
    for unit_kind, key, mod in roster(kind):
        if only_keys and key not in only_keys:
            continue
        root, base, frames_dir, sheet = asset_paths(unit_kind, key, mod)
        rec = st.setdefault(f"{unit_kind}:{key}", {})
        rec["cn"] = mod.PLANTS[key]["cn"] if unit_kind == "plant" else mod.ENEMIES[key]["cn"]
        try:
            if phase in ("base", "all"):
                mod.make_base(key)
                rec["base"] = os.path.exists(base)
            if phase in ("frames", "all"):
                mod.make_frames(key)
                rec["frames"] = os.path.isdir(frames_dir) and all(
                    os.path.exists(os.path.join(frames_dir, n + ".png")) for n in mod.REQUIRED_PNG
                )
            if phase in ("sheet", "all"):
                if os.path.isdir(frames_dir):
                    os.makedirs(os.path.dirname(sheet), exist_ok=True)
                    build_dir(frames_dir, sheet)
                    rec["sheet"] = os.path.exists(sheet)
                else:
                    failures[key] = "frames dir missing, run frames first"
        except SystemExit as e:
            failures[key] = str(e)
            print(f"!! [fail] {unit_kind}:{key}: {e}")
        except Exception as e:  # 网络/解析等任何意外都不应中断整批
            failures[key] = repr(e)
            traceback.print_exc()
        save_status(st)
    print("\n===== PHASE", phase, "DONE =====")
    print("units:", len(roster(kind)), "failures:", failures if failures else "none")
    save_status(st)
    return failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True, choices=["base", "frames", "sheet", "all"])
    ap.add_argument("--kind", default="all", choices=["plant", "enemy", "all"])
    ap.add_argument("--keys", default="", help="逗号分隔，只跑指定 key（调试用）")
    a = ap.parse_args()
    only = [s.strip() for s in a.keys.split(",") if s.strip()] or None
    fails = run_phase(a.phase, a.kind, only)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
