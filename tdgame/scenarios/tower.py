# -*- coding: utf-8 -*-
"""M4 爬塔：把无尽模式的轮次缩放包装成"一层一层往上爬"。

与无尽了区别：
- **层数是显式的**，每层用 `endless.build_round_schedule` 生成出怪表，
  难度随层号单调上升（波数、单波上限、解锁敌人都涨）；
- 每 N 层来一层 Boss（用固定的 boss50 出怪表，可重复挑战）；
- 爬到的最高层会写进存档（`savegame.snapshot` 的 `tower_floor`），下次接着爬。

纯逻辑、无渲染依赖，可 headless 批量跑。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import config as C
from ..engine.board import Simulation
from ..engine.bot import RuleBot
from ..engine.wavegen import fixed_schedule
from .endless import build_round_schedule

DEFAULT_FLOORS = 20
BOSS_EVERY = 10          # 第 10、20 层是 Boss 层
MAX_SECONDS = 320.0

# Boss 层用的敌人。
#
# 原本这里放的是 `boss_50`（与 M3 门槛同一只），但实测它在当前卡池下**打不死**：
# `block_flat=30` 把豌豆/双发的伤害完全归零，唯一有效的 custom_shieldbreaker 只有
# 28.6 dps，打 5500 原始伤害要 193 秒而战斗只有约 120 秒（BACKLOG D-11）。
# 塔里放一个 0% 通过率的墙没有意义，所以在 D-11 修好之前，Boss 层改用"巨人攻坚"，
# 修好后把下面这一行换回 "boss_50" 即可。
BOSS_KEY = "giant"


def is_boss_floor(floor: int) -> bool:
    """floor 从 1 开始；每 BOSS_EVERY 层一个 Boss。"""
    return floor > 0 and floor % BOSS_EVERY == 0


def floor_schedule(reg, floor: int, seed: int, card_keys: List[str]) -> List:
    """第 floor 层的出怪表。"""
    if floor < 1:
        raise ValueError(f"层号从 1 开始，收到 {floor}")
    if is_boss_floor(floor):
        # 层数越高，Boss 层的护卫越厚
        extra = min(3, floor // BOSS_EVERY)
        return fixed_schedule(
            [(8.0, "normal"), (14.0, "cone"), (20.0, "bucket"),
             (28.0, BOSS_KEY), (46.0, "cone"), (60.0, "bucket"),
             (74.0, "bucket"), (88.0, BOSS_KEY)][:6 + extra])
    # 用第 (floor-1) 轮的缩放：第 1 层等价第 0 轮，最平缓
    return build_round_schedule(reg.enemies, floor - 1, seed, card_keys, reg.plants)


class TowerRun:
    """一次爬塔进程：记录当前层与最高层。"""

    def __init__(self, reg, card_pool: List[str], seed: int = 1000,
                 floors: int = DEFAULT_FLOORS, start_floor: int = 1):
        self.reg = reg
        self.card_pool = list(card_pool)
        self.seed = seed
        self.floors = floors
        self.floor = max(1, int(start_floor))
        self.best_floor = self.floor
        self.history: List[Dict[str, Any]] = []

    def schedule(self) -> List:
        return floor_schedule(self.reg, self.floor, self.seed + self.floor, self.card_pool)

    def run_floor(self, max_seconds: float = MAX_SECONDS) -> Dict[str, Any]:
        """打当前层；赢了就上一层。返回本层结果。"""
        sched = self.schedule()
        sim = Simulation(self.reg.plants, self.reg.enemies, sched, self.card_pool,
                         seed=self.seed + self.floor, start_resource=C.START_RESOURCE,
                         max_seconds=max_seconds)
        metrics = sim.run_to_end(RuleBot(self.card_pool, smart=True))
        won = bool(metrics["won"])
        rec = {
            "floor": self.floor,
            "boss": is_boss_floor(self.floor),
            "won": won,
            "duration": round(metrics["duration"], 1),
            "mowers_used": metrics["mowers_used"],
            "waves": len(sched),
        }
        self.history.append(rec)
        if won:
            self.best_floor = max(self.best_floor, self.floor + 1)
            self.floor += 1
        else:
            rec["failed_at"] = self.floor
        return rec

    def climb(self, stop_at: int = 0, max_seconds: float = MAX_SECONDS) -> Dict[str, Any]:
        """连续往上爬，直到失败或爬到 stop_at（0 表示 floors 上限）。"""
        target = stop_at or self.floors
        while self.floor <= target:
            rec = self.run_floor(max_seconds=max_seconds)
            if not rec["won"]:
                break
        return self.status()

    def status(self) -> Dict[str, Any]:
        return {
            "floor": self.floor,
            "best_floor": self.best_floor,
            "floors": self.floors,
            "cleared": len([h for h in self.history if h["won"]]),
            "attempts": len(self.history),
            "reached_top": self.floor > self.floors,
        }


def run_tower(reg, card_pool: List[str], seed: int = 1000,
              floors: int = DEFAULT_FLOORS, start_floor: int = 1) -> Dict[str, Any]:
    """headless 爬一次塔，返回统计（用于回归与难度评估）。"""
    run = TowerRun(reg, card_pool, seed=seed, floors=floors, start_floor=start_floor)
    st = run.climb()
    st["history"] = run.history
    st["died_at"] = None if st["reached_top"] else run.floor
    return st
