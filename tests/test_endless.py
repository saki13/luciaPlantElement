# -*- coding: utf-8 -*-
"""M4 反制器 + 可解性闸门（solver）的测试。

这两个东西之前一个"实现了但没人调用"（反制选怪），一个"留了回调但永远传 None"
（可解性闸门）。本文件把它们钉住，避免以后再退化成死代码。
"""
from __future__ import annotations

import unittest
from pathlib import Path

from tdgame.engine.solver import headless_win_rate, make_solver
from tdgame.engine.wavegen import build_schedule, fixed_schedule
from tdgame.headless_run import POOL_LATE
from tdgame.scenarios.endless import (
    SOLVABILITY_MIN,
    allowed_for_round,
    build_counter_schedule,
    ensure_solvable,
    pick_counter_enemies,
    profile_cards,
)
from tdgame.engine.loader import load_registry

DATA = Path(__file__).resolve().parents[1] / "tdgame" / "data"
REG = load_registry(DATA)


class CounterScheduleTests(unittest.TestCase):
    def _base(self, seed=1000):
        return build_schedule(REG.enemies, 25, seed,
                              allowed=allowed_for_round(12),
                              wave_cap_fn=lambda w: min(10, 3 + w // 2))

    def test_preserves_length_and_timing(self):
        base = self._base()
        counter = build_counter_schedule(REG.enemies, 25, 1000, POOL_LATE, REG.plants)
        self.assertEqual(len(counter), len(base), "反制只替换成分，不能改变总出怪数")
        self.assertEqual([e[0] for e in counter], [e[0] for e in base], "时间轴必须一致")
        self.assertEqual([e[2] for e in counter], [e[2] for e in base], "行分配必须一致")

    def test_actually_injects_counters(self):
        base = self._base()
        counter = build_counter_schedule(REG.enemies, 25, 1000, POOL_LATE, REG.plants)
        changed = [(a, b) for a, b in zip(base, counter) if a[1] != b[1]]
        self.assertTrue(changed, "应当有槽位被替换成反制怪")
        injected = {b[1] for _a, b in changed}
        # POOL_LATE 的画像（control=3）对应的真反制是"高重量免控"一类，
        # 所以注入的应当是重甲/巨人，而不是随便什么怪。
        self.assertTrue(injected & {"bucket", "giant"},
                        f"注入的应是重甲类反制，实际 {injected}")

    def test_does_not_inject_dilution_when_player_has_shield_break(self):
        """规则6 的稀释怪（盾兵/杂兵）不该被当成反制注入。

        盾兵 block_flat=20 会把豌豆/双发的伤害完全归零，实测 1/16 的注入
        就能把 25 波无尽胜率从 0.40 打到 0.00。
        """
        profile = profile_cards(POOL_LATE, REG.plants)
        self.assertIn("shield_break", profile["tags"])
        counter = build_counter_schedule(REG.enemies, 25, 1000, POOL_LATE, REG.plants)
        base = self._base()
        injected = {b[1] for a, b in zip(base, counter) if a[1] != b[1]}
        self.assertNotIn("shield_cadet", injected,
                         "玩家已有破盾时，不应把盾兵当反制批量注入")

    def test_ratio_zero_is_noop(self):
        base = self._base()
        same = build_counter_schedule(REG.enemies, 25, 1000, POOL_LATE, REG.plants,
                                      counter_ratio=0.0)
        self.assertEqual(same, base)

    def test_pick_counter_enemies_returns_known_keys(self):
        profile = profile_cards(POOL_LATE, REG.plants)
        picks = pick_counter_enemies(profile)
        self.assertTrue(picks)
        for k in picks:
            self.assertIn(k, REG.enemies, f"选中了不存在的敌人 {k}")


class SolverTests(unittest.TestCase):
    def test_headless_win_rate_is_deterministic(self):
        sched = fixed_schedule([(8.0, "normal"), (14.0, "cone"), (20.0, "bucket")])
        a = headless_win_rate(REG.plants, REG.enemies, sched, POOL_LATE, 1000, runs=3)
        b = headless_win_rate(REG.plants, REG.enemies, sched, POOL_LATE, 1000, runs=3)
        self.assertEqual(a, b)
        self.assertGreaterEqual(a, 0.0)
        self.assertLessEqual(a, 1.0)

    def test_easy_schedule_scores_high(self):
        sched = fixed_schedule([(10.0, "normal")])
        rate = headless_win_rate(REG.plants, REG.enemies, sched, POOL_LATE, 1000, runs=3)
        self.assertGreaterEqual(rate, SOLVABILITY_MIN)

    def test_empty_schedule_is_auto_win(self):
        rate = headless_win_rate(REG.plants, REG.enemies, [], POOL_LATE, 1000, runs=2)
        self.assertEqual(rate, 1.0)

    def test_make_solver_binds_registry(self):
        solve = make_solver(REG, runs=2)
        sched = fixed_schedule([(10.0, "normal")])
        self.assertGreaterEqual(solve(sched, POOL_LATE, 1000), SOLVABILITY_MIN)


class EnsureSolvableTests(unittest.TestCase):
    def test_without_solver_is_unchecked(self):
        sched, info = ensure_solvable(REG.enemies, 3, 1, POOL_LATE, REG.plants)
        self.assertFalse(info["checked"])
        self.assertIsNone(info["win_rate"])

    def test_with_solver_reports_checked_result(self):
        solve = make_solver(REG, runs=2)
        sched, info = ensure_solvable(REG.enemies, 3, 1, POOL_LATE, REG.plants,
                                      solver=solve)
        self.assertTrue(info["checked"])
        self.assertIsNotNone(info["win_rate"])
        self.assertTrue(sched, "仍应返回一张出怪表")

    def test_unsolvable_round_rerolls(self):
        """solver 恒返回 0 时，应当重 roll 到上限并给出 warning。"""
        calls = {"n": 0}

        def never(schedule, cards, seed):
            calls["n"] += 1
            return 0.0

        _, info = ensure_solvable(REG.enemies, 3, 1, POOL_LATE, REG.plants,
                                  solver=never, max_rolls=3)
        self.assertTrue(info["checked"])
        self.assertEqual(calls["n"], 3, "应当按 max_rolls 重 roll")
        self.assertIn("warning", info)


if __name__ == "__main__":
    unittest.main()
