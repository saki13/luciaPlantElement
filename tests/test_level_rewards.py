# -*- coding: utf-8 -*-
"""关卡奖励的回归测试。

背景（真实踩过的坑）：关卡 JSON 由 `scripts/gen_levels.py` **整体重写**，
所以任何手改 JSON 加的 reward 都会在下次生成时被静默冲掉。
当时 `m3_boss` 的 460 代币 + T8 权限就这么丢了，只因为某条测试从 8 变 0 才发现。

所以这里守三件事：
1. 重新生成关卡后，每关的 reward 必须一字不变（直接复现那个 bug）。
2. 奖励的结构必须自洽（发了的植物要真实存在；待实现的要标未实现）。
3. M2 只发代币、不发植物（design §19.1）。
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LV = ROOT / "tdgame" / "data" / "levels"
PLANTS = ROOT / "tdgame" / "data" / "plants"


def snapshot() -> dict:
    out = {}
    for f in sorted(LV.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[d["key"]] = d.get("reward") or {}
    return out


def plant_defs() -> dict:
    out = {}
    for f in PLANTS.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[d["key"]] = d
    return out


class RegenerationTest(unittest.TestCase):
    def test_regenerating_levels_keeps_rewards(self):
        """核心回归：跑一遍生成器，所有 reward 必须原样保留。

        这条测试会真的执行 gen_levels.py（内容应完全相同，不会弄脏工作区）。
        它正是当初那个 bug 的复现：手改 JSON 的奖励被重新生成冲掉。
        """
        before = snapshot()
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "gen_levels.py")],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0, f"生成器失败：{proc.stderr[-400:]}")
        after = snapshot()

        self.assertEqual(set(before), set(after), "关卡集合变了")
        drift = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
        self.assertFalse(
            drift,
            "重新生成后 reward 发生了变化（说明奖励没写进生成器，手改会被冲掉）：\n"
            + "\n".join(f"  {k}: {b} -> {a}" for k, (b, a) in list(drift.items())[:5]))


class RewardIntegrityTest(unittest.TestCase):
    def test_every_level_has_a_reward(self):
        snap = snapshot()
        empty = [k for k, r in snap.items()
                 if not (r.get("plant") or r.get("plant_pending")
                         or int(r.get("design_tokens", 0) or 0) > 0)]
        self.assertFalse(empty, f"这些关卡没有任何奖励：{empty}")

    def test_plant_rewards_point_to_real_plants(self):
        snap, defs = snapshot(), plant_defs()
        missing = [f"{k}->{r['plant']}" for k, r in snap.items()
                   if r.get("plant") and r["plant"] not in defs]
        self.assertFalse(missing, f"奖励指向不存在的植物：{missing}")

    def test_pending_plants_are_marked_unimplemented(self):
        snap, defs = snapshot(), plant_defs()
        bad = []
        for k, r in snap.items():
            p = r.get("plant_pending")
            if not p:
                continue
            d = defs.get(p)
            if d is None:
                bad.append(f"{k}->{p} 不存在")
            elif d.get("_implemented") is not False:
                bad.append(f"{k}->{p} 未标 _implemented=false")
            elif not r.get("plant_pending_reason"):
                bad.append(f"{k}->{p} 缺 plant_pending_reason")
        self.assertFalse(bad, f"待实现植物标记不规范：{bad}")

    def test_no_level_has_both_plant_and_pending(self):
        bad = [k for k, r in snapshot().items() if r.get("plant") and r.get("plant_pending")]
        self.assertFalse(bad, f"同一关不能既发植物又挂待实现：{bad}")

    def test_m2_gives_tokens_only(self):
        """M2 定位是教定制器与能力机制，不发预设植物。"""
        bad = [k for k, r in snapshot().items()
               if k.startswith("m2_") and (r.get("plant") or r.get("plant_pending"))]
        self.assertFalse(bad, f"M2 不该发植物：{bad}")

    def test_m3_boss_grants_t8_permission(self):
        r = snapshot()["m3_boss"]
        self.assertEqual(r.get("unlock_tier"), 8)
        self.assertEqual(r.get("design_tokens"), 460,
                         "460 是对 balance 净额公式穷举出的最便宜 T8，改了要重新核算")


if __name__ == "__main__":
    unittest.main()
