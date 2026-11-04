# -*- coding: utf-8 -*-
"""M5「我是僵尸」：攻防反转模式（纯逻辑，headless 可测）。

与主线的区别：
- 植物是**关卡预置**的，玩家不能种（`Simulation.objective = "devour"` 会直接拒绝 `can_place`）；
- 敌人由**玩家花预算按需投放**，没有出怪表；
- 胜负倒过来：把场上植物全部啃光 = 通关，超时 = 失败。

预算单位直接复用敌人 JSON 里的 `budget` 字段（普通/旗帜/快速 1、路障/盾兵 2、
铁桶 4、巨人 8），这样两边数值只维护一份。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import config as C
from ..engine.board import Simulation

MODE = "izombie"


def enemy_cost(reg, key: str) -> int:
    d = reg.enemies.get(key) or {}
    return int(d.get("budget", 1) or 1)


class ZombieSession:
    """我是僵尸的一局：预置植物 + 玩家投僵尸。"""

    def __init__(self, level: Dict[str, Any], reg, seed: int = 0):
        self.level = level
        self.reg = reg
        self.key = level.get("key", "zombie")
        self.max_seconds = float(level.get("max_sec", 120))
        self.sim = Simulation(reg.plants, reg.enemies, [], [], seed=seed,
                              start_resource=0, max_seconds=self.max_seconds,
                              sky_sun=False, objective="devour")
        for entry in level.get("plants", []):
            row, col, pkey = entry[0], entry[1], entry[2]
            self.sim.setup_plant(pkey, int(row), int(col))
        self.start_budget = int(level.get("budget", 0))
        self.budget = self.start_budget
        self.allowed: List[str] = list(level.get("allowed", []))
        self.spawned = 0
        self.placements: List[Tuple[float, str, int]] = []
        self._acc = 0.0

    # ------------------------------------------------------------------ 投放
    def cost(self, key: str) -> int:
        return enemy_cost(self.reg, key)

    def can_place(self, key: str, row: int) -> Tuple[bool, str]:
        if self.sim.over:
            return False, "over"
        if not (0 <= row < C.ROWS):
            return False, "out_of_board"
        if key not in self.reg.enemies:
            return False, "unknown"
        if self.allowed and key not in self.allowed:
            return False, "not_allowed"
        if self.cost(key) > self.budget:
            return False, "no_budget"
        return True, "ok"

    def place_zombie(self, key: str, row: int) -> bool:
        ok, _why = self.can_place(key, row)
        if not ok:
            return False
        self.budget -= self.cost(key)
        self.sim.spawn_enemy(key, row)
        self.spawned += 1
        self.placements.append((round(self.sim.now, 2), key, row))
        return True

    # ------------------------------------------------------------------ 推进
    def tick(self, dt_seconds: float) -> None:
        """按真实秒数推进，内部累计成固定的 C.DT 步长（与 PlaySession 一致）。"""
        if dt_seconds <= 0:
            return
        self._acc += float(dt_seconds)
        while self._acc >= C.DT and not self.sim.over:
            self._acc -= C.DT
            self.sim.step(C.DT)

    # ------------------------------------------------------------------ 查询
    def plants_left(self) -> int:
        return len(self.sim.plants)

    def zombies_alive(self) -> int:
        return len(self.sim.enemies)

    def status(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "mode": MODE,
            "budget": self.budget,
            "start_budget": self.start_budget,
            "plants_left": self.plants_left(),
            "start_plants": len(self.level.get("plants", [])),
            "zombies_alive": self.zombies_alive(),
            "spawned": self.spawned,
            "time": round(self.sim.now, 2),
            "time_left": round(max(0.0, self.max_seconds - self.sim.now), 2),
            "over": self.sim.over,
            "won": self.sim.won,
        }

    def cards(self) -> List[Dict[str, Any]]:
        """卡栏：与主线同结构，方便渲染层复用（sun 字段放的是"预算价"）。"""
        out = []
        for k in self.allowed:
            d = self.reg.enemies.get(k) or {}
            out.append({"key": k, "cn": d.get("cn", k), "sun": self.cost(k),
                        "kind": "enemy"})
        return out


class ZombieBot:
    """headless 用的投放策略。

    关键教训：早期版本"永远往植物最多的行丢"，结果 30 只僵尸全堆一行，
    清完那行后集体撞死在最左侧割草机上，别的行一株没碰、预算烧光 —— 必输。
    正确打法是**按行分散**：优先补给"还有植物但当前没兵"的行。
    """

    def __init__(self, decide_every: float = 0.6, per_row_limit: int = 2,
                 cheap_first: bool = False):
        self.decide_every = decide_every
        self.per_row_limit = per_row_limit
        # 默认真"强度优先"。原因：豌豆射手射程覆盖整行，20 dps 5 秒就能打死
        # 100 血的普通僵尸，而走完全程要 14.5 秒 —— 普通/快速僵尸永远摸不到豌豆，
        # 买了就是纯浪费预算（实测 cheap_first=True 时，含铁桶的关卡也只有 0 胜率）。
        self.cheap_first = cheap_first
        self._last = -1.0

    def think(self, s: ZombieSession) -> None:
        if s.sim.now - self._last < self.decide_every:
            return
        self._last = s.sim.now
        rows = sorted({p.row for p in s.sim.plants})
        if not rows:
            return
        busy: Dict[int, int] = {}
        for e in s.sim.enemies:
            busy[e.row] = busy.get(e.row, 0) + 1
        # 兵最少的行先补，保证同时向所有残存防线施压
        for row in sorted(rows, key=lambda r: busy.get(r, 0)):
            if busy.get(row, 0) >= self.per_row_limit:
                continue
            order = sorted(s.allowed, key=lambda k: s.cost(k))
            if not self.cheap_first:
                order = list(reversed(order))
            for key in order:
                if s.can_place(key, row)[0]:
                    s.place_zombie(key, row)
                    return


def run_level(level: Dict[str, Any], reg, seed: int = 1000,
              decide_every: float = 0.6, per_row_limit: int = 3,
              cheap_first: bool = False) -> Dict[str, Any]:
    """headless 跑一局我是僵尸，返回 metrics。"""
    s = ZombieSession(level, reg, seed=seed)
    bot = ZombieBot(decide_every, per_row_limit=per_row_limit, cheap_first=cheap_first)
    guard = 0
    while not s.sim.over and guard < 20000:
        bot.think(s)
        s.tick(C.DT)
        guard += 1
    st = s.status()
    st["duration"] = round(s.sim.now, 2)
    st["budget_left"] = s.budget
    return st
