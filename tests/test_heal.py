# -*- coding: utf-8 -*-
"""治疗机制测试：周围植物回血、范围限制、满血不浪费。"""
from __future__ import annotations

import unittest
from pathlib import Path

from tdgame import config as C
from tdgame.engine.board import Simulation
from tdgame.engine.loader import load_registry

ROOT = Path(__file__).resolve().parents[1]
REG = load_registry(ROOT / "tdgame" / "data")
SCHED = [(999.0, "normal", 0)]


def make_sim():
    return Simulation(REG.plants, REG.enemies, SCHED,
                      ["wallnut", "heal_bloom"], seed=5,
                      start_resource=2000, max_seconds=600, sky_sun=False)


class HealTests(unittest.TestCase):
    def test_heals_damaged_neighbor(self):
        sim = make_sim()
        sim.place_plant("wallnut", 2, 3)
        sim.place_plant("heal_bloom", 2, 4)
        target = sim.plant_at(2, 3)
        target.hp -= 150
        before = target.hp
        for _ in range(int(3.0 / C.DT)):
            sim.step(C.DT)
        self.assertGreater(target.hp, before, "周围受伤植物应被治疗")

    def test_does_not_heal_out_of_range(self):
        sim = make_sim()
        sim.place_plant("wallnut", 0, 0)
        sim.place_plant("heal_bloom", 4, 8)
        target = sim.plant_at(0, 0)
        target.hp -= 150
        before = target.hp
        for _ in range(int(3.0 / C.DT)):
            sim.step(C.DT)
        self.assertEqual(target.hp, before, "超出 3x3 范围不该被治疗")

    def test_does_not_overflow(self):
        sim = make_sim()
        sim.place_plant("wallnut", 2, 3)
        sim.place_plant("heal_bloom", 2, 4)
        target = sim.plant_at(2, 3)
        target.hp -= 10
        for _ in range(int(5.0 / C.DT)):
            sim.step(C.DT)
        self.assertLessEqual(target.hp, target.hp_max, "治疗不应超过上限")

    def test_heal_event_logged(self):
        sim = make_sim()
        sim.place_plant("wallnut", 2, 3)
        sim.place_plant("heal_bloom", 2, 4)
        sim.plant_at(2, 3).hp -= 100
        for _ in range(int(2.0 / C.DT)):
            sim.step(C.DT)
        self.assertTrue(any("heal" in ln for ln in sim.event_log))


if __name__ == "__main__":
    unittest.main()
