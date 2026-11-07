# -*- coding: utf-8 -*-
"""工坊逻辑测试（不依赖 pygame）。"""
from __future__ import annotations

import unittest

from tdgame.ui_workshop import WorkshopState, render_state


class WorkshopTests(unittest.TestCase):
    def test_initial_cost_is_zero(self):
        s = WorkshopState()
        self.assertEqual(s.cost, 0)
        self.assertTrue(s.can_build)

    def test_axis_capped_by_phase(self):
        s = WorkshopState(phase="P2")
        for _ in range(10):
            s.bump("fire", +1)
        self.assertEqual(s.levels["fire"], 3, "P2 单轴上限应为 3")

    def test_cannot_go_negative(self):
        s = WorkshopState()
        s.bump("fire", -1)
        self.assertEqual(s.levels["fire"], 0)

    def test_shield_break_costs_tokens(self):
        s = WorkshopState()
        s.toggle_tag("shield_break")
        self.assertIn("shield_break", s.tags)
        self.assertGreater(s.cost, 0)

    def test_cost_limits_build(self):
        s = WorkshopState(tokens=100)
        s.toggle_tag("shield_break")          # 80
        for _ in range(3):
            s.bump("fire", +1)                # +120 -> 200 > 100
        self.assertFalse(s.affordable)
        self.assertFalse(s.can_build)

    def test_build_returns_engine_ready_definition(self):
        s = WorkshopState(tokens=400, name="破盾测试株")
        s.bump("fire", +3)
        s.toggle_tag("shield_break")
        self.assertTrue(s.can_build, s.summary()[1])
        d = s.build()
        for key in ("key", "cn", "role", "axes", "sun", "hp"):
            self.assertIn(key, d, f"产物缺少字段 {key}")
        self.assertIn("shield_break", d.get("tags", []))

    def test_render_contains_key_numbers(self):
        s = WorkshopState()
        s.bump("fire", +2)
        text = render_state(s)
        self.assertIn("工坊", text)
        self.assertIn("火力", text)
        self.assertIn("代币", text)


if __name__ == "__main__":
    unittest.main()
