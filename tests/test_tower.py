# -*- coding: utf-8 -*-
"""爬塔测试：层数缩放、Boss 层、进度推进、与存档的衔接。"""
from __future__ import annotations

import collections
import unittest
from pathlib import Path

from tdgame.engine.loader import load_registry
from tdgame.headless_run import POOL_BASIC, POOL_LATE
from tdgame.scenarios.progression import PlayerProgress
from tdgame.scenarios.savegame import FORMAT, restore, snapshot
from tdgame.scenarios.tower import (
    BOSS_KEY,
    DEFAULT_FLOORS,
    TowerRun,
    floor_schedule,
    is_boss_floor,
    run_tower,
)

ROOT = Path(__file__).resolve().parents[1]
REG = load_registry(ROOT / "tdgame" / "data")


class FloorScheduleTests(unittest.TestCase):
    def test_floor_must_start_at_one(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                floor_schedule(REG, bad, 1000, POOL_BASIC)

    def test_boss_floor_every_ten(self):
        self.assertFalse(is_boss_floor(9))
        self.assertTrue(is_boss_floor(10))
        self.assertTrue(is_boss_floor(20))
        self.assertFalse(is_boss_floor(11))

    def test_boss_floor_contains_boss_enemy(self):
        sched = floor_schedule(REG, 10, 1000, POOL_LATE)
        keys = [k for _, k, _ in sched]
        self.assertIn(BOSS_KEY, keys, "Boss 层应出现攻坚单位")
        self.assertNotIn("boss_50", keys,
                         "D-11 未修前不放 boss_50（当前卡池打不死）")

    def test_boss_floor_scales_with_floor(self):
        low = len(floor_schedule(REG, 10, 1000, POOL_LATE))
        high = len(floor_schedule(REG, 30, 1000, POOL_LATE))
        self.assertGreater(high, low, "层数越高 Boss 层护卫越厚")

    def test_normal_floors_scale_up(self):
        """普通层的波数应随层号单调不减。"""
        counts = []
        for floor in (1, 5, 9, 13, 17):
            if is_boss_floor(floor):
                continue
            counts.append(len(floor_schedule(REG, floor, 1000, POOL_LATE)))
        self.assertEqual(counts, sorted(counts), f"波数应单调不减，实际 {counts}")

    def test_schedule_is_deterministic(self):
        a = floor_schedule(REG, 7, 1234, POOL_LATE)
        b = floor_schedule(REG, 7, 1234, POOL_LATE)
        self.assertEqual(a, b)


class TowerRunTests(unittest.TestCase):
    def test_starts_at_requested_floor(self):
        run = TowerRun(REG, POOL_LATE, start_floor=5)
        self.assertEqual(run.floor, 5)
        self.assertEqual(run.best_floor, 5)

    def test_start_floor_clamped_to_one(self):
        run = TowerRun(REG, POOL_LATE, start_floor=0)
        self.assertEqual(run.floor, 1)

    def test_winning_advances_floor(self):
        run = TowerRun(REG, POOL_LATE, seed=1000)
        rec = run.run_floor()
        self.assertTrue(rec["won"], "第 1 层应当能过")
        self.assertEqual(run.floor, 2)
        self.assertGreaterEqual(run.best_floor, 2)

    def test_history_records_each_attempt(self):
        run = TowerRun(REG, POOL_LATE, seed=1000)
        run.run_floor()
        run.run_floor()
        self.assertEqual(len(run.history), 2)
        self.assertEqual([h["floor"] for h in run.history], [1, 2])

    def test_climb_stops_on_loss(self):
        run = TowerRun(REG, POOL_BASIC, seed=1000, floors=DEFAULT_FLOORS)
        st = run.climb()
        self.assertGreater(st["cleared"], 0, "至少能爬过几层")
        self.assertLessEqual(st["floor"], DEFAULT_FLOORS + 1)
        self.assertEqual(st["cleared"] + (0 if st["reached_top"] else 1),
                         len(run.history))

    def test_status_shape(self):
        st = TowerRun(REG, POOL_LATE).status()
        for k in ("floor", "best_floor", "floors", "cleared", "attempts", "reached_top"):
            self.assertIn(k, st)


class TowerDifficultyTests(unittest.TestCase):
    def test_tower_has_a_curve_not_a_wall(self):
        """爬塔不该开局即死，也不该轻松登顶 —— 中间要有个合理的墙。"""
        results = [run_tower(REG, POOL_LATE, seed=s, floors=20) for s in range(1000, 1003)]
        best = [r["best_floor"] for r in results]
        self.assertTrue(all(b >= 5 for b in best), f"不该在前 5 层就死：{best}")
        self.assertTrue(any(b < 20 for b in best), f"不该全部轻松登顶：{best}")

    def test_boss_floors_are_harder_than_neighbours(self):
        """Boss 层的通关率不应高于相邻普通层（否则 Boss 层没意义）。"""
        def winrate(floor):
            import copy
            from tdgame.engine.board import Simulation
            from tdgame.engine.bot import RuleBot

            wins = 0
            for seed in range(1000, 1004):
                sched = floor_schedule(REG, floor, seed, POOL_LATE)
                sim = Simulation(REG.plants, REG.enemies, sched, POOL_LATE,
                                 seed=seed, start_resource=100, max_seconds=320)
                wins += 1 if sim.run_to_end(RuleBot(POOL_LATE, smart=True))["won"] else 0
            return wins / 4

        boss = winrate(10)
        normal = winrate(9)
        self.assertLessEqual(boss, normal, f"Boss 层({boss}) 不该比普通层({normal}) 更容易")


class SaveIntegrationTests(unittest.TestCase):
    def test_tower_floor_round_trips(self):
        p = PlayerProgress()
        p.tower_floor = 7
        data = snapshot(p)
        self.assertEqual(data["tower_floor"], 7)
        q, _ = restore(data)
        self.assertEqual(q.tower_floor, 7)

    def test_negative_floor_clamped(self):
        q, _ = restore({"format": FORMAT, "cleared": [], "design_tokens": 0,
                        "tower_floor": -3})
        self.assertEqual(q.tower_floor, 0)

    def test_bogus_floor_ignored(self):
        q, warn = restore({"format": FORMAT, "cleared": [], "design_tokens": 0,
                           "tower_floor": "9"})
        self.assertEqual(q.tower_floor, 0)
        self.assertIsNotNone(warn)

    def test_old_save_without_tower_field_still_loads(self):
        q, warn = restore({"format": FORMAT, "cleared": ["m1_01"], "design_tokens": 3})
        self.assertIsNone(warn, "缺字段的老存档应正常读取")
        self.assertEqual(q.tower_floor, 0)
        self.assertEqual(q.cleared, ["m1_01"])


if __name__ == "__main__":
    unittest.main()
