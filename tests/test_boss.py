# -*- coding: utf-8 -*-
"""Boss 机制（M3）：召唤与多阶段。

数据侧 `boss_50.json` 早就写了 `summon` / `phase` 字段，但引擎从来不读——
之前 Boss 只是"高威胁精英"。这两个测试把新实现钉住。
"""
from __future__ import annotations

import unittest
from pathlib import Path

from tdgame.engine.board import Simulation
from tdgame.engine.loader import load_registry

DATA = Path(__file__).resolve().parents[1] / "tdgame" / "data"
REG = load_registry(DATA)


def make_sim(schedule, pool=None, start=500, max_seconds=400.0):
    pool = pool or ["sunbloom", "peashooter"]
    return Simulation(REG.plants, REG.enemies, schedule, pool,
                      seed=1000, start_resource=start, max_seconds=max_seconds)


class SummonTests(unittest.TestCase):
    def test_boss_spawns_minions_on_interval(self):
        sim = make_sim([(1.0, "boss_50", 2)])
        sim.step(1.0)                      # 让 Boss 出场
        boss = [e for e in sim.enemies if e.key == "boss_50"]
        self.assertEqual(len(boss), 1)
        self.assertTrue(boss[0].summon_mob, "Boss 应带 summon 配置")

        for _ in range(130):               # 13s，interval=12s，至少召一次
            sim.step(0.1)

        minions = [e for e in sim.enemies if e.summoned_by is not None]
        self.assertGreaterEqual(len(minions), 1, "12s 后应召出至少一只小怪")
        self.assertTrue(all(m.key == "cone" for m in minions))
        self.assertTrue(all(m.summoned_by is boss[0] for m in minions))

    def test_summon_capped_by_max_alive(self):
        sim = make_sim([(1.0, "boss_50", 2)])
        sim.step(1.0)
        boss = [e for e in sim.enemies if e.key == "boss_50"][0]
        cap = boss.summon_max
        self.assertGreater(cap, 0)
        # 推进很久，召唤数不应超过上限（小怪没被打死，存活数一直顶着 cap）
        for _ in range(1200):
            sim.step(0.1)
        alive = sum(1 for e in sim.enemies if e.summoned_by is boss and not e.dead)
        self.assertLessEqual(alive, cap)

    def test_normal_enemy_never_summons(self):
        sim = make_sim([(1.0, "normal", 0)])
        for _ in range(200):
            sim.step(0.1)
        self.assertFalse([e for e in sim.enemies if e.summoned_by is not None])


class PhaseTests(unittest.TestCase):
    def test_boss_enters_phase2_and_gets_faster(self):
        sim = make_sim([(1.0, "boss_50", 2)])
        sim.step(1.0)
        boss = [e for e in sim.enemies if e.key == "boss_50"][0]
        base_speed = boss.base_speed
        base_interval = boss.summon_interval
        self.assertEqual(boss.phase, 1)

        # 直接把本体打到阈值以下（绕开护甲，专测阶段切换）
        boss.hp_body = boss.hp_body_max * 0.4
        sim.step(0.1)

        self.assertEqual(boss.phase, 2, "血量跌破 50% 应进入二阶段")
        self.assertAlmostEqual(boss.base_speed, base_speed * 1.5, places=6)
        self.assertAlmostEqual(boss.summon_interval, base_interval * 0.6, places=6)

    def test_phase_only_triggers_once(self):
        sim = make_sim([(1.0, "boss_50", 2)])
        sim.step(1.0)
        boss = [e for e in sim.enemies if e.key == "boss_50"][0]
        boss.hp_body = boss.hp_body_max * 0.4
        sim.step(0.1)
        speed_after = boss.base_speed
        for _ in range(50):
            sim.step(0.1)
        self.assertEqual(boss.phase, 2)
        self.assertAlmostEqual(boss.base_speed, speed_after, places=6,
                               msg="二阶段不应重复倍乘速度")

    def test_enemy_without_phase_stays_phase1(self):
        sim = make_sim([(1.0, "normal", 0)])
        sim.step(1.0)
        e = sim.enemies[0]
        e.hp_body = 1.0
        sim.step(0.1)
        self.assertEqual(e.phase, 1)


if __name__ == "__main__":
    unittest.main()
