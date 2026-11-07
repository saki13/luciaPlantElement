# -*- coding: utf-8 -*-
"""首车救援机制测试：第一次掉车不判负，改为清场 + 每行补种冰西瓜。"""
from __future__ import annotations

import unittest
from pathlib import Path

from tdgame import config as C
from tdgame.engine.board import Simulation
from tdgame.engine.loader import load_registry

ROOT = Path(__file__).resolve().parents[1]
REG = load_registry(ROOT / "tdgame" / "data")

# 留一只远期敌人，避免"波次跑完 + 场上无敌人"被判定为通关
LONG_SCHEDULE = [(999.0, "normal", 0)]


def make_sim():
    return Simulation(REG.plants, REG.enemies, LONG_SCHEDULE, ["sunbloom"],
                      seed=7, start_resource=50, max_seconds=600,
                      sky_sun=False, rescue=True)


class RescueTests(unittest.TestCase):
    def test_first_breach_is_not_a_defeat(self):
        sim = make_sim()
        sim.spawn_enemy("normal", 2, x=C.LAWN_MOWER_TRIGGER_X - 0.1)
        sim.step(C.DT)
        self.assertFalse(sim.over, "首车不应结束对局")
        self.assertEqual(sim.mowers_used, 1)
        self.assertEqual(sim.rescues, 1, "首车应触发救援")

    def test_rescue_clears_zombies_and_plants_melons(self):
        sim = make_sim()
        for row in range(C.ROWS):
            sim.spawn_enemy("normal", row, x=C.LAWN_MOWER_TRIGGER_X - 0.1)
        sim.step(C.DT)
        self.assertEqual(sim.rescues, 1)
        self.assertEqual(len(sim.enemies), 0, "救援应清空场上僵尸")
        melons = [p for p in sim.plants if p.key == "winter_melon"]
        self.assertEqual(len(melons), C.ROWS, "每行应补种一株冰西瓜")

    def test_second_breach_does_not_rescue_again(self):
        sim = make_sim()
        sim.spawn_enemy("normal", 0, x=C.LAWN_MOWER_TRIGGER_X - 0.1)
        sim.step(C.DT)
        self.assertEqual(sim.rescues, 1)
        sim.spawn_enemy("normal", 1, x=C.LAWN_MOWER_TRIGGER_X - 0.1)
        sim.step(C.DT)
        self.assertEqual(sim.rescues, 1, "救援只触发一次")

    def test_rescue_is_reported(self):
        sim = make_sim()
        sim.spawn_enemy("normal", 3, x=C.LAWN_MOWER_TRIGGER_X - 0.1)
        sim.step(C.DT)
        self.assertEqual(sim.rescues, 1)
        self.assertTrue(any("rescue" in line for line in sim.event_log),
                        "救援应写进事件日志")


if __name__ == "__main__":
    unittest.main()
