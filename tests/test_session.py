# -*- coding: utf-8 -*-
"""交互会话（PlaySession）测试：点选 / 种植 / 铲种 / 冷却 / 胜负。

交互逻辑全部在 Python 里，所以这些都能 headless 跑，不需要 pygame 或 Godot。
"""
from __future__ import annotations

import unittest

from tdgame import config as C
from tdgame.engine.loader import load_registry
from tdgame.engine.session import SHOVEL, PlaySession

DATA = __import__("pathlib").Path(__file__).resolve().parents[1] / "tdgame" / "data"
REG = load_registry(DATA)


def make_level(**over) -> dict:
    lv = {
        "key": "test_level",
        "phase": "M1",
        "start_resource": 500,
        "max_seconds": 60.0,
        "card_pool": ["peashooter", "sunbloom", "wallnut"],
        "spawn": {"mode": "fixed", "entries": [[1.0, "normal"]], "rows": [0]},
        "reward": {"design_tokens": 0, "unlock": []},
    }
    lv.update(over)
    return lv


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.s = PlaySession(make_level(), REG, seed=1000)

    def test_select_valid_and_unknown(self):
        self.s.select("peashooter")
        self.assertEqual(self.s.selected, "peashooter")
        self.s.select("boss_50")          # 不在卡池
        self.assertEqual(self.s.selected, "peashooter")

    def test_shovel_toggle(self):
        self.s.toggle_shovel()
        self.assertEqual(self.s.selected, SHOVEL)
        self.s.toggle_shovel()
        self.assertIsNone(self.s.selected)

    def test_click_without_selection_does_nothing(self):
        ok, reason = self.s.click_cell(0, 0)
        self.assertFalse(ok)
        self.assertEqual(reason, "no_selection")
        self.assertEqual(len(self.s.sim.plants), 0)


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self.s = PlaySession(make_level(), REG, seed=1000)

    def test_place_ok_and_deselects(self):
        self.s.select("peashooter")
        ok, reason = self.s.place(0, 0)
        self.assertTrue(ok, reason)
        self.assertEqual(len(self.s.sim.plants), 1)
        self.assertIsNone(self.s.selected, "种下后应自动取消选择")

    def test_occupied(self):
        self.s.select("peashooter")
        self.s.place(0, 0)
        self.s.select("peashooter")
        ok, reason = self.s.place(0, 0)
        self.assertFalse(ok)
        self.assertEqual(reason, "occupied")

    def test_recharging_blocks_second_placement(self):
        self.s.select("peashooter")
        self.s.place(0, 0)
        self.s.select("peashooter")
        ok, reason = self.s.place(0, 1)
        self.assertFalse(ok)
        self.assertEqual(reason, "recharging")

    def test_no_sun(self):
        s = PlaySession(make_level(start_resource=0), REG, seed=1000)
        s.select("peashooter")
        ok, reason = s.place(0, 0)
        self.assertFalse(ok)
        self.assertEqual(reason, "no_sun")

    def test_out_of_board(self):
        self.s.select("peashooter")
        ok, reason = self.s.place(C.ROWS, 0)
        self.assertFalse(ok)
        self.assertEqual(reason, "out_of_board")

    def test_place_deducts_sun(self):
        before = self.s.sun
        self.s.select("peashooter")
        self.s.place(0, 0)
        self.assertEqual(self.s.sun, before - 100)


class ShovelTests(unittest.TestCase):
    def setUp(self):
        self.s = PlaySession(make_level(), REG, seed=1000)

    def test_shovel_removes_and_frees_cell(self):
        self.s.select("peashooter")
        self.s.place(2, 3)
        before_sun = self.s.sun
        ok, reason = self.s.shovel(2, 3)
        self.assertTrue(ok, reason)
        self.assertEqual(len(self.s.sim.plants), 0)
        self.assertEqual(self.s.sun, before_sun, "铲种不返还阳光")
        # 格子空出来后能重新种——但要先等卡片冷却结束（recharge 5s）
        self.s.tick(6.0)
        self.s.select("peashooter")
        ok2, reason2 = self.s.place(2, 3)
        self.assertTrue(ok2, reason2)

    def test_shovel_empty_cell(self):
        ok, reason = self.s.shovel(0, 0)
        self.assertFalse(ok)
        self.assertEqual(reason, "empty")

    def test_shovel_via_click_with_shovel_selected(self):
        self.s.select("wallnut")
        self.s.place(1, 1)
        self.s.toggle_shovel()
        ok, _ = self.s.click_cell(1, 1)
        self.assertTrue(ok)
        self.assertEqual(len(self.s.sim.plants), 0)

    def test_shovel_clears_enemy_eating_reference(self):
        """敌人正在啃的植物被铲掉后，eating 必须置空，不能指向已死对象。"""
        self.s.select("wallnut")
        self.s.place(0, 8)
        # 推进到敌人贴上来啃
        for _ in range(1200):
            self.s.tick(0.1)
            if any(e.eating is not None for e in self.s.sim.enemies):
                break
        eating = [e for e in self.s.sim.enemies if e.eating is not None]
        self.assertTrue(eating, "预期有敌人正在啃食")
        target = eating[0].eating
        self.s.shovel(0, 8)
        for e in self.s.sim.enemies:
            self.assertIsNot(e.eating, target, "eating 不能指向已铲除的植物")


class TimeTests(unittest.TestCase):
    def test_tick_advances_time_in_dt_steps(self):
        s = PlaySession(make_level(), REG, seed=1000)
        s.tick(1.0)
        self.assertAlmostEqual(s.sim.now, 1.0, places=6)
        s.tick(0.05)          # 不足一个 DT，暂不推进
        self.assertAlmostEqual(s.sim.now, 1.0, places=6)
        s.tick(0.05)
        self.assertAlmostEqual(s.sim.now, 1.1, places=6)

    def test_no_progress_after_game_over(self):
        s = PlaySession(make_level(spawn={"mode": "fixed", "entries": [], "rows": []}), REG)
        s.tick(1.0)
        self.assertTrue(s.over)
        t = s.sim.now
        s.tick(5.0)
        self.assertEqual(s.sim.now, t)


class OutcomeTests(unittest.TestCase):
    def test_empty_spawn_wins_immediately(self):
        s = PlaySession(make_level(spawn={"mode": "fixed", "entries": [], "rows": []}), REG)
        s.tick(0.5)
        self.assertTrue(s.over)
        self.assertTrue(s.won)

    def test_losing_all_lives_loses(self):
        # 同一时刻刷一堆僵尸会被一枚小车一次全灭（这是正确机制），所以要**错峰**刷：
        # 首只触发本行小车，之后每只单独破线各扣 1 命，5 命扣光即负。
        lv = make_level(
            start_resource=0,
            card_pool=["peashooter"],
            max_seconds=600.0,
            spawn={"mode": "fixed",
                   "entries": [[1.0 + i * 10.0, "fast"] for i in range(10)],
                   "rows": [0] * 10},
        )
        s = PlaySession(lv, REG, seed=1000)
        for _ in range(12000):
            s.tick(0.1)
            if s.over:
                break
        self.assertTrue(s.over)
        self.assertFalse(s.won, "生命耗尽应判负")
        self.assertLessEqual(s.lives, 0)

    def test_placing_after_over_is_rejected(self):
        s = PlaySession(make_level(spawn={"mode": "fixed", "entries": [], "rows": []}), REG)
        s.tick(0.5)
        self.assertTrue(s.over)
        s.select("peashooter")
        ok, reason = s.place(0, 0)
        self.assertFalse(ok)
        self.assertEqual(reason, "over")


class CardsTests(unittest.TestCase):
    def test_card_status_fields(self):
        s = PlaySession(make_level(), REG, seed=1000)
        cards = s.cards()
        self.assertEqual(len(cards), 3)
        first = cards[0]
        for field in ("key", "sun", "cd", "cd_max", "affordable", "ready", "selected"):
            self.assertIn(field, first)
        self.assertTrue(first["affordable"])
        self.assertTrue(first["ready"])

    def test_selected_flag_follows_selection(self):
        s = PlaySession(make_level(), REG, seed=1000)
        s.select("sunbloom")
        selected = [c["key"] for c in s.cards() if c["selected"]]
        self.assertEqual(selected, ["sunbloom"])

    def test_cooldown_counts_down(self):
        s = PlaySession(make_level(), REG, seed=1000)
        s.select("peashooter")
        s.place(0, 0)
        cd_before = [c for c in s.cards() if c["key"] == "peashooter"][0]["cd"]
        self.assertGreater(cd_before, 0)
        s.tick(1.0)
        cd_after = [c for c in s.cards() if c["key"] == "peashooter"][0]["cd"]
        self.assertLess(cd_after, cd_before)


class EntitiesTests(unittest.TestCase):
    def test_entities_shape(self):
        s = PlaySession(make_level(), REG, seed=1000)
        s.select("peashooter")
        s.place(0, 2)
        s.tick(0.5)
        e = s.entities()
        self.assertEqual(len(e["plants"]), 1)
        self.assertEqual(e["plants"][0]["row"], 0)
        self.assertEqual(e["plants"][0]["col"], 2)
        self.assertIsInstance(e["enemies"], list)
        self.assertIsInstance(e["projectiles"], list)


if __name__ == "__main__":
    unittest.main()
