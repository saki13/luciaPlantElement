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
             "pine_needler", "melonpult", "winter_melon", "bamboo", "thorn_piercer"]


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

    # ---- M2 六个能力挑战考场：全部固定表，每个只教一种能力 ----
    # 设计原则与格挡考场一致：两行聚焦、密度可控、敌人编排本身就是"考点"，
    # 而不是让随机尸潮把机制淹掉。
    shield_entries = [[12, "normal"], [18, "normal"], [26, "fast"], [34, "shield_cadet"],
                      [42, "normal"], [50, "shield_cadet"], [58, "cone"], [66, "shield_cadet"],
                      [74, "normal"], [82, "shield_cadet"], [90, "fast"], [98, "normal"]]
    shield_rows = [1, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1, 2]
    levels.append(fixed_level("m2_shield", "M2", "格挡教学考场", shield_entries, shield_rows,
                              LATE_POOL, start=200, reward=200))

    # 护甲考场：路障(280EHP) 打头，铁桶(650EHP) 压阵，考察"高甲该用爆发/穿甲而不是平推"
    armor_entries = [[12, "normal"], [20, "cone"], [28, "cone"], [36, "bucket"],
                     [46, "normal"], [54, "cone"], [62, "bucket"], [72, "bucket"],
                     [82, "cone"], [92, "normal"]]
    armor_rows = [1, 1, 2, 1, 2, 1, 2, 2, 1, 2]
    levels.append(fixed_level("m2_armor", "M2", "护甲教学考场", armor_entries, armor_rows,
                              LATE_POOL, start=200, reward=120, max_sec=200))

    # 高速考场：开局长间隔就压快速僵尸，考察"早铺防线 / 用减速换时间"
    speed_entries = [[10, "fast"], [16, "fast"], [22, "normal"], [28, "fast"],
                     [36, "fast"], [44, "normal"], [50, "fast"], [58, "fast"],
                     [66, "normal"], [74, "fast"], [82, "fast"]]
    speed_rows = [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1]
    levels.append(fixed_level("m2_speed", "M2", "高速教学考场", speed_entries, speed_rows,
                              LATE_POOL, start=200, reward=100, max_sec=180))

    # 人海考场：同一时刻多只同波进场，考察"范围伤害"（西瓜/松针）而非单点
    swarm_waves = [(14, 4), (30, 4), (46, 5), (62, 5), (78, 6)]
    swarm_entries, swarm_rows = [], []
    for t, n in swarm_waves:
        for i in range(n):
            swarm_entries.append([t, "normal"])
            swarm_rows.append(1 if i % 2 == 0 else 2)
    levels.append(fixed_level("m2_swarm", "M2", "人海教学考场", swarm_entries, swarm_rows,
                              LATE_POOL, start=200, reward=120, max_sec=180))

    # 控制考场：快慢混编、普通与路障交替，考察"减速/击退能不能换来输出窗口"
    control_entries = [[12, "normal"], [20, "fast"], [28, "cone"], [36, "fast"],
                       [44, "normal"], [52, "fast"], [60, "cone"], [68, "fast"],
                       [76, "normal"], [84, "fast"]]
    control_rows = [1, 2, 1, 2, 1, 2, 1, 2, 1, 2]
    levels.append(fixed_level("m2_control", "M2", "控制教学考场", control_entries, control_rows,
                              LATE_POOL, start=200, reward=100, max_sec=180))

    # 重量免控考场：巨人(weight 99 / 免控 / 1600HP) 为主，考察"硬控无效，只能堆伤与墙"
    weight_entries = [[14, "cone"], [26, "giant"], [40, "bucket"], [56, "giant"],
                      [72, "cone"], [88, "giant"], [104, "bucket"]]
    weight_rows = [1, 1, 2, 2, 1, 2, 1]
    levels.append(fixed_level("m2_weight", "M2", "重量免控考场", weight_entries, weight_rows,
                              LATE_POOL, start=250, reward=140, max_sec=260))

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
