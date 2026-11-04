# -*- coding: utf-8 -*-
"""headless 战斗模拟：固定步长离散引擎，覆盖 v0.2 §3/§4 全部战斗机制。

坐标：行 0..ROWS-1；格坐标 x 连续，植物占列 col（区间 [col, col+1)，中心 col+0.5），
敌人前缘 x 从板右 (COLS+0.5) 向左移动到 -0.2 触发小车/破线。时间单位秒。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import config as C
from .. import balance
from .entities import Enemy, Plant, Projectile


class Simulation:
    def __init__(self, plant_defs: Dict[str, Dict[str, Any]], enemy_defs: Dict[str, Dict[str, Any]],
                 spawn_schedule: Sequence[Tuple[float, str, Optional[int]]], card_pool: Sequence[str],
                 seed: int = 0, start_resource: int = C.START_RESOURCE,
                 max_seconds: float = 600.0, sky_sun: bool = True,
                 objective: str = "survive"):
        self.plant_defs = plant_defs
        self.enemy_defs = enemy_defs
        self.schedule = sorted(spawn_schedule, key=lambda z: z[0])
        self.card_pool = list(card_pool)
        self.rng_seed = seed
        self._rand_state = seed
        self.max_seconds = max_seconds
        self.sky_sun_enabled = sky_sun
        # "survive"（默认，主线：守住 N 波）或 "devour"（M5 我是僵尸：把场上植物啃光）
        self.objective = objective

        self.reset(start_resource)

    # ------------------------------------------------------------------ 初始化
    def reset(self, start_resource: int = C.START_RESOURCE) -> None:
        self.now = 0.0
        self.sun = int(start_resource)
        self.lives = C.START_LIVES
        self.plants: List[Plant] = []
        self.enemies: List[Enemy] = []
        self.projectiles: List[Projectile] = []
        self.mowers = {r: True for r in range(C.ROWS)}
        self.cooldown_left: Dict[str, float] = {}
        self.sky_timer = C.SKY_SUN_INTERVAL
        self._spawn_idx = 0
        self.over = False
        self.won = False
        self.kills: Dict[str, int] = {}
        self.mowers_used = 0
        self.breaches = 0
        self.sun_earned = 0
        self.plants_placed = 0
        self.event_log: List[str] = []

    # ------------------------------------------------------------------ 随机（确定性 LCG，行分配用）
    def _rand(self) -> float:
        self._rand_state = (1103515245 * self._rand_state + 12345) & 0x7FFFFFFF
        return self._rand_state / 0x7FFFFFFF

    # ------------------------------------------------------------------ 布阵 API（bot / 真机共用）
    def plant_at(self, row: int, col: int) -> Optional[Plant]:
        for p in self.plants:
            if p.alive and p.row == row and p.col == col:
                return p
        return None

    def can_place(self, key: str, row: int, col: int) -> Tuple[bool, str]:
        if self.objective == "devour":
            return False, "devour_mode"      # 我是僵尸：植物是关卡预置的，玩家不能种
        if key not in self.card_pool or key not in self.plant_defs:
            return False, "not_in_pool"
        if not (0 <= row < C.ROWS and 0 <= col < C.COLS):
            return False, "out_of_board"
        if self.plant_at(row, col) is not None:
            return False, "occupied"
        d = self.plant_defs[key]
        if self.cooldown_left.get(key, 0) > 0:
            return False, "recharging"
        if self.sun < d["sun"]:
            return False, "no_sun"
        return True, "ok"

    def place_plant(self, key: str, row: int, col: int) -> bool:
        ok, _ = self.can_place(key, row, col)
        if not ok:
            return False
        d = self.plant_defs[key]
        self.sun -= int(d["sun"])
        self.cooldown_left[key] = float(d.get("recharge", C.RECHARGE_MID))
        self.plants.append(Plant(key, row, col, d, self.now))
        self.plants_placed += 1
        return True

    def setup_plant(self, key: str, row: int, col: int) -> bool:
        """关卡预置植物：不走阳光/冷却，也不受 card_pool 限制（M5 我是僵尸用）。"""
        if key not in self.plant_defs:
            return False
        if not (0 <= row < C.ROWS and 0 <= col < C.COLS):
            return False
        if self.plant_at(row, col) is not None:
            return False
        self.plants.append(Plant(key, row, col, self.plant_defs[key], self.now))
        return True

    def spawn_enemy(self, key: str, row: int, x: Optional[float] = None) -> Optional[Enemy]:
        """按需在场上放一只敌人（M5 我是僵尸的"出怪"由玩家决定）。"""
        d = self.enemy_defs.get(key)
        if d is None or not (0 <= row < C.ROWS):
            return None
        e = Enemy(key, row, d, C.COLS + 0.5 if x is None else x)
        self.enemies.append(e)
        return e

    def remove_plant(self, row: int, col: int) -> bool:
        """铲掉指定格的植物（不返还阳光，与 PVZ 一致）。

        正在啃它的敌人会立即松开，避免 `eating` 指向已死对象。
        """
        target = self.plant_at(row, col)
        if target is None:
            return False
        target.alive = False
        for e in self.enemies:
            if e.eating is target:
                e.eating = None
        self.plants = [p for p in self.plants if p is not target]
        return True

    def _add_sun(self, amount: int) -> None:
        self.sun += amount
        self.sun_earned += amount

    # ------------------------------------------------------------------ 主步进
    def step(self, dt: float = C.DT) -> None:
        if self.over:
            return
        self.now = round(self.now + dt, 6)
        self._update_cooldowns(dt)
        self._update_economy(dt)
        self._spawn_due()
        self._update_plants(dt)
        self._update_projectiles(dt)
        self._update_enemies(dt)
        self._cleanup()
        self._check_end()

    def run_to_end(self, bot=None, frame_budget: int = 20000) -> Dict[str, Any]:
        """推进直到分胜负；bot 可选，需实现 think(sim) 在每步前布阵。"""
        frames = 0
        while not self.over and frames < frame_budget:
            if bot is not None:
                bot.think(self)
            self.step(C.DT)
            frames += 1
        return self.metrics()

    def _update_cooldowns(self, dt: float) -> None:
        for k in list(self.cooldown_left.keys()):
            self.cooldown_left[k] = max(0.0, self.cooldown_left[k] - dt)

    def _update_economy(self, dt: float) -> None:
        if self.sky_sun_enabled:
            self.sky_timer -= dt
            if self.sky_timer <= 0:
                self._add_sun(C.SKY_SUN_VALUE)
                self.sky_timer += C.SKY_SUN_INTERVAL
        for p in self.plants:
            if not p.alive:
                continue
            eco = p.defn.get("economy")
            if eco:
                p.produce_timer -= dt
                if p.produce_timer <= 0:
                    self._add_sun(int(eco.get("produce", C.SUN_VALUE)))
                    p.produce_timer += float(eco.get("interval", C.SUNFLOWER_INTERVAL))

    def _spawn_due(self) -> None:
        while self._spawn_idx < len(self.schedule) and self.schedule[self._spawn_idx][0] <= self.now:
            _, ekey, row = self.schedule[self._spawn_idx]
            r = row if row is not None else int(self._rand() * C.ROWS)
            self.enemies.append(Enemy(ekey, r, self.enemy_defs[ekey], C.COLS + 0.5))
            self._spawn_idx += 1

    # ------------------------------------------------------------------ 植物行为
    def _update_plants(self, dt: float) -> None:
        for p in self.plants:
            if not p.alive:
                continue
            # 一次性引信（爆栗果）
            if p.fuse_timer is not None:
                p.fuse_timer -= dt
                if p.fuse_timer <= 0:
                    self._detonate(p)
                    p.alive = False
                continue
            combat = p.defn.get("combat")
            if not combat:
                continue
            p.attack_timer -= dt
            if p.attack_timer <= 0:
                fired = self._plant_attack(p, combat)
                if fired:
                    p.attack_timer += float(combat["atk_interval"])

    def _plant_attack(self, p: Plant, combat: Dict[str, Any]) -> bool:
        rng = combat.get("range", {"type": "row", "cells": C.COLS})
        if rng.get("type") == "melee":
            target = self._melee_target(p, float(rng.get("cells", 1)))
            if target is None:
                return False
            p.strike_count += 1
            ability = combat.get("ability")
            is_heavy = ability and p.strike_count % int(ability.get("n", 3)) == 0
            if is_heavy:
                dmg = float(ability.get("damage", combat["damage"]))
                self._apply_damage(target, dmg, p.defn.get("tags", []))
                # 重劈溅射：上下相邻行同列附近，最多 3 体
                for er in (p.row - 1, p.row + 1):
                    neigh = self._enemy_near_col(er, p.col, float(ability.get("splash_radius_cells", 0.5)))
                    if neigh is not None:
                        self._apply_damage(neigh, dmg * float(ability.get("splash_damage_mult", 0.5)),
                                           p.defn.get("tags", []))
            else:
                self._apply_damage(target, float(combat["damage"]), p.defn.get("tags", []))
            return True
        # 远程
        target = self._ranged_target(p, float(rng.get("cells", C.COLS)))
        if target is None:
            return False
        proj_spec = combat["projectile"]
        ability = combat.get("ability")
        p.shot_count += 1
        is_skill = bool(ability and p.shot_count % int(ability.get("n", 4)) == 0)
        dmg = float(combat["damage"])
        tags = list(p.defn.get("tags", []))
        spec = proj_spec
        if is_skill and ability.get("use_projectile"):
            spec = self._skill_projectile(p, ability)
            dmg = float(ability.get("damage", dmg * ability.get("damage_mult", 1.0)))
        self.projectiles.append(Projectile(p, p.row, p.cx + 0.2, spec, dmg, tags, is_skill))
        return True

    def _skill_projectile(self, p: Plant, ability: Dict[str, Any]) -> Dict[str, Any]:
        """重籽等技能弹：在主 projectile 同结构上覆盖伤害/击退字段。"""
        base = dict(p.defn["combat"]["projectile"])
        if ability.get("knockback_cells"):
            base["knockback_cells"] = float(ability["knockback_cells"])
        base.update(ability.get("projectile_overrides", {}))
        return base

    def _ranged_target(self, p: Plant, range_cells: float) -> Optional[Enemy]:
        cands = [e for e in self.enemies if not e.dead and e.row == p.row
                 and e.x <= p.cx + range_cells and e.x > p.cx - 1.0]
        return min(cands, key=lambda e: e.x) if cands else None

    def _melee_target(self, p: Plant, range_cells: float) -> Optional[Enemy]:
        cands = [e for e in self.enemies if not e.dead and e.row == p.row
                 and e.x <= p.cx + 0.6 and e.x >= p.cx - 1.0]
        return min(cands, key=lambda e: e.x) if cands else None

    def _enemy_near_col(self, row: int, col: int, tol: float) -> Optional[Enemy]:
        center = col + 0.5
        cands = [e for e in self.enemies if not e.dead and e.row == row
                 and abs((e.x + 0.4) - center) <= tol + 0.4]
        return min(cands, key=lambda e: abs((e.x + 0.4) - center)) if cands else None

    def _detonate(self, p: Plant) -> None:
        expl = p.defn["combat"]["on_place"]["explosion"]
        self._area_damage(p.row, p.cx, float(expl["radius"]), float(expl["damage"]),
                          p.defn.get("tags", []), edge_mult=1.0)

    # ------------------------------------------------------------------ 弹道
    def _update_projectiles(self, dt: float) -> None:
        for pr in self.projectiles:
            if pr.dead:
                continue
            pr.x += pr.speed * dt                       # 子弹朝右（敌人入口方向）飞行拦截
            if pr.x > C.COLS + 1.0:
                pr.dead = True
                continue
            hit_enemy = self._projectile_find_target(pr)
            if hit_enemy is not None:
                self._resolve_projectile_hit(pr, hit_enemy)

    def _projectile_find_target(self, pr: Projectile) -> Optional[Enemy]:
        # 同一弹道上前后排，子弹最先撞上身体最靠左（最靠近家）的敌人
        cands = [e for e in self.enemies if not e.dead and e.row == pr.row
                 and pr.x >= e.x - 0.3 and pr.x <= e.x + 0.6]
        if not cands:
            return None
        return min(cands, key=lambda e: e.x)

    def _resolve_projectile_hit(self, pr: Projectile, enemy: Enemy) -> None:
        spec = pr.spec
        hit = str(spec.get("hit", "single"))
        # 直击
        self._apply_damage(enemy, pr.damage, pr.tags, spec=spec)
        # on_hit：直击 AoE + 碎片（松针）
        on_hit = spec.get("on_hit")
        if on_hit:
            cx = enemy.x + 0.4
            if on_hit.get("splash"):
                self._area_damage(enemy.row, cx, float(on_hit["splash"]["radius"]),
                                  float(on_hit["splash"]["damage"]), pr.tags,
                                  edge_mult=1.0, center_enemy=enemy)
            frag = on_hit.get("fragments")
            if frag:
                self._resolve_fragments(enemy, cx, frag, pr.tags)
        # 普通 splash 弹（西瓜类）
        if hit.startswith("splash:") and not on_hit:
            radius = float(hit.split(":", 1)[1])
            self._area_damage(enemy.row, enemy.x + 0.4, radius, pr.damage, pr.tags,
                              edge_mult=float(spec.get("edge_damage_mult", 1.0)), center_enemy=enemy)
        # 控制
        self._apply_control(enemy, spec)
        # 穿透计数
        pr.hit_left -= 1
        if pr.hit_left <= 0 or not hit.startswith("pierce:"):
            pr.dead = True

    def _resolve_fragments(self, center: Enemy, cx: float, frag: Dict[str, Any], tags) -> None:
        radius = float(frag.get("radius", 1))
        around = [e for e in self.enemies if not e.dead and abs(e.row - center.row) <= radius
                  and abs((e.x + 0.4) - cx) <= radius + 0.4]
        needle_dmg = float(frag["damage_each"])
        for e in around:
            hits = int(frag.get("center_hits", 2)) if e is center else int(frag.get("adjacent_hits", 1))
            for _ in range(hits):
                self._apply_damage(e, needle_dmg, tags)

    def _area_damage(self, row: int, cx: float, radius: float, damage: float, tags,
                     edge_mult: float = 1.0, center_enemy: Optional[Enemy] = None) -> None:
        for e in self.enemies:
            if e.dead or abs(e.row - row) > radius:
                continue
            if abs((e.x + 0.4) - cx) > radius + 0.4:
                continue
            mult = 1.0 if (center_enemy is not None and e is center_enemy) else edge_mult
            self._apply_damage(e, damage * mult, tags)

    # ------------------------------------------------------------------ 伤害/控制落地
    def _apply_damage(self, enemy: Enemy, raw: float, tags, spec: Optional[Dict[str, Any]] = None) -> None:
        ap = spec.get("ap_mult") if spec else None
        balance.resolve_hit(enemy, raw, tags, ap_mult=ap)

    def _apply_control(self, enemy: Enemy, spec: Dict[str, Any]) -> None:
        slow = spec.get("slow")
        if slow:
            enemy.slow_mult = balance.effective_speed_mult(float(slow["factor"]), enemy.slow_resist)
            enemy.slow_until = self.now + float(slow.get("duration", 2.5))
        kb = spec.get("knockback_cells")
        if kb:
            dist = balance.knockback_distance(float(kb), enemy.weight, enemy.kb_immune)
            enemy.x = min(C.COLS + 0.5, enemy.x + dist)

    # ------------------------------------------------------------------ Boss 机制（M3）
    def _update_boss_phases(self) -> None:
        """本体血量跌破阈值 -> 进二阶段：提速、召唤更频繁。"""
        for e in self.enemies:
            if e.dead or e.phase != 1 or e.phase_hp_ratio <= 0:
                continue
            if e.hp_body_max <= 0:
                continue
            if (e.hp_body / e.hp_body_max) <= e.phase_hp_ratio:
                e.phase = 2
                e.base_speed *= e.phase_speed_mult
                if e.summon_interval > 0:
                    e.summon_interval *= e.phase_summon_mult
                self.event_log.append(f"t={self.now:.1f} {e.key} phase2")

    def _update_summons(self, dt: float) -> None:
        """会召唤的敌人：每 interval 秒生一只 mob，同父存活数不超过 max_alive。"""
        for e in list(self.enemies):
            if e.dead or not e.summon_mob or e.summon_interval <= 0:
                continue
            e.summon_timer -= dt
            if e.summon_timer > 0:
                continue
            e.summon_timer += e.summon_interval
            alive = sum(1 for c in self.enemies if not c.dead and c.summoned_by is e)
            if alive >= e.summon_max:
                continue
            mob_def = self.enemy_defs.get(e.summon_mob)
            if not mob_def:
                continue
            child = Enemy(e.summon_mob, e.row, mob_def, min(C.COLS + 0.5, e.x + 0.8))
            child.summoned_by = e
            self.enemies.append(child)
            self.event_log.append(f"t={self.now:.1f} {e.key} summon {e.summon_mob}")

    # ------------------------------------------------------------------ 敌人移动 / 啃食
    def _update_enemies(self, dt: float) -> None:
        self._update_boss_phases()
        self._update_summons(dt)
        for e in self.enemies:
            if e.dead:
                continue
            if e.regen > 0 and e.hp_body < e.hp_body_max:
                e.hp_body = min(e.hp_body_max, e.hp_body + e.regen * dt)
            blocker = self._blocker_for(e)
            if blocker is not None:
                e.eating = blocker
                dmg = e.bite_dps * dt
                passive = blocker.defn.get("passive") or {}
                dmg *= float(passive.get("frontal_damage_taken_mult", 1.0))
                blocker.hp -= dmg
                if blocker.hp <= 0:
                    blocker.alive = False
                    e.eating = None
            else:
                e.eating = None
                e.x -= e.base_speed * e.current_speed_mult(self.now) * dt / C.CELL
                if e.x <= C.LAWN_MOWER_TRIGGER_X:
                    self._handle_breach(e)

    def _blocker_for(self, e: Enemy) -> Optional[Plant]:
        cands = [p for p in self.plants if p.alive and p.row == e.row and (p.col + 1) >= e.x - 1e-9]
        if not cands:
            return None
        target = max(cands, key=lambda p: p.col)
        return target if e.x <= target.col + 1.0 + 1e-9 else None

    def _handle_breach(self, e: Enemy) -> None:
        # mower_immune 的 Boss 级单位不吃割草机，直接算破线扣命
        if self.mowers.get(e.row, False) and not e.mower_immune:
            self.mowers[e.row] = False
            self.mowers_used += 1
            # 割草机清场，但碾不动 mower_immune 的 Boss 级单位
            for other in [x for x in self.enemies
                          if x.row == e.row and not x.dead and not x.mower_immune]:
                other.dead = True
                self.kills[other.key] = self.kills.get(other.key, 0) + 1
            self.event_log.append(f"t={self.now:.1f} row{e.row} mower")
        else:
            e.breached = True
            e.dead = True
            self.breaches += 1
            self.lives -= 1
            self.event_log.append(f"t={self.now:.1f} row{e.row} breach lives={self.lives}")
            # Boss 冲到家里 = 这一局彻底失败。不能把它从 enemies 里移除后
            # 让 "出怪表跑完且场上无敌人" 误判成通关。
            if e.mower_immune:
                self.over, self.won = True, False
                self.event_log.append(f"t={self.now:.1f} {e.key} breached -> defeat")

    # ------------------------------------------------------------------ 清理 / 结束
    def _cleanup(self) -> None:
        for e in self.enemies:
            if not e.dead and e.hp_body <= 0:
                e.dead = True
        for e in self.enemies:
            if e.dead and not e.breached and e.hp_body <= 0 and getattr(e, "_counted", False) is False:
                e._counted = True
                self.kills[e.key] = self.kills.get(e.key, 0) + 1
        self.enemies = [e for e in self.enemies if not e.dead]
        self.plants = [p for p in self.plants if p.alive]
        self.projectiles = [p for p in self.projectiles if not p.dead]

    def _check_end(self) -> None:
        if self.over:                    # 已有结论（例如 Boss 破线判负）就别覆盖
            return
        if self.objective == "devour":
            # M5 我是僵尸：把场上植物全部啃光算通关，超时算失败。
            # 注意这里**不能**走下面"出怪表跑完且场上无敌人"的判定 ——
            # 该模式的敌人是玩家按需放的，开局场上一只都没有。
            if not self.plants:
                self.over, self.won = True, True
                return
            if self.now >= self.max_seconds:
                self.over, self.won = True, False
            return
        if self.lives <= 0:
            self.over, self.won = True, False
            return
        if self._spawn_idx >= len(self.schedule) and not self.enemies:
            self.over, self.won = True, True
            return
        if self.now >= self.max_seconds:
            self.over, self.won = True, False

    def metrics(self) -> Dict[str, Any]:
        return {
            "won": self.won, "duration": round(self.now, 2), "sun_left": self.sun,
            "sun_earned": self.sun_earned, "mowers_used": self.mowers_used,
            "breaches": self.breaches, "lives_left": max(0, self.lives),
            "kills": dict(self.kills), "plants_placed": self.plants_placed,
            "plants_alive": len(self.plants), "seed": self.rng_seed,
        }
