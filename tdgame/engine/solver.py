# -*- coding: utf-8 -*-
"""headless 可解性求解器（M4）：给无限模式的可解性闸门提供真实胜率。

`endless.ensure_solvable` 早就留好了 solver 回调，但一直传 `None` 等于没闸门。
本模块用固定 seed 小样本跑 RuleBot，给出一个确定性的胜率估计，供闸门判断
「这一轮玩家当前卡池到底打不打得过」。

注意：这不是渲染层逻辑，纯标准库，可在 headless 批量跑。
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from ..engine.board import Simulation
from ..engine.bot import RuleBot


def headless_win_rate(plant_defs: Dict[str, Dict[str, Any]],
                      enemy_defs: Dict[str, Dict[str, Any]],
                      schedule: List,
                      card_keys: Sequence[str],
                      seed: int,
                      runs: int = 5,
                      start_resource: int = 100,
                      max_seconds: float = 400.0) -> float:
    """对同一张出怪表跑 runs 局（seed, seed+1, ...），返回胜率。"""
    if runs <= 0:
        return 0.0
    pool = list(card_keys)
    wins = 0
    for i in range(runs):
        sim = Simulation(plant_defs, enemy_defs, schedule, pool, seed=seed + i,
                         start_resource=start_resource, max_seconds=max_seconds)
        metrics = sim.run_to_end(RuleBot(pool, smart=True))
        if metrics["won"]:
            wins += 1
    return wins / runs


def make_solver(reg, runs: int = 5, start_resource: int = 100,
                max_seconds: float = 400.0):
    """把 Registry 绑进来，返回 `endless.ensure_solvable` 需要的 solver 回调。"""

    def _solve(schedule, card_keys, seed: int) -> float:
        return headless_win_rate(reg.plants, reg.enemies, schedule, card_keys, seed,
                                 runs=runs, start_resource=start_resource,
                                 max_seconds=max_seconds)

    return _solve
