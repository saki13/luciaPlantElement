# -*- coding: utf-8 -*-
"""规则化自动布阵器（headless 里替代真人），按正常 PVZ 玩家节奏运营。

优先级：①危急行补墙（且该行已有火力）②给最危险的缺火力行补输出 ③余钱才扩经济。
smart=True  读场上威胁按 counter_map 思路选解（破盾/爆发/AoE/控制/肉盾）；
smart=False 只铺基础直射+经济+墙，用于验证教学关丢车、低品阶打不过 T10 Boss。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .. import config as C
from .board import Simulation

# 敌人从右（高 col=入口）向左（低 col=家）：墙放前排高列，火力在后排低列
ECON_COLS = (0,)
WALL_COL = 7
OUTPUT_COLS = tuple(range(2, 7))
WALL_KEYS = {"wallnut"}
ECON_KEYS = {"sunbloom"}


class RuleBot:
    def __init__(self, card_pool: Sequence[str], smart: bool = True, decide_every: float = 0.3,
                 max_sunflowers: int = 5):
        self.pool = list(card_pool)
        self.smart = smart
        self.decide_every = decide_every
        self.max_sunflowers = max_sunflowers
        self._last = -1.0

    # ------------------------------------------------------------------
    def think(self, sim: Simulation) -> None:
        if sim.now - self._last < self.decide_every:
            return
        self._last = sim.now

        # 火力/破盾优先于补墙：需要破盾时保证 150 阳光一够就先出破盾株，不被补墙吃光
        self._emergency_fire(sim)
        self._emergency_walls(sim)
        self._grow_economy(sim)
        self._balance_firepower(sim)

    def _try_place(self, sim: Simulation, key: str, row: int, cols: Sequence[int]) -> bool:
        if key not in self.pool:
            return False
        for col in cols:
            if sim.can_place(key, row, col)[0]:
                return sim.place_plant(key, row, col)
        return False

    def _count(self, sim: Simulation, key: str) -> int:
        return sum(1 for p in sim.plants if p.key == key)

    def _outputs_in_row(self, sim: Simulation, row: int) -> int:
        return sum(1 for p in sim.plants if p.row == row
                   and p.key not in ECON_KEYS and p.key not in WALL_KEYS)

    def _nearest(self, sim: Simulation, row: int) -> Optional[float]:
        xs = [e.x for e in sim.enemies if e.row == row]
        return min(xs) if xs else None

    # ------------------------------------------------------------------ ① 危急墙
    def _emergency_walls(self, sim: Simulation) -> None:
        if "wallnut" not in self.pool:
            return
        for row in range(C.ROWS):
            nx = self._nearest(sim, row)
            if nx is None or nx >= 8.0:
                continue
            has_wall = any(p.row == row and p.key in WALL_KEYS for p in sim.plants)
            has_fire = self._outputs_in_row(sim, row) >= 1
            if not has_wall and has_fire:
                self._try_place(sim, "wallnut", row, (WALL_COL, 6))

    def _row_needs_break(self, sim: Simulation, row: int) -> bool:
        """本行有格挡敌人且尚无破盾株：需刚性预留阳光出破盾，别再砸对盾无效的直射。"""
        if not self.smart:
            return False
        if not any(self._plant_has_tag(sim, k, "shield_break") for k in self.pool):
            return False
        if not any(e.row == row and e.block_flat > 0 for e in sim.enemies):
            return False
        return not any(p.row == row and self._plant_has_tag(sim, p.key, "shield_break")
                       for p in sim.plants)

    def _emergency_fire(self, sim: Simulation) -> None:
        # 只要有敌人的行还完全没火力，立刻补一株（最高军事优先，避免空门）
        for row in range(C.ROWS):
            if self._nearest(sim, row) is None or self._outputs_in_row(sim, row) != 0:
                continue
            if self._row_needs_break(sim, row):
                self._try_place(sim, "custom_shieldbreaker", row, OUTPUT_COLS)
                return
            for key in self._preferences(sim, [], row):
                if self._try_place(sim, key, row, OUTPUT_COLS):
                    return

    # ------------------------------------------------------------------ ② 火力
    def _balance_firepower(self, sim: Simulation) -> None:
        # 行优先级：有敌人的行按最逼近排序，其次按现有火力多少（少的优先）
        threatened = []
        for row in range(C.ROWS):
            nx = self._nearest(sim, row)
            if nx is not None:
                threatened.append((nx, self._outputs_in_row(sim, row), row))
        threatened.sort(key=lambda z: (z[0], z[1]))

        # 余钱堆积时进入爆兵节奏，更快把每行铺满，把阳光转成战力
        boom = sim.sun >= 300
        for _, _, row in threatened:
            target = len(OUTPUT_COLS) if boom else 1 + int(sim.now // 8.0)
            if self._outputs_in_row(sim, row) >= min(target, len(OUTPUT_COLS)):
                continue
            if self._row_needs_break(sim, row):
                # 刚性破盾：只尝试破盾株，买不起就保留现金等下一轮，不在该行砸无效直射
                self._try_place(sim, "custom_shieldbreaker", row, OUTPUT_COLS)
                continue
            for key in self._preferences(sim, [], row):
                if self._try_place(sim, key, row, OUTPUT_COLS):
                    return

        # 中后期有余力再向暂无敌人的行预铺，避免前期分散资源
        if sim.now >= 30.0:
            for row in range(C.ROWS):
                if self._outputs_in_row(sim, row) == 0 or boom:
                    if self._outputs_in_row(sim, row) >= len(OUTPUT_COLS):
                        continue
                    for key in self._preferences(sim, [], row):
                        if self._try_place(sim, key, row, OUTPUT_COLS):
                            return

    # ------------------------------------------------------------------ ③ 经济（标准 PVZ 经济流）
    def _flower_target(self, sim: Simulation) -> int:
        if sim.now < 30:
            return 3
        if sim.now < 55:
            return 4
        return self.max_sunflowers

    def _grow_economy(self, sim: Simulation) -> None:
        if "sunbloom" not in self.pool:
            return
        n = self._count(sim, "sunbloom")
        if n >= self._flower_target(sim):
            return
        # 敌人已逼近（nx<6）时军事优先，暂停扩经济，避免家门口还在种花
        if any(self._nearest(sim, r) is not None and self._nearest(sim, r) < 6.0
               for r in range(C.ROWS)):
            return
        for row in range(C.ROWS):
            if self._try_place(sim, "sunbloom", row, ECON_COLS):
                return

    def _plant_has_tag(self, sim: Simulation, key: str, tag: str) -> bool:
        return tag in sim.plant_defs.get(key, {}).get("tags", [])

    # ------------------------------------------------------------------ counter 偏好序列（高优先级在前；格挡由 _row_needs_break 刚性处理）
    def _preferences(self, sim: Simulation, threats: List[Any], row: int) -> List[str]:
        # 全场威胁用于 AoE/爆发/控制类备战
        watch = list(sim.enemies)
        has_armor = any(e.armor_hp > 0 for e in watch)
        is_fast = any(e.base_speed >= 55 for e in watch)
        swarm = len(watch) >= 5
        elite = any("giant" in e.tags or "boss" in e.tags for e in watch)

        if not self.smart:
            return ["repeater", "peashooter", "morningglory"]
        if elite:
            return ["winter_melon", "melonpult", "bombberry", "pine_needler", "repeater", "peashooter"]
        if has_armor:
            return ["bombberry", "melonpult", "winter_melon", "repeater", "peashooter"]
        if swarm:
            return ["pine_needler", "leafdancer", "melonpult", "bombberry", "repeater", "peashooter"]
        if is_fast:
            return ["frostbell", "repeater", "peashooter"]
        return ["repeater", "peashooter", "morningglory"]
