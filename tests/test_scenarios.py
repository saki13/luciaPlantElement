# -*- coding: utf-8 -*-
"""场景层（M2 定制器 / M4 无尽反制 / M5 僵尸编辑 / 进度 / 关卡运行）单元测试。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame import config as C
from tdgame.engine.loader import load_registry, Registry
from tdgame.scenarios import (
    customizer as cz, zombie_editor as ze, endless as el, progression as pg,
    level_run,
)
from tdgame.headless_run import POOL_BASIC

DATA = ROOT / "tdgame" / "data"


class CustomizerTests(unittest.TestCase):
    def test_first_plant_matches_doc_200_tokens_t3(self):
        # 火力3 + 破盾，远程免费底盘 area2/dur1
        axes = {"fire": 3, "area": 2, "pierce": 0, "durability": 1, "control": 0}
        ok, errs, q = cz.validate_build("ranged", axes, ["shield_break"], "P2", 200)
        self.assertTrue(ok, errs)
        self.assertEqual(q["total"], 200)          # 轴120 + 破盾80
        d = cz.build_plant_definition("ut_break", "测试破盾", "ranged", axes,
                                      ["shield_break"], "P2", 200)
        self.assertEqual(d["tier"], 3)
        self.assertEqual(d["sun"], 150)
        self.assertIn("shield_break", d["tags"])

    def test_build_is_registerable(self):
        axes = {"fire": 2, "area": 2, "pierce": 0, "durability": 1, "control": 0}
        d = cz.build_plant_definition("ut_card", "测试卡", "ranged", axes, [], "P2", 200)
        reg = Registry()
        reg.add_plant(d)
        self.assertEqual(reg.errors, [])
        self.assertIn("ut_card", reg.plants)

    def test_phase_gate_rejects_over_level_axis_and_tag(self):
        axes = {"fire": 4, "area": 2, "pierce": 0, "durability": 1, "control": 0}
        ok, errs, _ = cz.validate_build("ranged", axes, [], "P2", 9999)
        self.assertFalse(ok)                       # P2 单轴封顶3
        ok2, errs2, _ = cz.validate_build(
            "ranged", {"fire": 3, "area": 2, "pierce": 0, "durability": 1, "control": 0},
            ["armor_pierce"], "P2", 9999)
        self.assertFalse(ok2)                      # 穿甲 P2 未解锁

    def test_token_budget_enforced(self):
        axes = {"fire": 3, "area": 2, "pierce": 0, "durability": 1, "control": 0}
        ok, _, _ = cz.validate_build("ranged", axes, ["shield_break"], "P2", 199)
        self.assertFalse(ok)


class ZombieEditorTests(unittest.TestCase):
    def test_valid_build_passes_loader(self):
        axes = {"speed": 2, "defense": 0, "body": 1, "regen": 0}
        d = ze.build_enemy_definition("ut_z", "测试僵尸", axes)
        reg = Registry()
        reg.add_enemy(d)
        self.assertEqual(reg.errors, [])
        self.assertLess(d["armor"]["reduction"], 1)

    def test_block_tag_costs_points(self):
        base = {"speed": 2, "defense": 0, "body": 1, "regen": 0}
        self.assertGreater(ze.quote_points(base, ["block"]), ze.quote_points(base, []))

    def test_immobile_and_overbudget_rejected(self):
        ok, _ = ze.validate_enemy_build({"speed": 0, "defense": 0, "body": 1, "regen": 0})
        self.assertFalse(ok)
        maxed = {a: 5 for a in ("speed", "defense", "body", "regen")}
        ok2, _ = ze.validate_enemy_build(maxed, [], point_cap=600)
        self.assertFalse(ok2)


class EndlessTests(unittest.TestCase):
    def setUp(self):
        self.reg = load_registry(DATA)

    def test_round_unlock_curve(self):
        self.assertNotIn("bucket", el.allowed_for_round(3))
        self.assertIn("bucket", el.allowed_for_round(4))
        self.assertIn("giant", el.allowed_for_round(9))

    def test_counter_picker_targets_weak_axis(self):
        prof = {"axes_max": {"fire": 2, "area": 1, "pierce": 3, "durability": 1, "control": 0},
                "tags": set(), "max_tier": 5, "melee": 0, "ranged": 6}
        self.assertIn("giant", el.pick_counter_enemies(prof))     # 穿透特化→厚本体
        prof2 = {"axes_max": {"fire": 2, "area": 3, "pierce": 0, "durability": 1, "control": 0},
                 "tags": set(), "max_tier": 5, "melee": 0, "ranged": 6}
        self.assertIn("bucket", el.pick_counter_enemies(prof2))   # AoE→高甲精英

    def test_boss_round_contains_boss(self):
        cards = list(self.reg.plants.keys())
        sched = el.build_round_schedule(self.reg.enemies, 50, 1, cards, self.reg.plants)
        self.assertIn("boss_50", [k for _, k, _ in sched])

    def test_solvability_noop_without_solver(self):
        cards = list(self.reg.plants.keys())
        _, info = el.ensure_solvable(self.reg.enemies, 3, 1, cards, self.reg.plants)
        self.assertFalse(info["checked"])


class ProgressionTests(unittest.TestCase):
    def setUp(self):
        self.levels = level_run.load_levels(DATA / "levels")
        self.p = pg.PlayerProgress(self.levels)

    def test_first_clear_grants_200_repeat_gives_none(self):
        self.assertEqual(self.p.clear_level("m2_shield"), 200)
        self.assertEqual(self.p.clear_level("m2_shield"), 0)
        self.assertEqual(self.p.design_tokens, 200)
        self.assertIn("plant_customizer", self.p.unlocked)

    def test_phase_detection(self):
        self.assertEqual(self.p.reached_phase(), "P1")
        self.p.clear_level("m2_shield")
        self.assertEqual(self.p.reached_phase(), "P2")

    def test_reward_single_source_is_level_json(self):
        """奖励以关卡 JSON 为唯一来源，progression 不得再持有硬编码表。"""
        self.assertFalse(hasattr(pg, "CHALLENGE_TOKEN_REWARD"),
                         "CHALLENGE_TOKEN_REWARD 已删除，避免与关卡 JSON 双写")
        for key, lv in self.levels.items():
            expected = int((lv.get("reward") or {}).get("design_tokens", 0) or 0)
            got = pg.reward_for_level(key, True, self.levels)["design_tokens"]
            self.assertEqual(got, expected, key)

    def test_reward_without_levels_is_zero(self):
        """不传 levels 时没有回退表，一律 0。"""
        self.assertEqual(pg.reward_for_level("m2_shield")["design_tokens"], 0)


class LevelRunTests(unittest.TestCase):
    def setUp(self):
        self.reg = load_registry(DATA)
        self.levels = level_run.load_levels(DATA / "levels")

    def test_all_levels_loaded(self):
        # M1x10 + M2x6 + M3x15 + m3_boss = 32
        self.assertEqual(len(self.levels), 32)
        self.assertIn("m1_01", self.levels)
        self.assertIn("m3_boss", self.levels)
        self.assertIn("m3_08", self.levels, "M3 进阶主线应补齐到 8 关")
        phases = {lv["phase"] for lv in self.levels.values()}
        self.assertEqual(phases, {"M1", "M2", "M3"})

    def test_m1_first_level_winnable(self):
        _, m = level_run.run_level(self.levels["m1_01"], self.reg, seed=1000)
        self.assertTrue(m["won"])

    def test_m2_shield_smart_wins_dumb_cannot(self):
        lv = self.levels["m2_shield"]
        _, smart = level_run.run_level(lv, self.reg, seed=1000, smart=True)
        _, dumb = level_run.run_level(lv, self.reg, card_pool=POOL_BASIC,
                                      seed=1000, smart=False)
        self.assertTrue(smart["won"])
        self.assertFalse(dumb["won"])


if __name__ == "__main__":
    unittest.main()
