# -*- coding: utf-8 -*-
"""新机制测试：护甲壳（南瓜）/ 反弹光环（荆棘）/ 竹笋强化 / 荆棘女王奖励。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tdgame import config as C
from tdgame.engine.board import Simulation
from tdgame.engine.loader import load_registry
from tdgame.scenarios.progression import PlayerProgress
from tdgame.scenarios.savegame import load_from, save_to

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tdgame" / "data"
REG = load_registry(DATA)


def make_sim(pool=(), start=1000):
    sim = Simulation(REG.plants, REG.enemies, [], list(pool), seed=1000,
                     start_resource=start, max_seconds=600, sky_sun=False)
    return sim


class ShellTests(unittest.TestCase):
    def test_pumpkin_can_shell_an_occupied_cell(self):
        sim = make_sim(["wallnut", "iron_pumpkin"])
        self.assertTrue(sim.place_plant("wallnut", 0, 2))
        ok, why = sim.can_place("iron_pumpkin", 0, 2)
        self.assertTrue(ok, f"护甲壳应可套在已有植物上，实际 {why}")
        self.assertTrue(sim.place_plant("iron_pumpkin", 0, 2))
        host = sim.plant_at(0, 2)
        self.assertGreater(host.shell_hp, 0, "宿主应当获得壳血量")
        self.assertEqual(host.shell_key, "iron_pumpkin")

    def test_cannot_double_shell(self):
        # 同一格已经套了壳，就不能再套第二层（不是冷却问题，直接判 occupied）
        sim = make_sim(["wallnut", "iron_pumpkin"], start=3000)
        sim.place_plant("wallnut", 0, 2)
        sim.place_plant("iron_pumpkin", 0, 2)
        ok2, why2 = sim.can_place("iron_pumpkin", 0, 2)
        self.assertFalse(ok2, "同一格不能再套第二层壳")
        self.assertEqual(why2, "occupied")

    def test_shell_absorbs_before_body(self):
        sim = make_sim(["wallnut", "iron_pumpkin"])
        sim.place_plant("wallnut", 0, 2)
        sim.place_plant("iron_pumpkin", 0, 2)
        host = sim.plant_at(0, 2)
        body_before = host.hp
        shell_before = host.shell_hp
        sim._damage_plant(host, 100.0)
        self.assertLess(host.shell_hp, shell_before)
        self.assertEqual(host.hp, body_before, "壳没破之前不该扣本体")

    def test_shell_break_then_body(self):
        sim = make_sim(["wallnut", "iron_pumpkin"])
        sim.place_plant("wallnut", 0, 2)
        sim.place_plant("iron_pumpkin", 0, 2)
        host = sim.plant_at(0, 2)
        sim._damage_plant(host, host.shell_hp + 50)
        self.assertEqual(host.shell_hp, 0.0)
        self.assertEqual(host.hp, host.hp_max - 50, "溢出部分应打到本体")


class ReflectionTests(unittest.TestCase):
    def test_biting_near_aura_hurts_the_biter(self):
        sim = make_sim(["wallnut", "thorn_aura"])
        sim.place_plant("wallnut", 2, 3)
        sim.place_plant("thorn_aura", 2, 2)          # 同排相邻 -> 在 3x3 内
        e = sim.spawn_enemy("normal", 2, x=4.0)
        hp_before = e.hp_body
        for _ in range(5):
            sim.step(C.DT)
        self.assertLess(e.hp_body, hp_before, "啃食者应被荆棘反弹扣血")

    def test_aura_out_of_range_does_nothing(self):
        sim = make_sim(["wallnut", "thorn_aura"])
        sim.place_plant("wallnut", 2, 6)
        sim.place_plant("thorn_aura", 2, 1)          # 列差 5 > radius
        e = sim.spawn_enemy("normal", 2, x=7.0)
        hp_before = e.hp_body
        for _ in range(5):
            sim.step(C.DT)
        self.assertEqual(e.hp_body, hp_before, "超出范围的啃食不该被反弹")

    def test_thorn_queen_reflects_harder_than_aura(self):
        aura = REG.plants["thorn_aura"]["reflection"]["ratio"]
        queen = REG.plants["thorn_queen"]["reflection"]["ratio"]
        self.assertGreater(queen, aura)


class BambooTests(unittest.TestCase):
    def test_bamboo_is_tankier(self):
        hp = REG.plants["bamboo"]["hp"]
        self.assertGreaterEqual(hp, 500, "竹笋应当有坦度（用户要求）")

    def test_bamboo_has_heavy_splash(self):
        c = REG.plants["bamboo"]["combat"]
        self.assertIn("ability", c, "应当有重劈能力（近战群伤）")
        self.assertGreater(c["ability"]["damage"], c["damage"])


class ThornQueenRewardTests(unittest.TestCase):
    def test_first_boss_clear_unlocks_thorn_queen(self):
        p = PlayerProgress()
        got = p.record_boss_clear("boss_50")
        self.assertEqual(got, "thorn_queen")
        self.assertIn("thorn_queen", p.unlocked_plants)

    def test_repeat_clear_is_noop(self):
        p = PlayerProgress()
        p.record_boss_clear("boss_50")
        self.assertIsNone(p.record_boss_clear("boss_50"))
        self.assertEqual(p.unlocked_plants.count("thorn_queen"), 1)

    def test_boss_clears_persist(self):
        p = PlayerProgress()
        p.record_boss_clear("boss_50")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            save_to(path, p)
            q, warn = load_from(path)
            self.assertIsNone(warn)
            self.assertEqual(q.boss_clears, ["boss_50"])
            self.assertIn("thorn_queen", q.unlocked_plants)


if __name__ == "__main__":
    unittest.main()
