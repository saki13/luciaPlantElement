# -*- coding: utf-8 -*-
"""`board.step` 逐步一致性 trace（E-02）。

现有的校准/关卡基线比对的是**聚合指标**（胜率、平均时长、破线数），一粒
"某一步算错但最后结果碰巧一样"的 bug 它们抓不到。这个模块把整局模拟的
**逐步状态**导出来，用于：

1. Python 侧回归：任何改动只要让某一步的状态变了，就会在 diff 里指到具体步数；
2. 跨语言校验：GDScript 移植侧 replay 同一份场景，逐步比对 digest。

为了让 trace 只依赖**引擎逻辑**、不夹带 Bot 策略，场景里用的是：
- 植物：`setup_plant` 预置（绕过阳光/冷却），
- 敌人：固定出怪表（固定行、固定时间），
- 天空阳光：关闭（去掉与战斗无关的随机源）。

于是两侧只要引擎一致，trace 就必须逐字段相同。
"""
from __future__ import annotations

from typing import Any, Dict, List

from .. import config as C
from .board import Simulation

TRACE_FORMAT = "pvz-board-trace/1"


# ---------------------------------------------------------------------- 场景定义
# 三项覆盖不同的核心路径：直射+啃墙、护甲+减速、格挡。
SCENARIOS: Dict[str, Dict[str, Any]] = {
    "core_shoot_bite": {
        "cn": "直射 vs 啃墙（最基础的一局）",
        "seed": 1000,
        "steps": 600,
        "plants": [[2, 1, "peashooter"], [2, 5, "wallnut"],
                   [3, 2, "repeater"]],
        "schedule": [[2.0, "normal", 2], [5.0, "normal", 2],
                     [9.0, "fast", 3], [14.0, "cone", 2]],
    },
    "armor_slow": {
        "cn": "护甲 + 减速（铁桶/寒冰）",
        "seed": 1001,
        "steps": 600,
        "plants": [[0, 1, "frostbell"], [0, 4, "peashooter"],
                   [1, 1, "melonpult"]],
        "schedule": [[2.0, "bucket", 0], [6.0, "bucket", 1],
                     [11.0, "cone", 0]],
    },
    "block_shield": {
        "cn": "格挡（盾兵 + 破盾株）",
        "seed": 1002,
        "steps": 500,
        "plants": [[4, 1, "custom_shieldbreaker"], [4, 4, "peashooter"]],
        "schedule": [[2.0, "shield_cadet", 4], [7.0, "shield_cadet", 4],
                     [13.0, "normal", 4]],
    },
    "move_bite": {
        "cn": "移动 + 啃食（GDScript 移植的第一块，无弹道无特殊机制）",
        "seed": 1003,
        "steps": 400,
        "plants": [[1, 1, "wallnut"], [3, 4, "wallnut"]],
        "schedule": [[2.0, "normal", 1], [4.0, "normal", 3],
                     [7.0, "cone", 1], [12.0, "normal", 3]],
    },
}


def _digest(sim: Simulation) -> Dict[str, Any]:
    """一步之后的状态摘要。数值统一 round 到固定小数位，避免浮点尾数噪音。"""
    return {
        "t": round(sim.now, 4),
        "sun": int(sim.sun),
        "lives": int(sim.lives),
        "plants": sorted([int(p.row), int(p.col), round(p.hp, 4)]
                         for p in sim.plants),
        "enemies": sorted([int(e.row), round(e.x, 4), round(e.hp_body, 4)]
                          for e in sim.enemies),
        "proj": sorted([int(p.row), round(p.x, 4)] for p in sim.projectiles),
        "kills": int(sum(sim.kills.values())),
        "mowers": int(sim.mowers_used),
        "breaches": int(sim.breaches),
        "over": bool(sim.over),
    }


def run_scenario(name: str) -> Dict[str, Any]:
    """跑一个场景，返回逐步 digest 列表。"""
    spec = SCENARIOS[name]
    pool = sorted({p[2] for p in spec["plants"]})
    sim = Simulation({}, {}, [], pool, seed=spec["seed"], start_resource=0,
                     max_seconds=1e9, sky_sun=False)
    # 用真实注册表（plant_defs/enemy_defs 需要完整定义）
    from .loader import load_registry
    from pathlib import Path

    reg = load_registry(Path(__file__).resolve().parents[1] / "data")
    sim.plant_defs = reg.plants
    sim.enemy_defs = reg.enemies
    sim.card_pool = pool

    for row, col, key in spec["plants"]:
        if not sim.setup_plant(key, int(row), int(col)):
            raise RuntimeError(f"{name}: 预置植物失败 {key}@({row},{col})")

    # 固定出怪表：直接登记到 schedule，交给引擎按时间刷
    sim.schedule = sorted([(float(t), k, int(r)) for t, k, r in spec["schedule"]],
                          key=lambda z: z[0])
    sim._spawn_idx = 0

    frames: List[Dict[str, Any]] = []
    for step in range(int(spec["steps"])):
        if sim.over:
            break
        sim.step(C.DT)
        frames.append(_digest(sim))

    # 把本场景用到的角色定义一并塞进 trace：GDScript 侧不需要能访问仓库外的
    # tdgame/data（res:// 走不出项目目录），trace 因此是自包含的。
    used_plants = {k: reg.plants[k] for _r, _c, k in spec["plants"] if k in reg.plants}
    used_enemies = {k: reg.enemies[k] for _t, k, _r in spec["schedule"] if k in reg.enemies}

    return {
        "format": TRACE_FORMAT,
        "defs": {"plants": used_plants, "enemies": used_enemies},
        "scenario": name,
        "cn": spec["cn"],
        "seed": spec["seed"],
        "plants": spec["plants"],
        "schedule": spec["schedule"],
        "steps": len(frames),
        "frames": frames,
    }


def run_all() -> Dict[str, Any]:
    return {"format": TRACE_FORMAT,
            "scenarios": {name: run_scenario(name) for name in SCENARIOS}}
