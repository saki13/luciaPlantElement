# -*- coding: utf-8 -*-
"""M4 无尽 / 爬塔：轮次缩放 + 自动反制僵尸生成器（纯逻辑，可 headless 验证）。

两条核心规则（v0.2 §15 与 counter_map.principles）：
1. 同威胁点预算内，把点数投到玩家当前最薄弱的轴，打贬值而非无脑堆血量；
2. 每个生成组合必须存在当前卡池可打出 >50% 胜率的解法，否则作废重 roll。

第 50 轮固定刷 T10 门槛 Boss（boss_50）；前期怪最多带 1 个机制，50 轮才允许多机制复合。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from ..engine.wavegen import build_schedule

# 轮次 -> 解锁敌人（含 M2/M3 机制怪），节奏比主线更陡
ROUND_UNLOCKS = [
    (0, ["normal", "fast", "banner"]),
    (2, ["cone"]),
    (4, ["shield_cadet", "bucket"]),
    (8, ["giant"]),
]
BOSS_EVERY = 50
SOLVABILITY_MIN = 0.50


def allowed_for_round(round_idx: int) -> List[str]:
    allowed: List[str] = []
    for threshold, keys in ROUND_UNLOCKS:
        if round_idx >= threshold:
            allowed.extend(keys)
    return allowed


def round_budget_growth(round_idx: int) -> int:
    """无尽单轮威胁预算：比主线 8+4w 更陡，体现后期压力。"""
    return 8 + 6 * round_idx


def profile_cards(card_keys: Sequence[str], plant_defs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """汇总玩家卡池画像：各轴最高档、标签集合、最高品阶、近战/远程构成。"""
    axes_max = {a: 0 for a in ("fire", "area", "pierce", "durability", "control")}
    tags: set = set()
    max_tier = 1
    melee = ranged = 0
    for k in card_keys:
        d = plant_defs.get(k)
        if not d:
            continue
        for a, lv in d.get("axes", {}).items():
            axes_max[a] = max(axes_max[a], int(lv))
        tags.update(d.get("tags", []))
        max_tier = max(max_tier, int(d.get("tier", 1)))
        if d.get("role") == "melee":
            melee += 1
        elif d.get("role") == "ranged":
            ranged += 1
    return {"axes_max": axes_max, "tags": tags, "max_tier": max_tier,
            "melee": melee, "ranged": ranged}


# selector_rules 语义 -> 具体敌人 key（counter_map 规则的可执行映射，草案）
def pick_counter_enemies(profile: Dict[str, Any]) -> List[str]:
    ax, tags = profile["axes_max"], profile["tags"]
    picks: List[str] = []
    # 规则6：玩家已有破盾 -> 只混少量盾兵，主体仍是无盾怪，避免盾被单方面完克
    if "shield_break" in tags:
        picks += ["shield_cadet", "normal", "fast"]
    # 规则1：穿透特化但单发火力弱 -> 高本体无甲厚血
    if ax["pierce"] >= 3 and ax["fire"] <= 2:
        picks.append("giant")
    # 规则2：单体狙击 -> 低成本快速人海
    if ax["area"] <= 2 and ax["pierce"] <= 1:
        picks += ["fast", "normal"]
    # 规则3：AoE 强但单体弱 -> 少量高甲精英分散 + 快速单位
    if ax["area"] >= 3 and ax["fire"] <= 3:
        picks += ["bucket", "giant", "fast"]
    # 规则4：控制特化 -> 高重量免控/减速抵抗
    if ax["control"] >= 3:
        picks += ["giant", "bucket"]
    # 规则5：近战短手 -> 快速高啃咬
    if profile["melee"] > 0 and profile["ranged"] == 0:
        picks.append("fast")
    # 去重保序
    seen, ordered = set(), []
    for k in picks:
        if k not in seen:
            seen.add(k)
            ordered.append(k)
    return ordered or ["normal", "fast"]


def build_round_schedule(enemy_defs: Dict[str, Dict[str, Any]], round_idx: int, seed: int,
                         card_keys: Sequence[str], plant_defs: Dict[str, Dict[str, Any]]) -> List:
    """生成某一轮的出怪表；每 50 轮插入 T10 Boss。"""
    if round_idx > 0 and round_idx % BOSS_EVERY == 0:
        # 门槛轮：Boss 前置少量护卫，固定时间点
        from ..engine.wavegen import fixed_schedule
        return fixed_schedule([(8.0, "normal"), (14.0, "cone"), (20.0, "bucket"),
                               (28.0, "boss_50"), (46.0, "cone"), (60.0, "bucket")])
    allowed = allowed_for_round(round_idx)
    profile = profile_cards(card_keys, plant_defs)
    extra = [k for k in pick_counter_enemies(profile) if k in allowed]
    cap = min(12, 4 + round_idx // 2)
    return build_schedule(enemy_defs, waves=1 + round_idx // 4, seed=seed,
                          extra_pool=extra, allowed=allowed,
                          wave_cap_fn=lambda w, _cap=cap: _cap)


# solver 回调签名：(schedule, card_keys, seed) -> 胜率 float；None 表示暂不做可解性回归
Solver = Callable[[List, Sequence[str], int], float]


def ensure_solvable(enemy_defs, round_idx: int, seed: int, card_keys: Sequence[str],
                    plant_defs: Dict[str, Dict[str, Any]], solver: Optional[Solver] = None,
                    max_rolls: int = 3):
    """可解性闸门：胜率不足 0.5 则换 seed 重 roll；未注入 solver 时直接返回（M4 接入 headless）。"""
    sched = build_round_schedule(enemy_defs, round_idx, seed, card_keys, plant_defs)
    if solver is None:
        return sched, {"checked": False, "win_rate": None}
    for attempt in range(max_rolls):
        win_rate = solver(sched, card_keys, seed + attempt * 7919)
        if win_rate >= SOLVABILITY_MIN:
            return sched, {"checked": True, "win_rate": round(win_rate, 3), "rolls": attempt}
        sched = build_round_schedule(enemy_defs, round_idx, seed + (attempt + 1) * 7919,
                                     card_keys, plant_defs)
    return sched, {"checked": True, "win_rate": round(win_rate, 3), "rolls": max_rolls,
                   "warning": "solvability below threshold after rerolls"}
