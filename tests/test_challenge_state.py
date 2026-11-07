# -*- coding: utf-8 -*-
"""挑战关状态机测试：救援通关不算过关，必须"干净通关"。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tdgame.scenarios.progression import (CHALLENGE_CLEAN, CHALLENGE_LEVELS,
                                          CHALLENGE_RESCUED, PlayerProgress)
from tdgame.scenarios.savegame import load_from, save_to


class ChallengeStateTests(unittest.TestCase):
    def setUp(self):
        self.p = PlayerProgress()

    def test_initial_state(self):
        self.assertEqual(self.p.next_challenge(), "m2_shield")
        self.assertTrue(self.p.can_enter_challenge("m2_shield"))
        self.assertFalse(self.p.can_enter_challenge("m2_armor"),
                         "后面的挑战关要先解锁")

    def test_rescued_clear_is_not_a_clear(self):
        st = self.p.record_challenge_result("m2_shield", won=True, rescues=1)
        self.assertEqual(st, CHALLENGE_RESCUED)
        self.assertFalse(self.p.challenge_cleared("m2_shield"))
        self.assertTrue(self.p.needs_refight("m2_shield"),
                        "救援通关后应当要求重打本关")
        self.assertEqual(self.p.next_challenge(), "m2_shield",
                         "没干净通关就不能进下一关")

    def test_clean_clear_advances(self):
        st = self.p.record_challenge_result("m2_shield", won=True, rescues=0)
        self.assertEqual(st, CHALLENGE_CLEAN)
        self.assertTrue(self.p.challenge_cleared("m2_shield"))
        self.assertFalse(self.p.needs_refight("m2_shield"))
        self.assertEqual(self.p.next_challenge(), "m2_armor")

    def test_loss_does_not_change_state(self):
        self.p.record_challenge_result("m2_shield", won=False, rescues=0)
        self.assertEqual(self.p.challenge_state.get("m2_shield"), None)
        self.assertEqual(self.p.next_challenge(), "m2_shield")

    def test_clean_not_downgraded_by_later_rescue(self):
        self.p.record_challenge_result("m2_shield", won=True, rescues=0)
        st = self.p.record_challenge_result("m2_shield", won=True, rescues=2)
        self.assertEqual(st, CHALLENGE_CLEAN, "已干净通关不能被后来的救援降级")

    def test_all_four_challenges_in_order(self):
        for key in CHALLENGE_LEVELS:
            self.assertEqual(self.p.next_challenge(), key)
            self.p.record_challenge_result(key, won=True, rescues=0)
        self.assertIsNone(self.p.next_challenge(), "四关全清后没有下一个")

    def test_full_flow_rescued_then_clean(self):
        """完整流程：救援通关 -> 重打 -> 干净通关 -> 才解锁下一关。"""
        self.p.record_challenge_result("m2_shield", won=True, rescues=1)
        self.assertTrue(self.p.needs_refight("m2_shield"))
        self.assertEqual(self.p.next_challenge(), "m2_shield")
        self.p.record_challenge_result("m2_shield", won=True, rescues=0)
        self.assertFalse(self.p.needs_refight("m2_shield"))
        self.assertEqual(self.p.next_challenge(), "m2_armor")

    def test_state_persists(self):
        self.p.record_challenge_result("m2_shield", won=True, rescues=1)
        self.p.record_challenge_result("m2_armor", won=True, rescues=0)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            save_to(path, self.p)
            q, warn = load_from(path)
        self.assertIsNone(warn)
        self.assertEqual(q.challenge_state.get("m2_shield"), CHALLENGE_RESCUED)
        self.assertEqual(q.challenge_state.get("m2_armor"), CHALLENGE_CLEAN)


if __name__ == "__main__":
    unittest.main()
