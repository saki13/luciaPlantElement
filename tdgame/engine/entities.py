# -*- coding: utf-8 -*-
"""运行时实体：只持有动态状态，静态数值来自加载后的 JSON 定义（dict）。"""
from __future__ import annotations

from typing import Any, Dict, Optional


class Plant:
    def __init__(self, key: str, row: int, col: int, definition: Dict[str, Any], now: float):
        self.key = key
        self.row = row
        self.col = col
        self.defn = definition
        self.hp = float(definition.get("hp", 100))
        self.hp_max = self.hp
        self.placed_at = now
        self.attack_timer = 0.0          # 距下次攻击的倒计时
        self.shot_count = 0              # 已发射次数（every_n 技能用）
        self.strike_count = 0
        self.produce_timer = float((definition.get("economy") or {}).get("first", 0))
        self.fuse_timer = None           # 一次性植物引信（爆栗）
        fuse = ((definition.get("combat") or {}).get("on_place") or {}).get("fuse")
        if fuse is not None:
            self.fuse_timer = float(fuse)
        self.alive = True

    @property
    def cx(self) -> float:
        return self.col + 0.5

    @property
    def role(self) -> str:
        return self.defn.get("role", "ranged")


class Enemy:
    def __init__(self, key: str, row: int, definition: Dict[str, Any], spawn_x: float):
        self.key = key
        self.row = row
        self.defn = definition
        self.x = float(spawn_x)                       # 前缘格坐标，从右向左减小
        self.hp_body = float(definition["hp_body"])
        self.hp_body_max = self.hp_body
        self.armor_hp = float(definition.get("armor", {}).get("hp", 0) or 0)
        self.armor_hp_max = self.armor_hp
        self.armor_reduction = float(definition.get("armor", {}).get("reduction", 0) or 0)
        self.block_flat = float(definition.get("block_flat", 0) or 0)
        self.base_speed = float(definition["speed"])
        self.bite_dps = float(definition.get("bite_dps", 25))
        self.weight = float(definition.get("weight", 1))
        self.slow_resist = float(definition.get("slow_resist", 0))
        self.kb_immune = bool(definition.get("kb_immune", False))
        self.regen = float(definition.get("regen", 0) or 0)
        self.slow_until = -1.0
        self.slow_mult = 1.0
        self.eating: Optional[Plant] = None
        self.dead = False
        self.breached = False
        self.tags = set(definition.get("tags", []))

    def current_speed_mult(self, now: float) -> float:
        return self.slow_mult if now < self.slow_until else 1.0


class Projectile:
    def __init__(self, owner: Plant, row: int, x: float, spec: Dict[str, Any], damage: float,
                 tags, is_skill: bool = False):
        self.owner_key = owner.key
        self.row = row
        self.x = x
        self.spec = spec                  # projectile 静态段（speed/hit/on_hit/slow/...）
        self.damage = damage
        self.tags = set(tags or ())
        self.is_skill = is_skill
        self.dead = False
        self.hit_left = self._pierce_count()

    def _pierce_count(self) -> int:
        hit = str(self.spec.get("hit", "single"))
        if hit.startswith("pierce:"):
            return int(hit.split(":", 1)[1]) + 1     # 穿透 n 个 = 命中 n+1 体
        return 1

    @property
    def speed(self) -> float:
        return float(self.spec.get("speed", 300)) / 76.0     # px/s -> 格/s
