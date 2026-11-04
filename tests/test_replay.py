# -*- coding: utf-8 -*-
"""回放导出的守底测试：确定性、schema 自洽、素材覆盖。

跑法：python -m unittest tests.test_replay
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tdgame import config as C
from tdgame.engine.loader import load_registry
from tdgame.replay import DATA, ROOT, SCENE_NAMES, record

REG = load_registry(DATA)


def _digest(rep) -> str:
    return hashlib.sha256(
        json.dumps(rep, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class TestReplayDeterminism(unittest.TestCase):
    def test_same_seed_is_byte_identical(self):
        a = record(REG, "m2_shield_smart", 1000)
        b = record(REG, "m2_shield_smart", 1000)
        self.assertEqual(_digest(a), _digest(b))

    def test_different_seed_changes_output(self):
        a = record(REG, "m2_shield_smart", 1000)
        c = record(REG, "m2_shield_smart", 1001)
        self.assertNotEqual(_digest(a), _digest(c))


class TestReplaySchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = record(REG, "m2_shield_smart", 1000)

    def test_format_and_meta(self):
        self.assertEqual(self.rep["format"], "pvz-replay/1")
        meta = self.rep["meta"]
        for k in ("scene", "seed", "dt", "rows", "cols", "won", "duration", "ticks"):
            self.assertIn(k, meta)
        self.assertEqual(meta["dt"], C.DT)
        self.assertEqual(meta["ticks"], len(self.rep["frames"]))

    def test_frames_start_at_zero_and_step_exactly_dt(self):
        frames = self.rep["frames"]
        self.assertEqual(frames[0]["t"], 0.0)
        for i in range(1, len(frames)):
            self.assertAlmostEqual(frames[i]["t"] - frames[i - 1]["t"], C.DT, places=6)

    def test_metrics_agree_with_last_frame(self):
        meta = self.rep["meta"]
        last = self.rep["frames"][-1]
        self.assertEqual(meta["won"], meta["metrics"]["won"])
        self.assertEqual(meta["metrics"]["lives_left"], max(0, last["lives"]))
        self.assertEqual(meta["duration"], last["t"])

    def test_entity_records_have_expected_arity(self):
        for f in self.rep["frames"]:
            for p in f["p"]:
                self.assertEqual(len(p), 6)     # uid,row,col,key,hp%,shots
            for e in f["e"]:
                self.assertEqual(len(e), 7)     # uid,row,x,key,body%,armor%,eating
            for b in f["b"]:
                self.assertEqual(len(b), 4)     # row,x,key,speed


class TestReplayArtCoverage(unittest.TestCase):
    def test_every_unit_has_units_entry_and_sprite(self):
        rep = record(REG, "m2_shield_smart", 1000)
        units = rep["units"]
        keys = {d[3] for f in rep["frames"] for d in f["p"]} | \
               {d[3] for f in rep["frames"] for d in f["e"]}
        self.assertTrue(keys, "replay referenced no units at all")
        for key in keys:
            self.assertIn(key, units)
            kind = units[key]["kind"]
            sub = "enemies" if kind == "enemy" else ""
            path = Path(ROOT) / "anim_demo" / "assets" / "sprites" / sub / f"{key}.png"
            self.assertTrue(path.exists(), f"missing sprite sheet for {key}: {path}")


class TestReplayScenes(unittest.TestCase):
    def test_all_scenes_record(self):
        for scene in SCENE_NAMES:
            rep = record(REG, scene, 1000)
            self.assertGreater(len(rep["frames"]), 1, scene)
            self.assertIsInstance(rep["meta"]["won"], bool)


if __name__ == "__main__":
    unittest.main()
