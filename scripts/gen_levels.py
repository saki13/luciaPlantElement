# -*- coding: utf-8 -*-
"""一次性生成 data/levels 下 M1/M2/M3 关卡 JSON（确定性模板，可手工微调）。

运行：python scripts/gen_levels.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tdgame" / "data" / "levels"

BASE_POOL = ["sunbloom", "peashooter", "wallnut", "morningglory", "repeater"]
LATE_POOL = ["sunbloom", "peashooter", "repeater", "morningglory", "wallnut",
             "custom_shieldbreaker", "frostbell", "bombberry", "leafdancer",
             "pine_needler", "melonpult", "winter_melon", "bamboo"]


def budget_level(key, phase, cn, waves, allowed, card_pool, *, start=100,
                 cap_base=2, cap_grow=1, cap_max=6, reward=0):
    return {
        "key": key, "phase": phase, "name": key, "cn": cn,
        "start_resource": start, "max_seconds": 400,
        "card_pool": card_pool,
        "spawn": {"mode": "budget", "waves": waves, "allowed": allowed,
                  "first_spawn_at": 12, "cap_base": cap_base,
                  "cap_grow": cap_grow, "cap_max": cap_max},
        "reward": {"design_tokens": reward, "unlock": []},
    }


def fixed_level(key, phase, cn, entries, rows, card_pool, *, start=200, reward=0, max_sec=200):
    return {
        "key": key, "phase": phase, "name": key, "cn": cn,
        "start_resource": start, "max_seconds": max_sec,
        "card_pool": card_pool,
        "spawn": {"mode": "fixed", "entries": entries, "rows": rows},
        "reward": {"design_tokens": reward, "unlock": []},
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    levels = []

    # ---- M1 新手白天 10 关：逐关加波、逐关解锁卡，末段才引入轻甲路障 ----
    early_allowed = ["normal", "fast", "banner"]
    late_allowed = early_allowed + ["cone"]
    for i in range(1, 11):
        pool = ["sunbloom", "peashooter"]
        if i >= 3:
            pool.append("wallnut")
        if i >= 5:
            pool.append("morningglory")
        if i >= 8:
            pool.append("repeater")
        allowed = early_allowed if i <= 6 else late_allowed
        levels.append(budget_level(
            f"m1_{i:02d}", "M1", f"新手白天 第{i}关", waves=i,
            allowed=allowed, card_pool=pool))

    # ---- M2 六个能力挑战考场（首个格挡为固定聚焦表，其余为可跑预算骨架）----
    shield_entries = [[12, "normal"], [18, "normal"], [26, "fast"], [34, "shield_cadet"],
                      [42, "normal"], [50, "shield_cadet"], [58, "cone"], [66, "shield_cadet"],
                      [74, "normal"], [82, "shield_cadet"], [90, "fast"], [98, "normal"]]
    shield_rows = [1, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1, 2]
    levels.append(fixed_level("m2_shield", "M2", "格挡教学考场", shield_entries, shield_rows,
                              LATE_POOL, start=200, reward=200))
    levels.append(budget_level("m2_armor", "M2", "护甲教学考场", 5,
                               ["normal", "fast", "banner", "cone", "bucket"], LATE_POOL,
                               start=200, reward=120))
    levels.append(budget_level("m2_speed", "M2", "高速教学考场", 4,
                               ["normal", "fast", "banner"], LATE_POOL,
                               start=200, cap_max=8, reward=100))
    levels.append(budget_level("m2_swarm", "M2", "人海教学考场", 4,
                               ["normal", "fast", "banner"], LATE_POOL,
                               start=200, cap_base=4, cap_grow=2, cap_max=12, reward=120))
    levels.append(budget_level("m2_control", "M2", "控制教学考场", 5,
                               ["normal", "fast", "banner", "cone"], LATE_POOL,
                               start=200, reward=100))
    levels.append(budget_level("m2_weight", "M2", "重量免控考场", 6,
                               ["normal", "cone", "bucket", "giant"], LATE_POOL,
                               start=250, reward=140))

    # ---- M3 进阶 10 关骨架（先落首关占位）+ 阶段 Boss 固定表 ----
    levels.append(budget_level("m3_01", "M3", "进阶主线 第1关", 8,
                               ["normal", "fast", "banner", "cone", "shield_cadet", "bucket"],
                               LATE_POOL, start=150))
    boss_entries = [[8, "normal"], [14, "cone"], [20, "bucket"], [28, "boss_50"],
                    [46, "cone"], [60, "bucket"]]
    levels.append(fixed_level("m3_boss", "M3", "阶段Boss·五十轮门槛", boss_entries,
                              [2, 1, 3, 2, 1, 3], LATE_POOL, start=800, reward=300,
                              max_sec=320))

    for lv in levels:
        (OUT / f"{lv['key']}.json").write_text(
            json.dumps(lv, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(levels)} levels to {OUT}")


if __name__ == "__main__":
    main()
