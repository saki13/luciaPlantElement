# -*- coding: utf-8 -*-
"""可玩客户端的 UI 行为测试（关卡切换、存档接入、模式差异）。

这些是"界面能点、能换关、不崩"的最小保证；视觉细节靠截图人工看，
但状态机必须有测试守，否则改绘制很容易把它弄坏而没人发现。

注意：每个用例都用**独立的临时存档**，绝不碰玩家真实的 saves/progress.json。
（曾经因为共用真实存档，前一个用例通关后后面用例读到"已通关"而假失败。）
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame  # noqa: F401
except ImportError:  # Windows 本机没有全局 pygame，用项目自带 libs/
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "libs"))

from tdgame.app_pygame import GameApp


class _TempSaveMixin:
    def make_app(self, **kw) -> GameApp:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return GameApp(save_path=Path(tmp.name) / "progress.json", **kw)


class LevelCycleTests(_TempSaveMixin, unittest.TestCase):
    def setUp(self):
        self.app = self.make_app(use_sprites=False, mode="play")

    def test_cycle_moves_to_next_level(self):
        app = self.app
        app.level_key = sorted(app.levels)[0]
        app.new_game()
        first = app.level_key
        app.cycle_level(1)
        self.assertNotEqual(app.level_key, first, "按 ] 应当切到下一关")
        self.assertEqual(app.level_key, sorted(app.levels)[1])

    def test_cycle_wraps_around(self):
        app = self.app
        keys = sorted(app.levels)
        app.level_key = keys[-1]
        app.new_game()
        app.cycle_level(1)
        self.assertEqual(app.level_key, keys[0], "最后一关再下一关应当回到第一关")

    def test_cycle_rebuilds_session(self):
        app = self.app
        old_session = app.session
        app.cycle_level(1)
        self.assertIsNot(app.session, old_session, "换关必须重建 session")
        self.assertFalse(app.session.over)

    def test_cycle_negative(self):
        app = self.app
        keys = sorted(app.levels)
        app.level_key = keys[0]
        app.new_game()
        app.cycle_level(-1)
        self.assertEqual(app.level_key, keys[-1])


class ProgressHudTests(_TempSaveMixin, unittest.TestCase):
    def test_progress_and_save_path_exist(self):
        app = self.make_app(use_sprites=False, mode="play")
        self.assertTrue(hasattr(app, "progress"))
        self.assertTrue(hasattr(app, "save_path"))
        self.assertTrue(hasattr(app.progress, "tower_floor"),
                        "进度里要有爬塔层数，底部 HUD 会读它")

    def test_winning_records_once(self):
        app = self.make_app(use_sprites=False, mode="play")
        cleared_before = len(app.progress.cleared)
        # over/won 是 PlaySession 的只读属性，直接改它底下的 sim 更稳
        app.session.sim.over = True
        app.session.sim.won = True
        app._record_clear_if_needed()
        app._record_clear_if_needed()      # 第二次不应重复记账
        self.assertEqual(len(app.progress.cleared), cleared_before + 1)
        self.assertTrue(app._recorded)

    def test_second_clear_of_same_level_does_not_duplicate(self):
        app = self.make_app(use_sprites=False, mode="play")
        app.session.sim.over = True
        app.session.sim.won = True
        app._record_clear_if_needed()
        n = len(app.progress.cleared)
        app._recorded = False               # 模拟重开后再通关同一关
        app._record_clear_if_needed()
        self.assertEqual(len(app.progress.cleared), n,
                         "同一关二次通关不应重复计入 cleared")

    def test_izombie_does_not_record_mainline_progress(self):
        app = self.make_app(use_sprites=False, mode="izombie")
        cleared_before = list(app.progress.cleared)
        app.session.core.sim.over = True
        app.session.core.sim.won = True
        app._record_clear_if_needed()
        self.assertEqual(app.progress.cleared, cleared_before,
                         "我是僵尸不该影响主线阶段解锁")


class IzombieUiTests(_TempSaveMixin, unittest.TestCase):
    def test_izombie_cycles_among_zombie_levels(self):
        app = self.make_app(use_sprites=False, mode="izombie")
        first = app.level_key
        app.cycle_level(1)
        self.assertNotEqual(app.level_key, first)
        self.assertEqual(len(app.levels), 3)

    def test_izombie_has_no_shovel(self):
        app = self.make_app(use_sprites=False, mode="izombie")
        app.draw()
        self.assertEqual(app.shovel_rect.width, 0)


if __name__ == "__main__":
    unittest.main()
