# -*- coding: utf-8 -*-
"""守住黄金用例与 Python 事实源不漂移。

`godot/tests/golden_resolve_hit.json` 是 GDScript 侧一致性门禁的输入。如果有人改了
`tdgame/balance.py` 却没有重新生成它，门禁就会拿旧期望去比新实现——本测试专门堵这个洞：
每次跑单测都重新算一遍，和仓库里那份逐字段比对。

失败时执行：python scripts/gen_golden_hits.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gen_golden_hits as G  # noqa: E402

from tdgame.engine.loader import load_registry  # noqa: E402

GOLDEN = ROOT / "godot" / "tests" / "golden_resolve_hit.json"


class TestGoldenSync(unittest.TestCase):
    def test_golden_file_exists(self):
        self.assertTrue(GOLDEN.exists(),
                        f"黄金用例缺失：{GOLDEN}\n请执行 python scripts/gen_golden_hits.py")

    def test_committed_golden_matches_current_python(self):
        reg = load_registry(G.DATA)
        self.assertEqual(reg.errors, [])
        fresh = G.build_cases(reg)

        committed = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(committed.get("format"), G.FORMAT)
        self.assertEqual(committed.get("case_count"), len(fresh),
                         "用例数量漂移：balance.py 改过了，请重新生成黄金用例")

        committed_ids = [c["id"] for c in committed["cases"]]
        fresh_ids = [c["id"] for c in fresh]
        self.assertEqual(committed_ids, fresh_ids)

        # 逐用例比对（失败时只报前 3 个，避免刷屏）
        diffs = []
        for got, exp in zip(committed["cases"], fresh):
            if got != exp:
                diffs.append(exp["id"])
        self.assertEqual(
            diffs[:3], [],
            f"{len(diffs)} 个用例与 Python 实现不一致（示例 {diffs[:3]}）；"
            f"请执行 python scripts/gen_golden_hits.py 重新生成")

    def test_case_count_is_substantial(self):
        # 防止有人把生成器改瘦了导致门禁形同虚设
        committed = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertGreaterEqual(committed["case_count"], 500)
        total_hits = sum(len(c["hits"]) for c in committed["cases"])
        self.assertGreaterEqual(total_hits, 500)


if __name__ == "__main__":
    unittest.main()
