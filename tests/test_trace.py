# -*- coding: utf-8 -*-
"""board.step 逐步 trace 的测试（E-02 安全网）。"""
from __future__ import annotations

import unittest

from tdgame.engine.trace import SCENARIOS, TRACE_FORMAT, run_all, run_scenario


class TraceTests(unittest.TestCase):
    def test_all_scenarios_run(self):
        data = run_all()
        self.assertEqual(data["format"], TRACE_FORMAT)
        self.assertEqual(set(data["scenarios"]), set(SCENARIOS))

    def test_frames_have_expected_shape(self):
        tr = run_scenario("core_shoot_bite")
        self.assertGreater(tr["steps"], 100, "场景应当真的跑了很多步")
        f = tr["frames"][0]
        for k in ("t", "sun", "lives", "plants", "enemies", "proj",
                  "kills", "mowers", "breaches", "over"):
            self.assertIn(k, f)

    def test_deterministic(self):
        a = run_scenario("armor_slow")
        b = run_scenario("armor_slow")
        self.assertEqual(a["frames"], b["frames"], "同场景两次跑必须逐字段相同")

    def test_scenarios_are_not_degenerate(self):
        """每个场景都得真的动起来，否则基线等于没测。"""
        for name in SCENARIOS:
            tr = run_scenario(name)
            first, last = tr["frames"][0], tr["frames"][-1]
            moved = any(f["enemies"] != first["enemies"] for f in tr["frames"])
            self.assertTrue(moved, f"{name}: 敌人在整局里完全没动，场景无意义")
            self.assertNotEqual(first["t"], last["t"])

    def test_enemy_hp_actually_drops(self):
        """直射场景里敌人必须掉血 —— 否则说明弹道/命中没生效。"""
        tr = run_scenario("core_shoot_bite")
        full = {}
        for f in tr["frames"]:
            for row, x, hp in f["enemies"]:
                full.setdefault((row, round(x, 1)), set()).add(hp)
        self.assertTrue(any(len(v) > 1 for v in full.values()),
                        "没有任何敌人的血量变化过")

    def test_trace_covers_distinct_mechanics(self):
        """每个场景对应一类机制，名字里要能看出来，否则以后没人知道覆盖了什么。"""
        self.assertGreaterEqual(len(SCENARIOS), 4)
        names = " ".join(SCENARIOS)
        for kw in ("shoot", "armor", "block", "move"):
            self.assertIn(kw, names)
        # move_bite 是 GDScript 第一个移植块的对照场景，必须存在
        self.assertIn("move_bite", SCENARIOS)


if __name__ == "__main__":
    unittest.main()
