# -*- coding: utf-8 -*-
"""headless 引擎行为测试：啃食/小车/AoE/碎片/控制/确定性/胜负/加载校验。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame import config as C
from tdgame.engine.loader import load_registry
from tdgame.engine.board import Simulation
from tdgame.engine.entities import Enemy
from tdgame.engine.wavegen import build_schedule, fixed_schedule
from tdgame.engine.bot import RuleBot

DATA = ROOT / "tdgame" / "data"


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.reg = load_registry(DATA)

    def test_no_validation_errors_and_counts(self):
        self.assertEqual(self.reg.errors, [])
        self.assertGreaterEqual(len(self.reg.plants), 13)
        self.assertGreaterEqual(len(self.reg.enemies), 8)
        self.assertEqual(set(self.reg.counter_map["matchups"]),
                         {"block", "armor", "thick_body", "speed", "swarm",
                          "weight_control_immune", "high_bite"})

    def test_nominal_ehp_locked(self):
        self.assertEqual(self.reg.enemies["cone"]["_nominal_hp"], 280)
        self.assertEqual(self.reg.enemies["bucket"]["_nominal_hp"], 650)
        self.assertEqual(self.reg.enemies["boss_50"]["_nominal_hp"], 4400)


class EngineBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.reg = load_registry(DATA)
        self.pd, self.ed = self.reg.plants, self.reg.enemies

    def sim(self, schedule=None, pool=None):
        return Simulation(self.pd, self.ed, schedule or [], pool or list(self.pd), seed=1,
                          max_seconds=300)

    def spawn(self, key, row, x):
        e = Enemy(key, row, self.ed[key], x)
        sim = self.sim()
        sim.enemies.append(e)
        return sim, e

    def test_biting_damages_plant(self):
        sim = self.sim()
        sim.place_plant("wallnut", 0, 1)
        wall = sim.plant_at(0, 1)
        e = Enemy("normal", 0, self.ed["normal"], 2.0)
        sim.enemies.append(e)
        for _ in range(50):
            sim.step()
        self.assertIsNotNone(e.eating)
        self.assertAlmostEqual(wall.hp, 800 - 25 * C.DT * 50, places=3)

    def test_mower_clears_row_without_losing_life(self):
        sim = self.sim()
        sim.enemies.append(Enemy("normal", 0, self.ed["normal"], C.LAWN_MOWER_TRIGGER_X))
        for _ in range(3):
            sim.step()
        self.assertFalse(sim.mowers[0])
        self.assertEqual(sim.mowers_used, 1)
        self.assertEqual(sim.lives, 5)
        self.assertEqual(len([e for e in sim.enemies if e.row == 0]), 0)

    def test_breach_without_mower_costs_life(self):
        sim = self.sim()
        sim.mowers[0] = False
        sim.enemies.append(Enemy("normal", 0, self.ed["normal"], C.LAWN_MOWER_TRIGGER_X))
        for _ in range(3):
            sim.step()
        self.assertEqual(sim.breaches, 1)
        self.assertEqual(sim.lives, 4)

    def test_area_damage_hits_multiple_rows(self):
        sim = self.sim()
        targets = [Enemy("normal", r, self.ed["normal"], 4.4) for r in (0, 1)]
        sim.enemies.extend(targets)
        sim._area_damage(0, 4.4, 1.0, 180, [])
        for e in targets:
            self.assertLessEqual(e.hp_body, 0)

    def test_pine_center_74_adjacent_32(self):
        sim = self.sim()
        center = Enemy("normal", 0, self.ed["normal"], 4.4)
        adjacent = Enemy("normal", 1, self.ed["normal"], 4.4)
        sim.enemies.extend([center, adjacent])
        spec = self.pd["pine_needler"]["combat"]["projectile"]
        on = spec["on_hit"]
        sim._apply_damage(center, 30, [])                                   # 球直击
        sim._area_damage(0, 4.8, 1.0, on["splash"]["damage"], [])           # 命中 AoE
        sim._resolve_fragments(center, 4.8, on["fragments"], [])            # 松针
        self.assertEqual(round(100 - center.hp_body), 74)
        self.assertEqual(round(100 - adjacent.hp_body), 32)

    def test_shield_fully_counters_fragments(self):
        sim = self.sim()
        shield = Enemy("shield_cadet", 0, self.ed["shield_cadet"], 4.4)
        sim.enemies.append(shield)
        spec = self.pd["pine_needler"]["combat"]["projectile"]
        on = spec["on_hit"]
        sim._apply_damage(shield, 30, [])                                   # 30-20=10
        sim._area_damage(0, 4.8, 1.0, on["splash"]["damage"], [])           # 20 -> 0
        sim._resolve_fragments(shield, 4.8, on["fragments"], [])            # 12 针全归零
        self.assertEqual(round(100 - shield.hp_body), 10)

    def test_slow_and_knockback_control(self):
        sim = self.sim()
        e = Enemy("normal", 0, self.ed["normal"], 5.0)
        sim.enemies.append(e)
        sim._apply_control(e, {"slow": {"factor": 0.5, "duration": 2.5}, "knockback_cells": 0.3})
        self.assertEqual(e.slow_mult, 0.5)
        self.assertGreater(e.slow_until, sim.now)
        self.assertAlmostEqual(e.x, 5.3, places=4)
        # 铁桶 weight2 + slow_resist0.5
        b = Enemy("bucket", 1, self.ed["bucket"], 5.0)
        sim.enemies.append(b)
        sim._apply_control(b, {"slow": {"factor": 0.5, "duration": 2.5}, "knockback_cells": 0.3})
        self.assertEqual(b.slow_mult, 0.75)
        self.assertAlmostEqual(b.x, 5.15, places=4)
        g = Enemy("giant", 2, self.ed["giant"], 5.0)
        sim.enemies.append(g)
        sim._apply_control(g, {"knockback_cells": 0.3})
        self.assertEqual(g.x, 5.0)                                          # 免控巨人不动

    def test_determinism_same_seed(self):
        pool = ["sunbloom", "peashooter", "repeater", "wallnut", "bombberry"]
        sched = build_schedule(self.ed, 4, seed=7)

        def run(seed):
            return Simulation(self.pd, self.ed, sched, pool, seed=seed).run_to_end(RuleBot(pool))
        self.assertEqual(run(7), run(7))
        self.assertNotEqual(run(7), run(8))

    def test_win_when_all_cleared(self):
        sched = fixed_schedule([(5.0, "normal")], rows=[0])
        pool = ["sunbloom", "peashooter", "wallnut"]
        sim = Simulation(self.pd, self.ed, sched, pool, seed=1, max_seconds=120)
        m = sim.run_to_end(RuleBot(pool))
        self.assertTrue(m["won"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
