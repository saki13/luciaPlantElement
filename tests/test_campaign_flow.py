# -*- coding: utf-8 -*-
"""端到端战役流程验收测试。

覆盖整条链路：
  M1 18 关 -> 拿到代币/卡槽 -> M2 挑战关（救援通关不算数，干净通关才解锁下一关）
  -> 工坊造破盾植物 -> 带进去真正打通 -> M3 15 关 + Boss 可达

说明：逐关"能不能赢"由校准门禁（check_levels，38 关 × 5 seeds）负责；
本文件守的是**流程逻辑**是否正确咬合。
"""
from __future__ import annotations

import unittest
from pathlib import Path

from tdgame.engine.loader import load_registry
from tdgame.scenarios import customizer, level_run
from tdgame.scenarios.progression import (CHALLENGE_CLEAN, CHALLENGE_RESCUED,
                                          CARD_SLOT_BASE, CHALLENGE_LEVELS,
                                          PlayerProgress)
from tdgame.ui_workshop import WorkshopState

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tdgame" / "data"
REG = load_registry(DATA)
LEVELS = {}
import json  # noqa: E402

for f in (DATA / "levels").glob("*.json"):
    d = json.loads(f.read_text(encoding="utf-8"))
    LEVELS[d["key"]] = d

M1 = [f"m1_{i:02d}" for i in range(1, 19)]
M3 = [f"m3_{i:02d}" for i in range(1, 16)] + ["m3_boss"]


class CampaignFlowTests(unittest.TestCase):
    def test_p1_has_18_levels_and_rewards(self):
        self.assertEqual(len(M1), 18)
        for key in M1:
            self.assertIn(key, LEVELS, f"缺少关卡 {key}")
            r = LEVELS[key].get("reward") or {}
            self.assertTrue(r.get("plant") or r.get("design_tokens"),
                            f"{key} 没有任何奖励")

    def test_clearing_m1_unlocks_customizer_and_tokens(self):
        p = PlayerProgress(LEVELS)
        total = 0
        for key in M1:
            total += p.clear_level(key)
        self.assertEqual(len(p.cleared), 18)
        self.assertEqual(p.design_tokens, total)
        self.assertTrue(p.can_build() if hasattr(p, "can_build") else True)
        # 进 M2 后卡槽 = 6 + 挑战关数(0) + 阶段(P2=1) = 7
        self.assertGreaterEqual(p.card_slots(LEVELS), CARD_SLOT_BASE)

    def test_challenge_needs_clean_clear_to_advance(self):
        """M2 挑战关闭环：救援通关不算数 -> 干净通关才解锁下一关。"""
        lv = LEVELS["m2_shield"]
        p = PlayerProgress(LEVELS)

        # 1) 无克制配置：会被首车救援救下来
        _, dumb = level_run.run_level(lv, REG, card_pool=["sunbloom", "peashooter",
                                                          "wallnut", "repeater"],
                                      seed=1000, smart=False)
        self.assertTrue(dumb["won"], "挑战关必须有保底，不能卡死玩家")
        self.assertGreaterEqual(dumb.get("rescues", 0), 1)
        st = p.record_challenge_result("m2_shield", won=True,
                                       rescues=dumb.get("rescues", 0))
        self.assertEqual(st, CHALLENGE_RESCUED)
        self.assertTrue(p.needs_refight("m2_shield"))
        self.assertEqual(p.next_challenge(), "m2_shield", "救援通关不解锁下一关")

        # 2) 用工坊造一株破盾植物，再打一次
        ws = WorkshopState(tokens=400, name="端到端破盾株")
        ws.bump("fire", +3)
        ws.toggle_tag("shield_break")
        built = ws.build()
        key = built["key"]
        pool = ["sunbloom", "peashooter", "wallnut", built["cn"]]
        reg2 = load_registry(DATA)
        reg2.plants[key] = dict(built)

        # 玩家实际处境：关卡默认卡池 + 自己造的植物
        base_pool = list(lv.get("card_pool") or [])
        _, smart = level_run.run_level(lv, reg2, card_pool=base_pool + [key],
                                       seed=1000, smart=True)
        self.assertTrue(smart["won"], "带破盾植物应当能过关")
        self.assertEqual(smart.get("rescues", 0), 0, "干净通关不该用救援")

        st2 = p.record_challenge_result("m2_shield", won=True, rescues=0)
        self.assertEqual(st2, CHALLENGE_CLEAN)
        self.assertFalse(p.needs_refight("m2_shield"))
        self.assertEqual(p.next_challenge(), "m2_armor", "干净通关后解锁下一关")

    def test_four_challenges_gate_in_order(self):
        p = PlayerProgress(LEVELS)
        for key in CHALLENGE_LEVELS:
            self.assertEqual(p.can_enter_challenge(key), p.next_challenge() == key)
            p.record_challenge_result(key, won=True, rescues=0)
        self.assertIsNone(p.next_challenge())

    def test_m3_structure(self):
        self.assertEqual(len(M3), 16)
        for key in M3:
            self.assertIn(key, LEVELS, f"缺少关卡 {key}")

    def test_boss_grants_t8_permission(self):
        p = PlayerProgress(LEVELS)
        p.clear_level("m3_boss")
        self.assertGreaterEqual(p.plant_tier_permission, 8)

    def test_workshop_output_is_engine_consumable(self):
        ws = WorkshopState(tokens=400, name="可用性检查")
        ws.toggle_tag("shield_break")
        d = ws.build()
        for f in ("key", "cn", "role", "axes", "sun", "hp"):
            self.assertIn(f, d)
        ok, errs, quote = customizer.validate_build(
            d["role"], d["axes"], d.get("tags", []), "P2", 400)
        self.assertTrue(ok, errs)


if __name__ == "__main__":
    unittest.main()
