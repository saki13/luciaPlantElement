# -*- coding: utf-8 -*-
"""关卡回归闸门：让 `data/levels/*.json` 真正被模拟过。

问题背景：`headless_run` 只跑代码里手搓的场景，完全不读 `levels/`。全仓库只有
`tests/test_scenarios.py` 加载过 18 个关卡，且只跑了 `m1_01` 和 `m2_shield`。
剩下 16 关**从未被模拟过**，平衡性无从得知。

本脚本遍历所有关卡，每关用固定 seed 子集跑一遍，与 `reports/levels_baseline.json`
逐字段比对。引擎确定性，同 seed 结果完全一致，因此不需要容差。

用法：
    python scripts/check_levels.py              # 校验
    python scripts/check_levels.py --update     # 确认改动后重新基线化
    python scripts/check_levels.py --baseline X # 指定基线路径
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame.engine.loader import load_registry  # noqa: E402
from tdgame.scenarios.level_run import load_levels, run_level  # noqa: E402

DATA = ROOT / "tdgame" / "data"
BASELINE = ROOT / "reports" / "levels_baseline.json"
FORMAT = "pvz-levels-baseline/1"
DEFAULT_SEEDS = 5
SEED0 = 1000

FIELDS = ["win_rate", "clean_win_rate", "avg_mowers_used", "avg_breaches",
          "avg_lives_left", "avg_sun_left", "avg_duration"]


def run_all(seeds: int) -> Dict[str, Dict[str, Any]]:
    reg = load_registry(DATA)
    if reg.errors:
        raise SystemExit(f"loader errors: {reg.errors}")
    levels = load_levels(DATA / "levels")
    if not levels:
        raise SystemExit("没有读到任何关卡：tdgame/data/levels/")

    out: Dict[str, Dict[str, Any]] = {}
    for key in sorted(levels):
        lv = levels[key]
        ms = []
        for i in range(seeds):
            _, m = run_level(lv, reg, seed=SEED0 + i)
            ms.append(m)
        wins = [m for m in ms if m["won"]]
        out[key] = {
            "phase": lv.get("phase"),
            "spawn_mode": (lv.get("spawn") or {}).get("mode"),
            "win_rate": round(len(wins) / len(ms), 4),
            "clean_win_rate": round(sum(1 for m in wins if m["mowers_used"] == 0) / len(ms), 4),
            "avg_mowers_used": round(statistics.fmean(m["mowers_used"] for m in ms), 3),
            "avg_breaches": round(statistics.fmean(m["breaches"] for m in ms), 3),
            "avg_lives_left": round(statistics.fmean(m["lives_left"] for m in ms), 3),
            "avg_sun_left": round(statistics.fmean(m["sun_left"] for m in ms), 2),
            "avg_duration": round(statistics.fmean(m["duration"] for m in ms), 3),
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    ap.add_argument("--baseline", default=str(BASELINE))
    args = ap.parse_args(argv)
    baseline_path = Path(args.baseline)

    t0 = time.time()

    if args.update:
        levels = run_all(args.seeds)
        payload = {
            "format": FORMAT,
            "seeds_per_level": args.seeds,
            "seed_base": SEED0,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "note": "智能 Bot 全卡池，固定 seed 子集；结果确定，改动后需显式 --update",
            "levels": levels,
        }
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"baseline written: {baseline_path}  ({len(levels)} 关 x {args.seeds} seeds, "
              f"{time.time()-t0:.1f}s)")
        return 0

    if not baseline_path.exists():
        print(f"基线不存在：{baseline_path}\n请先跑 --update", file=sys.stderr)
        return 2
    base = json.loads(baseline_path.read_text(encoding="utf-8"))
    if base.get("format") != FORMAT:
        print(f"基线格式不匹配：{base.get('format')}", file=sys.stderr)
        return 2
    if args.seeds != int(base["seeds_per_level"]):
        print(f"--seeds={args.seeds} 与基线的 {base['seeds_per_level']} 不一致",
              file=sys.stderr)
        return 2

    now = run_all(args.seeds)
    expected: Dict[str, Dict[str, Any]] = base["levels"]

    diffs = []
    for key in sorted(set(expected) | set(now)):
        if key not in expected:
            diffs.append(f"{key}: 新增关卡（基线里没有）")
            continue
        if key not in now:
            diffs.append(f"{key}: 关卡消失")
            continue
        for f in FIELDS:
            if now[key].get(f) != expected[key].get(f):
                diffs.append(f"{key}.{f}: 现在 {now[key].get(f)}  基线 {expected[key].get(f)}")

    print(f"baseline : {baseline_path}  ({base['seeds_per_level']} seeds/level, "
          f"generated {base.get('generated_at')})")
    print(f"elapsed  : {time.time()-t0:.1f}s")
    print()
    print(f"{'level':<12}{'phase':<7}{'mode':<8}{'win':>6}{'clean':>7}{'mower':>7}{'sunL':>8}{'dur':>8}")
    for key in sorted(now):
        s = now[key]
        print(f"{key:<12}{str(s['phase']):<7}{str(s['spawn_mode']):<8}"
              f"{s['win_rate']:>6.2f}{s['clean_win_rate']:>7.2f}"
              f"{s['avg_mowers_used']:>7.2f}{s['avg_sun_left']:>8.1f}{s['avg_duration']:>8.1f}")

    # 健康提示（不参与闸门判定，但值得一眼看到）
    dead = [k for k in sorted(now) if now[k]["win_rate"] <= 0.0]
    easy = [k for k in sorted(now) if now[k]["win_rate"] >= 1.0]
    print()
    if dead:
        print(f"[提示] 智能 Bot 胜率 0 的关卡（疑似不可通关）：{', '.join(dead)}")
    if easy:
        print(f"[提示] 智能 Bot 100% 通关的关卡（可能过易）：{', '.join(easy)}")

    print()
    if diffs:
        print(f"RESULT: FAIL（{len(diffs)} 处偏差）")
        for d in diffs[:20]:
            print("  - " + d)
        if len(diffs) > 20:
            print(f"  ... 另有 {len(diffs)-20} 处")
        print("\n有意改动：python scripts/check_levels.py --update")
        return 1
    print("RESULT: PASS（与基线逐字段一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
