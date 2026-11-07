# -*- coding: utf-8 -*-
"""抛射僵尸与亵渎光环的行为测试。"""
from __future__ import annotations

import unittest
from pathlib import Path

from tdgame import config as C
from tdgame.engine.board import Simulation
from tdgame.engine.loader import load_registry

ROOT = Path(__file__).resolve().parents[1]
REG = load_registry(ROOT / "tdgame" / "data")
SCHED = [(999.0, "normal", 0)]


def make_sim(pool):
    return Simulation(REG.plants, REG.enemies, SCHED, pool, seed=3,
                      start_resource=3000, max_seconds=600, sky_sun=False)


class LobberTests(unittest.TestCase):
    def test_lobber_hits_back_row_not_front(self):
        sim = make_sim(["wallnut", "sunbloom"])
        sim.place_plant("wallnut", 2, 7)     # 前排（靠右）
        sim.place_plant("sunbloom", 2, 2)    # 后排（靠左）
        front = sim.plant_at(2, 7)
        back = sim.plant_at(2, 2)
        f0, b0 = front.hp, back.hp
        e = sim.spawn_enemy("lobber", 2, x=9.0)
        for _ in range(int(6.0 / C.DT)):
            sim.step(C.DT)
        self.assertEqual(front.hp, f0, "抛射不应伤到前排")
        self.assertLess(back.hp, b0, "抛射应打中该行最靠后的植物")

    def test_lobber_stops_at_distance(self):
        sim = make_sim(["wallnut"])
        sim.place_plant("wallnut", 1, 4)
        e = sim.spawn_enemy("lobber", 1, x=9.0)
        for _ in range(int(8.0 / C.DT)):
            sim.step(C.DT)
        # 与前排（col=4，中心 4.5）保持约 3 格
        self.assertLessEqual(e.x, 9.0, "抛射僵尸应当向前移动")
        self.assertGreaterEqual(e.x - 4.5, 2.5, "不应贴到前排")


class DesecratorTests(unittest.TestCase):
    def test_aura_drains_every_plant(self):
        sim = make_sim(["wallnut", "sunbloom"])
        a = sim.plant_at
        sim.place_plant("wallnut", 0, 3)
        sim.place_plant("sunbloom", 4, 3)
        p1, p2 = sim.plant_at(0, 3), sim.plant_at(4, 3)
        h1, h2 = p1.hp, p2.hp
        sim.spawn_enemy("desecrator", 2, x=9.0)
        for _ in range(int(2.0 / C.DT)):
            sim.step(C.DT)
        self.assertLess(p1.hp, h1, "全屏植物都应被削血")
        self.assertLess(p2.hp, h2, "不同行也应被削血")

    def test_aura_never_kills(self):
        sim = make_sim(["wallnut"])
        sim.place_plant("wallnut", 0, 3)
        p = sim.plant_at(0, 3)
        sim.spawn_enemy("desecrator", 2, x=9.0)
        for _ in range(int(30.0 / C.DT)):
            sim.step(C.DT)
        self.assertGreaterEqual(p.hp, 1.0, "光环有 1 HP 保底，不能直接杀死植物")


if __name__ == "__main__":
    unittest.main()
