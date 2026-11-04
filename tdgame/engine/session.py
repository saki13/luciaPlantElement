# -*- coding: utf-8 -*-
"""交互会话：把 `Simulation` 包成"玩家可操作"的状态机。

设计原则：**所有交互逻辑都在这里，渲染层只负责两件事**——把鼠标坐标换算成 (row, col)，
以及把 `entities()` / `cards()` / `status()` 画出来。

这样点选、种植、铲种、冷却、胜负判断全都能在 headless 下单测，
既不依赖 pygame 也不依赖 Godot，将来 Godot 版可以直接复用同一套语义。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .. import config as C
from ..scenarios.level_run import build_schedule_from_level
from .board import Simulation

SHOVEL = "__shovel__"

# 单次 tick 内最多推进的仿真步数，防止极端 dt 让一帧卡死
_MAX_STEPS_PER_TICK = 200


class PlaySession:
    """一局玩家对局。``level`` 是 `data/levels/*.json` 里的一份定义。"""

    def __init__(self, level: Dict[str, Any], reg, seed: int = 1000) -> None:
        self.level = level
        self.reg = reg
        self.seed = seed
        self.pool: List[str] = list(level["card_pool"])
        schedule = build_schedule_from_level(level, reg.enemies, seed)
        self.sim = Simulation(
            reg.plants, reg.enemies, schedule, self.pool, seed=seed,
            start_resource=int(level.get("start_resource", C.START_RESOURCE)),
            max_seconds=float(level.get("max_seconds", 300)),
        )
        self.selected: Optional[str] = None
        self.message = ""
        self._acc = 0.0

    # ------------------------------------------------------------------ 选择
    def select(self, key: Optional[str]) -> None:
        """选中一张卡（或取消）。不在卡池里的 key 会被忽略。"""
        if key is not None and key != SHOVEL and key not in self.pool:
            return
        self.selected = key

    def toggle_shovel(self) -> None:
        self.selected = None if self.selected == SHOVEL else SHOVEL

    # ------------------------------------------------------------------ 操作
    def place(self, row: int, col: int) -> Tuple[bool, str]:
        if self.sim.over:
            return False, "over"
        if self.selected in (None, SHOVEL):
            return False, "no_selection"
        ok, reason = self.sim.can_place(self.selected, row, col)
        if not ok:
            self.message = reason
            return False, reason
        self.sim.place_plant(self.selected, row, col)
        self.selected = None          # 种下后自动取消选择，与 PVZ 一致
        self.message = ""
        return True, "ok"

    def shovel(self, row: int, col: int) -> Tuple[bool, str]:
        if self.sim.over:
            return False, "over"
        if self.sim.remove_plant(row, col):
            self.message = ""
            return True, "ok"
        self.message = "empty"
        return False, "empty"

    def click_cell(self, row: int, col: int) -> Tuple[bool, str]:
        """按当前选择分发：铲子 -> 铲；卡片 -> 种；未选择 -> 忽略。"""
        if self.selected == SHOVEL:
            return self.shovel(row, col)
        return self.place(row, col)

    # ------------------------------------------------------------------ 时间
    def tick(self, dt_seconds: float) -> None:
        """推进真实时间；内部按固定步长 DT 累计，保证与 headless 完全一致。"""
        if self.sim.over:
            return
        self._acc += max(0.0, float(dt_seconds))
        steps = 0
        while self._acc >= C.DT and not self.sim.over and steps < _MAX_STEPS_PER_TICK:
            self.sim.step(C.DT)
            self._acc -= C.DT
            steps += 1

    # ------------------------------------------------------------------ 查询
    @property
    def over(self) -> bool:
        return self.sim.over

    @property
    def won(self) -> bool:
        return self.sim.won

    @property
    def sun(self) -> int:
        return self.sim.sun

    @property
    def lives(self) -> int:
        return self.sim.lives

    def cards(self) -> List[Dict[str, Any]]:
        """卡栏展示数据：阳光价、冷却剩余、是否买得起、是否选中。"""
        out: List[Dict[str, Any]] = []
        for key in self.pool:
            d = self.sim.plant_defs[key]
            price = int(d.get("sun", 0))
            cd = float(self.sim.cooldown_left.get(key, 0.0))
            out.append({
                "key": key,
                "sun": price,
                "cd": round(cd, 2),
                "cd_max": float(d.get("recharge", C.RECHARGE_MID)),
                "affordable": self.sim.sun >= price,
                "ready": cd <= 0.0,
                "selected": self.selected == key,
            })
        return out

    def entities(self) -> Dict[str, List[Dict[str, Any]]]:
        """渲染层要画的动态实体，坐标一律用格。"""
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
        return {
            "sun": self.sun, "lives": self.lives,
            "over": self.over, "won": self.won,
            "time": round(self.sim.now, 1),
            "plants": len(self.sim.plants), "enemies": len(self.sim.enemies),
            "selected": self.selected, "message": self.message,
            "level": self.level.get("key", "?"),
        }
