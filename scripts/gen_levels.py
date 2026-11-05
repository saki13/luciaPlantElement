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

    # ---- M3 进阶主线 8 关 + 阶段 Boss ----
    # 规划原为"约 10 关"，落地 8 关推进 + 1 关 Boss。卡池分两段：
    # 前 4 关只给到西瓜/寒仙子，后 4 关放开双发进阶与荆棘穿甲株。
    M3_POOL_EARLY = ["sunbloom", "peashooter", "repeater", "morningglory", "wallnut",
                     "custom_shieldbreaker", "frostbell", "bombberry", "melonpult"]
    # 进阶段逐关加码：波数、单波上限、允许的敌人集合都在涨
    m3_plan = [
        # (waves, allowed, cap_base, cap_max, start, use_full_pool)
        (8,  ["normal", "fast", "banner", "cone", "shield_cadet", "bucket"], 2, 6, 150, False),
        (9,  ["normal", "fast", "banner", "cone", "shield_cadet", "bucket"], 2, 7, 150, False),
        (10, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket"], 2, 7, 175, False),
        (11, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 3, 8, 175, False),
        (12, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 3, 8, 200, True),
        (13, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 3, 9, 200, True),
        (14, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 3, 9, 225, True),
        (15, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 4, 10, 225, True),
        # ---- 扩关到 15（承接 M2 不再发放的六株奖励，见 design §19.1）----
        (16, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 4, 11, 250, True),
        (17, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 4, 11, 250, True),
        (18, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 5, 12, 275, True),
        (19, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 5, 12, 275, True),
        (20, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 5, 13, 300, True),
        (21, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 6, 13, 300, True),
        (22, ["normal", "fast", "banner", "cone", "shield_cadet", "bucket", "giant"], 6, 14, 325, True),
    ]
    for i, (waves, allowed, cap_base, cap_max, start, full) in enumerate(m3_plan, start=1):
        levels.append(budget_level(
            f"m3_{i:02d}", "M3", f"进阶主线 第{i}关", waves, allowed,
            LATE_POOL if full else M3_POOL_EARLY,
            start=start, cap_base=cap_base, cap_max=cap_max))

    # 注：这里原本放的是 boss_50（T10 门槛 Boss），但按 game_balance_design.md
    # §10.1，M3 玩家的品阶上限只到 T6，撞 T10 门槛 Boss 必然 0% 胜率。
    # boss_50 已明确归给「无尽第 50 轮」。真正的 M3 阶段 Boss 待单独设计，
    # 在那之前用精英波（双巨人）占位。
    boss_entries = [[8, "normal"], [14, "cone"], [20, "bucket"], [28, "giant"],
                    [46, "cone"], [60, "bucket"], [76, "giant"]]
    levels.append(fixed_level("m3_boss", "M3", "阶段Boss·五十轮门槛", boss_entries,
                              [2, 1, 3, 2, 1, 3, 4], LATE_POOL, start=800, reward=300,
                              max_sec=320))


    # ---------------------------------------------------------------- 奖励表
    # 必须写在这里：关卡 JSON 由本脚本整体重写，手改 JSON 会被冲掉
    # （实际发生过：m3_boss 的 460 代币与 T8 权限被重新生成覆盖）。
    REWARDS = {
        # M1：成长阶梯，品阶单调，末关大奖
        "m1_01": {"plant": "sunbloom", "plant_reason": "经济位：一切开局的基础"},
        "m1_02": {"plant": "peashooter", "plant_reason": "最基础火力"},
        "m1_03": {"plant": "wallnut", "plant_reason": "肉盾位：先挡再打"},
        "m1_04": {"plant": "morningglory", "plant_reason": "第二路火力，教多线"},
        "m1_05": {"plant": "slow_vine", "plant_reason": "减速：教控场换输出窗口"},
        "m1_06": {"plant": "repeater", "plant_reason": "火力上台阶"},
        "m1_07": {"plant": "tri_pea", "plant_reason": "点射强化，应对中甲"},
        "m1_08": {"plant": "splash_pea", "plant_reason": "小范围溅射，应对成群"},
        "m1_09": {"plant": "charge_shot", "plant_reason": "蓄力：单发高伤"},
        "m1_10": {"plant": "melonpult", "plant_reason": "批次大奖：范围高伤，M2 敲门砖"},
        # M2：定位是教定制器与能力机制，只发代币，不发植物（design §19.1）
        # M3：15 关，承接 M2 移出的六株，品阶单调
        "m3_01": {"plant": "bamboo", "plant_reason": "近战半肉，补前排"},
        "m3_02": {"plant": "bombberry", "plant_reason": "一次性爆发，教时机"},
        "m3_03": {"plant": "leafdancer", "plant_reason": "穿透：应对列队尸群"},
        "m3_04": {"plant": "thorn_piercer", "plant_reason": "破甲：应对护甲抬升"},
        "m3_05": {"plant": "frostbell", "plant_reason": "控制：应对高速"},
        "m3_06": {"plant": "pine_needler", "plant_reason": "碎片溅射：应对人海"},
        "m3_07": {"plant": "saw_vine", "plant_reason": "穿透+击退"},
        "m3_08": {"plant": "pierce_crossbow", "plant_reason": "破甲强化"},
        "m3_09": {"plant": "ballista", "plant_reason": "连射穿透，火力台阶"},
        "m3_10": {"plant": "triple_gun", "plant_reason": "三重火力，进入中高品阶"},
        "m3_11": {"plant": "winter_melon", "plant_reason": "范围+控制（西瓜升级位）"},
        "m3_12": {"plant": "siege_mortar", "plant_reason": "高攻破甲，会被快速僵尸克制"},
        "m3_13": {"plant": "meteor_pult", "plant_reason": "远程范围压制"},
        "m3_14": {"plant": "iron_pumpkin",
                  "plant_reason": "肉盾（护甲壳）：可套在植物外层，机制已实现"},
        "m3_15": {"plant": "thorn_aura",
                  "plant_reason": "辅助（反弹光环）：周围方形区域反弹伤害，机制已实现"},
        # M3 Boss：不给植物，给够造 T8 的代币 + 创造 T8 的权限
        # 460 = 对 balance 净额公式穷举得到的最便宜 T8（area5/dur3/control5, power 162.0）
        "m3_boss": {"design_tokens": 460, "unlock_tier": 8,
                    "reward_reason": "M3 终关：给代币 + 创造 T8 的权限，植物由玩家自造"},
    }
    for lv in levels:
        extra = REWARDS.get(lv["key"])
        if extra:
            lv.setdefault("reward", {}).update(extra)

    for lv in levels:
        (OUT / f"{lv['key']}.json").write_text(
            json.dumps(lv, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(levels)} levels to {OUT}")


if __name__ == "__main__":
    main()
