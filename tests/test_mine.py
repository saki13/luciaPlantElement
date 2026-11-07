# -*- coding: utf-8 -*-
"""地雷机制：埋雷(arm) -> 待命 -> 敌人接近触发 -> 一次性爆炸。"""
from __future__ import annotations

import unittest
from pathlib import Path

from tdgame import config as C
from tdgame.engine.board import Simulation
from tdgame.engine.loader import load_registry

ROOT = Path(__file__).resolve().parents[1]
REG = load_registry(ROOT / "tdgame" / "data")
LONG_SCHEDULE = [(999.0, "normal", 0)]


def make_sim(sun=1000):
    return Simulation(REG.plants, REG.enemies, LONG_SCHEDULE,
                      ["potato_mine"], seed=11, start_resource=sun,
                      max_seconds=600, sky_sun=False)


class MineTests(unittest.TestCase):
    def test_mine_needs_arming_time(self):
        sim = make_sim()
        self.assertTrue(sim.place_plant("potato_mine", 2, 4))
        p = sim.plant_at(2, 4)
        self.assertIsNotNone(p.arm_timer, "刚种下应处于埋雷中")
        sim.step(C.DT)
        self.assertFalse(p.armed, "埋雷期间不应待命")

    def test_mine_arms_after_delay(self):
        sim = make_sim()
        sim.place_plant("potato_mine", 2, 4)
        p = sim.plant_at(2, 4)
        for _ in range(int(4.2 / C.DT)):
            sim.step(C.DT)
        self.assertTrue(p.armed, "4s 后应埋好待命")
        self.assertTrue(p.alive, "没有敌人时不应引爆")

    def test_mine_explodes_on_contact(self):
        sim = make_sim()
        sim.place_plant("potato_mine", 2, 4)
        p = sim.plant_at(2, 4)
        for _ in range(int(4.2 / C.DT)):
            sim.step(C.DT)
        e = sim.spawn_enemy("normal", 2, x=4.5)
        hp0 = e.hp_body
        sim.step(C.DT)
        self.assertFalse(p.alive, "踩到后地雷应炸掉")
        self.assertLess(e.hp_body, hp0, "敌人应受到爆炸伤害")

    def test_mine_does_not_trigger_before_armed(self):
        sim = make_sim()
        sim.place_plant("potato_mine", 2, 4)
        e = sim.spawn_enemy("normal", 2, x=4.5)
        hp0 = e.hp_body
        sim.step(C.DT)
        self.assertEqual(e.hp_body, hp0, "埋雷未完成时不该爆炸")


if __name__ == "__main__":
    unittest.main()
