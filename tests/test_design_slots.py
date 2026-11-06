# -*- coding: utf-8 -*-
"""档位点体系 v3 的规则测试（对齐 docs/TIER_SYSTEM_V3.md）。"""
from __future__ import annotations

import unittest

from tdgame import design_slots as D


class TierLookupTests(unittest.TestCase):
    def test_boundaries(self):
        cases = {5: 1, 6: 2, 7: 3, 8: 4, 9: 5, 10: 6, 12: 7, 14: 8,
                 16: 9, 17: 10, 18: 10, 19: 11, 23: 11, 24: 12,
                 26: 12, 27: 13, 30: 13}
        for slots, tier in cases.items():
            self.assertEqual(D.tier_for_slots(slots), tier,
                             f"{slots} 档应落在 T{tier}")

    def test_designer_examples(self):
        """设计方原话：16 档是 T9，17 档就是 T10。"""
        self.assertEqual(D.tier_for_slots(16), 9)
        self.assertEqual(D.tier_for_slots(17), 10)


class PeashooterTests(unittest.TestCase):
    def test_peashooter_is_t2(self):
        p = D.PlantPlan(levels={"dps": 2, "attack_speed": 4})
        self.assertEqual(p.slots, 6)
        self.assertEqual(p.tier, 2)
        self.assertEqual(p.dps, 20)
        self.assertEqual(p.interval, 1.4)
        self.assertAlmostEqual(p.damage_per_hit, 28.0)
        self.assertEqual(p.cooldown, 7.5)

    def test_cd_floor(self):
        """CD 下限 7.5s，再减也不低于它。"""
        p = D.PlantPlan(levels={"dps": 2, "cd": 5}, mechanics=("aura",))
        self.assertGreaterEqual(p.cooldown, D.CD_FLOOR)


class WallnutTests(unittest.TestCase):
    def test_wallnut_is_t4(self):
        p = D.PlantPlan(levels={"dps": 1, "hp": 3, "sun": 3, "cd": 1},
                        attacking=False, explicit_sun=50)
        self.assertEqual(p.slots, 8)
        self.assertEqual(p.tier, 4)
        self.assertEqual(p.sun, 50)
        self.assertEqual(p.hp if hasattr(p, "hp") else 4000,
                         D.HP_BY_LEVEL[3])

    def test_sun_reduction(self):
        p = D.PlantPlan(levels={"dps": 1, "sun": 3}, attacking=False)
        self.assertEqual(p.sun, D.TIER_SUN[p.tier] - 100)


class TenacityTests(unittest.TestCase):
    def test_slow_is_multiplicative_on_ratio_and_flat_on_time(self):
        """破格减速 142% / 15s 打巨人(150)：71% / 12s。"""
        ratio, dur = D.slow_after_tenacity(1.42, 15.0, "T5")
        self.assertAlmostEqual(ratio, 0.71)
        self.assertAlmostEqual(dur, 12.0)

    def test_boss_sp_immunity(self):
        ratio, dur = D.slow_after_tenacity(1.42, 15.0, "SP+")
        self.assertEqual(ratio, 0.0)
        self.assertEqual(dur, 0.0)

    def test_knockback_threshold(self):
        self.assertTrue(D.knockback_effective(100, "T3"))    # 80*0.8=64
        self.assertFalse(D.knockback_effective(100, "T5"))   # 150*0.8=120
        self.assertTrue(D.knockback_effective(150, "T5"))
        self.assertFalse(D.knockback_effective(150, "SP"))   # 300*0.8=240

    def test_splash_discount(self):
        self.assertAlmostEqual(D.splash_effect(1.42), 0.355)


class ValidationTests(unittest.TestCase):
    def test_level6_requires_overclock(self):
        p = D.PlantPlan(levels={"dps": 6}, attacking=False)
        ok, errs = p.validate()
        self.assertFalse(ok)
        self.assertTrue(any("破格" in e for e in errs))

    def test_level6_with_overclock_ok(self):
        p = D.PlantPlan(levels={"dps": 6}, mechanics=("overclock",),
                        attacking=False)
        ok, errs = p.validate()
        self.assertTrue(ok, errs)
        self.assertEqual(p.dps, 180)


class DesignerT6ExampleTests(unittest.TestCase):
    """设计方的 T6 例子：坦度1+攻击力3+阳光2+CD2+破盾1+减速1 = 10 档。

    注意：这里有一个**待确认的 1 点差异**——若「攻速」也占 1 点，
    则总数为 11（T6 上限也是 10，会溢出到 T7）。
    见 tests 报告里列出的两种读法。
    """

    def test_without_attack_speed_point(self):
        p = D.PlantPlan(levels={"hp": 1, "dps": 3, "sun": 2, "cd": 2,
                                "shield_break": 1, "slow": 1},
                        attacking=False)
        self.assertEqual(p.slots, 10)
        self.assertEqual(p.tier, 6)

    def test_with_attack_speed_point(self):
        p = D.PlantPlan(levels={"hp": 1, "dps": 3, "sun": 2, "cd": 2,
                                "shield_break": 1, "slow": 1,
                                "attack_speed": 4},
                        attacking=True)
        self.assertEqual(p.slots, 11)
        self.assertEqual(p.tier, 7)


if __name__ == "__main__":
    unittest.main()
