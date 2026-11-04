# -*- coding: utf-8 -*-
"""存档持久化测试：往返、坏档降级、以及"不信任文件"的安全性质。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tdgame.scenarios.progression import PHASES, PlayerProgress
from tdgame.scenarios.savegame import (
    FORMAT,
    load_from,
    restore,
    save_to,
    snapshot,
)


class RoundTripTests(unittest.TestCase):
    def test_round_trip_preserves_state(self):
        p = PlayerProgress()
        p.clear_level("m1_01")
        p.clear_level("m2_armor")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            save_to(path, p)
            q, warn = load_from(path)
            self.assertIsNone(warn)
            self.assertEqual(q.cleared, p.cleared)
            self.assertEqual(q.design_tokens, p.design_tokens)

    def test_snapshot_has_format_and_no_unlocked(self):
        p = PlayerProgress()
        snap = snapshot(p)
        self.assertEqual(snap["format"], FORMAT)
        self.assertNotIn("unlocked", snap, "unlocked 是推导出来的，不该落盘")

    def test_save_is_utf8_without_bom(self):
        p = PlayerProgress()
        p.clear_level("m1_01")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            save_to(path, p)
            head = path.read_bytes()[:3]
            self.assertNotEqual(head, b"\xef\xbb\xbf", "存档不能带 BOM")

    def test_atomic_write_leaves_no_tmp(self):
        p = PlayerProgress()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.json"
            save_to(path, p)
            self.assertEqual([f.name for f in Path(d).iterdir()], ["s.json"])


class CorruptionTests(unittest.TestCase):
    def test_missing_file_is_fresh_save_without_warning(self):
        with tempfile.TemporaryDirectory() as d:
            prog, warn = load_from(Path(d) / "nope.json")
            self.assertIsNone(warn)
            self.assertEqual(prog.cleared, [])
            self.assertEqual(prog.design_tokens, 0)

    def test_broken_json_degrades(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            prog, warn = load_from(path)
            self.assertIsNotNone(warn)
            self.assertEqual(prog.cleared, [])

    def test_wrong_types_are_ignored(self):
        prog, warn = restore({"format": FORMAT, "cleared": "m1_01",
                              "design_tokens": "99"})
        self.assertEqual(prog.cleared, [])
        self.assertEqual(prog.design_tokens, 0)
        self.assertIsNotNone(warn)

    def test_negative_tokens_clamped(self):
        prog, _ = restore({"format": FORMAT, "cleared": [], "design_tokens": -500})
        self.assertEqual(prog.design_tokens, 0)

    def test_duplicate_and_non_string_cleared_filtered(self):
        prog, _ = restore({"format": FORMAT,
                           "cleared": ["m1_01", "m1_01", 42, None, "m1_02"]})
        self.assertEqual(prog.cleared, ["m1_01", "m1_02"])

    def test_bom_file_is_tolerated(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bom.json"
            path.write_bytes(b"\xef\xbb\xbf" + json.dumps(
                {"format": FORMAT, "cleared": ["m1_01"], "design_tokens": 5}
            ).encode("utf-8"))
            prog, warn = load_from(path)
            self.assertIsNone(warn, "带 BOM 的存档应当被容忍")
            self.assertEqual(prog.cleared, ["m1_01"])


class SecurityTests(unittest.TestCase):
    def test_unlocked_is_rederived_not_trusted(self):
        """手改 JSON 不能白拿解锁：unlocked 只由 cleared 推导。"""
        forged = {
            "format": FORMAT,
            "cleared": [],                      # 一关没通
            "design_tokens": 999999,
            "unlocked": ["全部", "伪造的"],       # 伪造字段
        }
        prog, _ = restore(forged)
        self.assertNotIn("全部", prog.unlocked)
        self.assertNotIn("伪造的", prog.unlocked)
        self.assertEqual(prog.unlocked, set(PHASES["P1"].unlocks))

    def test_cleared_m3_unlocks_p3(self):
        prog, _ = restore({"format": FORMAT, "cleared": ["m3_01"],
                           "design_tokens": 0})
        self.assertTrue(set(PHASES["P3"].unlocks).issubset(prog.unlocked))


if __name__ == "__main__":
    unittest.main()
