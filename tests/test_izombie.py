# -*- coding: utf-8 -*-
"""M5「我是僵尸」测试：模式反转、预算、投放规则、胜负判定。"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from tdgame import config as C
from tdgame.engine.loader import load_registry
from tdgame.scenarios.i_zombie import (
    MODE,
    ZombieBot,
    ZombieSession,
    enemy_cost,
    run_level,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tdgame" / "data"
REG = load_registry(DATA)


def load_level(key: str) -> dict:
    return json.loads((DATA / "izombie" / f"{key}.json").read_text(encoding="utf-8"))


class SessionSetupTests(unittest.TestCase):
    def test_plants_are_preset(self):
        lv = load_level("zombie_01")
        s = ZombieSession(lv, REG, seed=1000)
        self.assertEqual(len(s.sim.plants), len(lv["plants"]))
        self.assertEqual(s.budget, lv["budget"])
        self.assertEqual(s.sim.objective, "devour")

    def test_player_cannot_plant_in_devour_mode(self):
        s = ZombieSession(load_level("zombie_01"), REG, seed=1000)
        ok, why = s.sim.can_place("peashooter", 0, 0)
        self.assertFalse(ok)
        self.assertEqual(why, "devour_mode")
        self.assertFalse(s.sim.place_plant("peashooter", 0, 0))

    def test_setup_plant_bypasses_cost_and_pool(self):
        s = ZombieSession({"key": "t", "budget": 0, "allowed": [], "plants": []},
                          REG, seed=1)
        self.assertEqual(s.sim.sun, 0)
        self.assertTrue(s.sim.setup_plant("winter_melon", 0, 0),
                        "预置植物不受阳光/卡池限制")
        self.assertFalse(s.sim.setup_plant("winter_melon", 0, 0), "同一格不能重复")


class PlacementTests(unittest.TestCase):
    def test_cost_comes_from_enemy_budget_field(self):
        self.assertEqual(enemy_cost(REG, "normal"), 1)
        self.assertEqual(enemy_cost(REG, "bucket"), 4)
        self.assertEqual(enemy_cost(REG, "giant"), 8)

    def test_place_deducts_budget_and_spawns(self):
        s = ZombieSession(load_level("zombie_01"), REG, seed=1000)
        before = s.budget
        self.assertTrue(s.place_zombie("normal", 0))
        self.assertEqual(s.budget, before - 1)
        self.assertEqual(len(s.sim.enemies), 1)
        self.assertEqual(s.spawned, 1)
        self.assertEqual(s.placements[0][1], "normal")

    def test_rejects_disallowed_and_expensive(self):
        s = ZombieSession(load_level("zombie_01"), REG, seed=1000)
        ok, why = s.can_place("giant", 0)
        self.assertFalse(ok)
        self.assertEqual(why, "not_allowed")
        s.budget = 1
        ok, why = s.can_place("cone", 0)      # cone 要 2
        self.assertFalse(ok)
        self.assertEqual(why, "no_budget")

    def test_rejects_out_of_board(self):
        s = ZombieSession(load_level("zombie_01"), REG, seed=1000)
        self.assertEqual(s.can_place("normal", C.ROWS), (False, "out_of_board"))
        self.assertEqual(s.can_place("normal", -1), (False, "out_of_board"))

    def test_cards_expose_budget_price(self):
        s = ZombieSession(load_level("zombie_01"), REG, seed=1000)
        cards = s.cards()
        self.assertEqual([c["key"] for c in cards], load_level("zombie_01")["allowed"])
        for c in cards:
            self.assertEqual(c["sun"], s.cost(c["key"]))
            self.assertEqual(c["kind"], "enemy")


class EndConditionsTests(unittest.TestCase):
    def test_win_when_all_plants_eaten(self):
        lv = {"key": "tiny", "budget": 40, "max_sec": 90,
              "allowed": ["bucket"], "plants": [[0, 2, "peashooter"]]}
        s = ZombieSession(lv, REG, seed=1000)
        bot = ZombieBot(0.6)
        for _ in range(2000):
            bot.think(s)
            s.tick(C.DT)
            if s.sim.over:
                break
        self.assertTrue(s.sim.over)
        self.assertTrue(s.sim.won, "啃光植物应判胜")
        self.assertEqual(s.plants_left(), 0)

    def test_timeout_is_loss(self):
        # 只给买不起任何僵尸的预算 -> 植物永远吃不完 -> 超时判负
        lv = {"key": "stall", "budget": 0, "max_sec": 5,
              "allowed": ["normal"], "plants": [[0, 2, "wallnut"]]}
        s = ZombieSession(lv, REG, seed=1000)
        for _ in range(200):
            s.tick(C.DT)
            if s.sim.over:
                break
        self.assertTrue(s.sim.over)
        self.assertFalse(s.sim.won)
        self.assertEqual(s.plants_left(), 1)

    def test_empty_defense_wins_immediately(self):
        lv = {"key": "empty", "budget": 0, "max_sec": 30,
              "allowed": [], "plants": []}
        s = ZombieSession(lv, REG, seed=1)
        s.tick(C.DT)
        self.assertTrue(s.sim.over and s.sim.won)


class LevelsTests(unittest.TestCase):
    def test_every_level_is_winnable(self):
        """设计红线：每个关卡都必须存在可打通的解法。"""
        for key in ("zombie_01", "zombie_02", "zombie_03"):
            lv = load_level(key)
            wins = sum(1 for seed in range(1000, 1003)
                       if run_level(lv, REG, seed=seed)["won"])
            self.assertGreaterEqual(wins, 2, f"{key} 应该能被稳定打通（实际 {wins}/3）")

    def test_levels_shrink_budget_is_not_free(self):
        """预算砍半后不该还能随便过 —— 说明预算确实是约束。"""
        lv = load_level("zombie_02")
        lv = dict(lv, budget=max(1, lv["budget"] // 3))
        wins = sum(1 for seed in range(1000, 1003)
                   if run_level(lv, REG, seed=seed)["won"])
        self.assertLess(wins, 3, "预算砍到 1/3 后不应仍然全胜")

    def test_status_shape(self):
        s = ZombieSession(load_level("zombie_01"), REG, seed=1000)
        st = s.status()
        for k in ("key", "mode", "budget", "plants_left", "zombies_alive",
                  "over", "won", "time_left"):
            self.assertIn(k, st)
        self.assertEqual(st["mode"], MODE)


if __name__ == "__main__":
    unittest.main()
