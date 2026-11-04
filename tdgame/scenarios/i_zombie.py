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
        """卡栏：与主线同结构，方便渲染层复用（sun 字段放的是"预算价"）。

        渲染层会读 `affordable` / `ready` 来画变暗与冷却遮罩，所以这里也要给全；
        我是僵尸没有卡片冷却，`ready` 恒为 True。
        """
        out = []
        for k in self.allowed:
            d = self.reg.enemies.get(k) or {}
            cost = self.cost(k)
            out.append({"key": k, "cn": d.get("cn", k), "sun": cost,
                        "kind": "enemy",
                        "cd": 0.0, "cd_max": 1.0,
                        "affordable": cost <= self.budget,
                        "ready": True, "selected": False})
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


class ZombiePlaySession:
    """把 `ZombieSession` 适配成 `GameApp` 期待的 `PlaySession` 形状。

    渲染层只认这几个成员（pool / cards / select / click_cell / entities /
    status / tick / sun / lives / over / won / selected），所以这里做一层薄适配，
    而不是让渲染层去分辨两种模式 —— 这样 `app_pygame` 的绘制代码一行都不用改。
    """

    def __init__(self, level: Dict[str, Any], reg, seed: int = 0):
        self.core = ZombieSession(level, reg, seed=seed)
        self.sim = self.core.sim
        self.level = level
        self.selected: Optional[str] = None
        self.pool: List[str] = list(self.core.allowed)
        self.message = ""

    # ---------------------------------------------------------------- 只读属性
    @property
    def over(self) -> bool:
        return self.sim.over

    @property
    def won(self) -> bool:
        return self.sim.won

    @property
    def sun(self) -> int:
        """顶部面板显示阳光的位置，这里显示剩余预算。"""
        return self.core.budget

    @property
    def lives(self) -> int:
        """我是僵尸没有"命"的概念，返回 0 让渲染层不画小车。"""
        return 0

    # ---------------------------------------------------------------- 交互
    def cards(self) -> List[Dict[str, Any]]:
        return self.core.cards()

    def cards(self) -> List[Dict[str, Any]]:
        """渲染层还要读 `selected` 来画高亮，它属于会话层而不是核心层。"""
        cards = self.core.cards()
        for c in cards:
            c["selected"] = (c["key"] == self.selected)
        return cards

    def select(self, key: str) -> bool:
        if key not in self.core.allowed:
            return False
        self.selected = key
        return True

    def toggle_shovel(self) -> None:
        """该模式没有铲子（植物是关卡预置的）。"""
        return None

    def click_cell(self, row: int, col: int) -> Tuple[bool, str]:
        if self.over:
            return False, "over"
        if self.selected is None:
            return False, "no_selection"
        ok, why = self.core.can_place(self.selected, row)
        if not ok:
            return False, why
        self.core.place_zombie(self.selected, row)
        return True, "ok"

    # ---------------------------------------------------------------- 帧
    def tick(self, dt_seconds: float) -> None:
        self.core.tick(dt_seconds)

    def entities(self) -> Dict[str, List[Dict[str, Any]]]:
        plants = [
            {"key": p.key, "row": p.row, "col": p.col,
             "hp_ratio": max(0.0, p.hp / p.hp_max) if p.hp_max else 0.0}
            for p in self.sim.plants
        ]
        enemies = [
            {"key": e.key, "row": e.row, "x": e.x,
             "hp_ratio": max(0.0, e.hp_body / e.hp_body_max) if e.hp_body_max else 0.0,
             "eating": e.eating is not None}
            for e in self.sim.enemies
        ]
        projectiles = [
            {"row": p.row, "x": p.x, "key": str(p.spec.get("key", p.owner_key))}
            for p in self.sim.projectiles
        ]
        return {"plants": plants, "enemies": enemies, "projectiles": projectiles}

    def status(self) -> Dict[str, Any]:
        st = self.core.status()
        st["selected"] = self.selected
        st["message"] = self.message
        st["level"] = st.get("key", "?")
        # 渲染层的历史字段名（PlaySession.status 用的就是这两个）
        st["plants"] = st.get("plants_left", 0)
        st["enemies"] = st.get("zombies_alive", 0)
        return st


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
