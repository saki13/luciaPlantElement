# -*- coding: utf-8 -*-
"""balance.py 纯公式单元测试：锁定 game_balance_design.md v0.2 的关键数值断言。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame import balance, config as C


def enemy(body=100, armor=0, red=0.0, block=0):
    return {"hp_body": body, "hp_body_max": body, "armor_hp": armor, "armor_hp_max": armor,
            "armor_reduction": red, "block_flat": block}


class HitPipelineTests(unittest.TestCase):
    def test_block_can_zero_and_break(self):
        e = enemy(block=20)
        d = balance.resolve_hit(e, 20, tags=[])
        self.assertTrue(d["blocked_fully"])
        self.assertEqual(e["hp_body"], 100)            # 满血，伤害归零
        d2 = balance.resolve_hit(e, 25, tags=[])
        self.assertEqual(d2["body_damage"], 5)         # 25-20
        e3 = enemy(block=20)
        d3 = balance.resolve_hit(e3, 20, tags=["shield_break"])
        self.assertTrue(d3["shield_broke"])
        self.assertEqual(d3["body_damage"], 20)        # 破盾全额，无视格挡

    def test_armor_ehp_conservation_red0(self):
        e = enemy(body=100, armor=100, red=0.0)
        balance.resolve_hit(e, 60)                     # 全被甲吸收
        self.assertEqual(e["armor_hp"], 40)
        self.assertEqual(e["hp_body"], 100)
        balance.resolve_hit(e, 60)                     # 甲穿，溢出20进本体
        self.assertEqual(e["armor_hp"], 0)
        self.assertEqual(e["hp_body"], 80)
        balance.resolve_hit(e, 80)
        self.assertLessEqual(e["hp_body"], 0)          # 累计原始伤害 200 = 标称 EHP

    def test_armor_pierce_only_affects_armor_segment(self):
        e = enemy(body=100, armor=100, red=0.0)
        d = balance.resolve_hit(e, 60, tags=["armor_pierce"], ap_mult=2.0)
        self.assertEqual(e["armor_hp"], 0)
        # 容量当量=100/2=50；溢出原始 10 点打本体，倍率不泄漏到本体
        self.assertEqual(d["body_damage"], 10)
        self.assertEqual(e["hp_body"], 90)

    def test_armor_reduction_on_overflow(self):
        e = enemy(body=100, armor=100, red=0.25)
        balance.resolve_hit(e, 100)                    # 正好剥光甲，本体无损
        self.assertEqual(e["armor_hp"], 0)
        self.assertEqual(e["hp_body"], 100)
        e2 = enemy(body=100, armor=100, red=0.25)
        d = balance.resolve_hit(e2, 140)               # 溢出40，折减后30进本体
        self.assertEqual(d["body_damage"], 30)
        self.assertEqual(e2["hp_body"], 70)


class PowerTierTests(unittest.TestCase):
    def test_teaching_first_plant_58_5_t3(self):
        axes = {"fire": 3, "area": 2, "pierce": 0, "durability": 1, "control": 0}
        p = balance.power_score(axes, generic_tag_count=1)   # shield_break 也算1个战斗标签
        self.assertAlmostEqual(p, 58.5, places=4)
        self.assertEqual(balance.tier_of(p), 3)

    def test_max_axes_caps_t13(self):
        axes = {a: 5 for a in balance.AXES}
        p = balance.power_score(axes, generic_tag_count=4)   # 280.8+12=292.8
        self.assertAlmostEqual(p, 292.8, places=4)
        self.assertEqual(balance.tier_of(p), 13)

    def test_t10_lower_bound(self):
        self.assertEqual(balance.tier_of(202.5), 10)
        self.assertEqual(balance.tier_of(0), 1)

    def test_design_token_first_plant_net_200(self):
        axes = {"fire": 3, "area": 2, "pierce": 0, "durability": 1, "control": 0}
        plan = balance.design_token_for_build(axes, "ranged", combat_tags=["shield_break"])
        self.assertEqual(plan["axis_tokens"], 120)
        self.assertEqual(plan["tag_tokens"], 80)
        self.assertEqual(plan["total"], 200)


class DerivedCostControlTests(unittest.TestCase):
    def test_sun_curve_anchors(self):
        self.assertEqual(balance.sun_cost(3), 150)
        self.assertEqual(balance.sun_cost(6), 325)
        self.assertEqual(balance.sun_cost(7), 500)
        self.assertEqual(balance.sun_cost(13), 900)

    def test_recharge_floor_and_ultra(self):
        self.assertGreaterEqual(balance.derive_recharge(1, []), C.RECHARGE_FLOOR)
        self.assertEqual(balance.derive_recharge(8, ["manual_ultimate"]), C.RECHARGE_ULTRA)
        self.assertEqual(balance.derive_recharge(10, ["one_shot"]), C.RECHARGE_SLOW + 2.5)
        self.assertEqual(balance.derive_recharge(3, ["one_shot"]), C.RECHARGE_SLOW)

    def test_slow_resist(self):
        self.assertEqual(balance.effective_speed_mult(0.5, 0), 0.5)
        self.assertEqual(balance.effective_speed_mult(0.5, 0.5), 0.75)
        self.assertEqual(balance.effective_speed_mult(0.5, 1), 1.0)

    def test_knockback_weight_and_immune(self):
        self.assertEqual(balance.knockback_distance(0.3, 1, False), 0.3)
        self.assertEqual(balance.knockback_distance(0.3, 2, False), 0.15)
        self.assertEqual(balance.knockback_distance(0.3, 2, True), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
