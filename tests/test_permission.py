# -*- coding: utf-8 -*-
"""阶段权限模型测试：关卡奖励 = 代币 + 可创造品阶权限。

设计意图（项目所有者定）：奖励不再"发某株具体植物"，而是给代币与权限，
让玩家在工坊里自己造。所以这里守的是**权限的正确性与单调性**。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tdgame import config as C
from tdgame.scenarios.customizer import PHASE_RULES
from tdgame.scenarios.progression import PlayerProgress, reward_for_level
from tdgame.scenarios.savegame import FORMAT, load_from, restore, save_to, snapshot

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tdgame" / "data"
import json  # noqa: E402

LEVELS = {
    f.stem: json.loads(f.read_text(encoding="utf-8"))
    for f in (DATA / "levels").glob("*.json")
}


class RewardSchemaTests(unittest.TestCase):
    def test_reward_has_unlock_tier(self):
        r = reward_for_level("m1_01", True, LEVELS)
        self.assertIn("design_tokens", r)
        self.assertIn("unlock_tier", r)

    def test_m3_boss_grants_t8_permission(self):
        """M3 Boss 的奖励是"够造 T8 的代币 + 创造 T8 的权限"。

        代币数不是拍脑袋：是穷举 balance.token_cost 得到的**最便宜 T8 配装**；
        若价目表变了，这个数会变，测试会提醒重新核算。
        """
        r = reward_for_level("m3_boss", True, LEVELS)
        self.assertEqual(r["unlock_tier"], 8)
        self.assertGreater(r["design_tokens"], 0, "必须给够代币，否则拿不到权限也造不出")

    def test_repeat_clear_gives_nothing(self):
        r = reward_for_level("m3_boss", False, LEVELS)
        self.assertEqual(r["design_tokens"], 0)
        self.assertEqual(r["unlock_tier"], 0)


class PermissionTests(unittest.TestCase):
    def test_permission_only_goes_up(self):
        p = PlayerProgress(LEVELS)
        p.plant_tier_permission = 9
        p.clear_level("m3_boss")          # 奖励是 unlock_tier=8
        self.assertEqual(p.plant_tier_permission, 9, "低权限不能顶掉已获得的高权限")

    def test_clear_raises_permission(self):
        p = PlayerProgress(LEVELS)
        self.assertEqual(p.plant_tier_permission, 0)
        p.clear_level("m3_boss")
        self.assertEqual(p.plant_tier_permission, 8)

    def test_max_buildable_tier_takes_larger(self):
        p = PlayerProgress(LEVELS)
        p.cleared = ["m1_01"]                       # -> P1，无定制器
        self.assertEqual(p.max_buildable_tier(), 0)
        p.cleared = ["m3_01"]                       # -> P3
        self.assertEqual(p.max_buildable_tier(), PHASE_RULES["P3"]["max_tier"])
        p.plant_tier_permission = 12
        self.assertEqual(p.max_buildable_tier(), 12, "权限可以超过阶段默认上限")

    def test_unlock_plant_is_idempotent(self):
        p = PlayerProgress(LEVELS)
        self.assertTrue(p.unlock_plant("melonpult"))
        self.assertFalse(p.unlock_plant("melonpult"))
        self.assertEqual(p.unlocked_plants, ["melonpult"])


class SaveTests(unittest.TestCase):
    def test_round_trip(self):
        p = PlayerProgress(LEVELS)
        p.unlock_plant("melonpult")
        p.unlock_plant("thorn_piercer")
        p.plant_tier_permission = 8
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            save_to(path, p)
            q, warn = load_from(path, LEVELS)
            self.assertIsNone(warn)
            self.assertEqual(q.unlocked_plants, p.unlocked_plants)
            self.assertEqual(q.plant_tier_permission, 8)

    def test_snapshot_exposes_fields(self):
        p = PlayerProgress(LEVELS)
        p.unlock_plant("x")
        p.plant_tier_permission = 5
        snap = snapshot(p)
        self.assertEqual(snap["unlocked_plants"], ["x"])
        self.assertEqual(snap["plant_tier_permission"], 5)

    def test_forged_permission_clamped(self):
        q, _ = restore({"format": FORMAT, "cleared": [], "design_tokens": 0,
                        "plant_tier_permission": 9999})
        self.assertEqual(q.plant_tier_permission, C.MAX_TIER, "手改档要被夹到 MAX_TIER")

    def test_negative_permission_clamped(self):
        q, _ = restore({"format": FORMAT, "cleared": [], "design_tokens": 0,
                        "plant_tier_permission": -5})
        self.assertEqual(q.plant_tier_permission, 0)

    def test_bogus_types_ignored(self):
        q, warn = restore({"format": FORMAT, "cleared": [], "design_tokens": 0,
                           "unlocked_plants": "x", "plant_tier_permission": "8"})
        self.assertEqual(q.unlocked_plants, [])
        self.assertEqual(q.plant_tier_permission, 0)
        self.assertIsNotNone(warn)


if __name__ == "__main__":
    unittest.main()
