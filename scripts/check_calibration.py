# -*- coding: utf-8 -*-
"""校准基线闸门：挡住"改了引擎但没人发现胜率变了"。

`headless_run` 的 100 局回归只把结果写进 `reports/headless_<时间戳>.json`，
没有任何断言。谁动了 `bot.py` / `board.py` / `config.py`，胜率可能悄悄变化而无人察觉。

本脚本用**固定 seed 子集**跑回归，与 `reports/calibration_baseline.json` 逐字段精确比对。
引擎是确定性的（同 seed 结果完全一致），所以这里**不需要容差**——任何偏差都说明
数值或节奏真的变了，必须显式重新基线化。

用法：
    python scripts/check_calibration.py            # 校验（CI / check_all 用）
    python scripts/check_calibration.py --update   # 确认改动符合预期后重新基线化
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame.engine.loader import load_registry  # noqa: E402
from tdgame.headless_run import DATA, build_scenes  # noqa: E402

BASELINE = ROOT / "reports" / "calibration_baseline.json"
FORMAT = "pvz-calibration-baseline/1"
DEFAULT_RUNS = 20

# 这些字段变了就说明平衡/节奏动了
FIELDS = ["win_rate", "clean_win_rate", "avg_mowers_used", "avg_breaches",
          "avg_lives_left", "avg_sun_left", "avg_duration"]


def run_scenes(runs: int) -> Dict[str, Dict[str, Any]]:
    reg = load_registry(DATA)
    if reg.errors:
        raise SystemExit(f"loader errors: {reg.errors}")
    out: Dict[str, Dict[str, Any]] = {}
    for scene in build_scenes(reg, runs):
        out[scene["scene"]] = {f: scene[f] for f in FIELDS}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="把当前结果写成新基线")
    ap.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                    help="每个场景的局数（必须与基线一致）")
    ap.add_argument("--baseline", default=str(BASELINE),
                    help=f"基线文件路径（默认 {BASELINE}）")
    args = ap.parse_args(argv)
    baseline_path = Path(args.baseline)

    t0 = time.time()

    if args.update:
        scenes = run_scenes(args.runs)
        payload = {
            "format": FORMAT,
            "runs_per_scene": args.runs,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "note": "固定 seed 1000..(1000+runs-1)，结果确定，改动后需显式 --update 重新基线化",
            "scenes": scenes,
        }
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"baseline written: {baseline_path}  ({args.runs} runs/scene, "
              f"{time.time()-t0:.1f}s)")
        return 0

    if not baseline_path.exists():
        print(f"基线不存在：{baseline_path}\n请先跑 python scripts/check_calibration.py --update",
              file=sys.stderr)
        return 2

    base = json.loads(baseline_path.read_text(encoding="utf-8"))
    if base.get("format") != FORMAT:
        print(f"基线格式不匹配：{base.get('format')}", file=sys.stderr)
        return 2
    base_runs = int(base["runs_per_scene"])
    if args.runs != base_runs:
        print(f"--runs={args.runs} 与基线的 {base_runs} 不一致；基线是固定 seed 子集，"
              f"局数变了就无法比对", file=sys.stderr)
        return 2

    now = run_scenes(args.runs)
    expected: Dict[str, Dict[str, Any]] = base["scenes"]

    diffs = []
    for scene in sorted(set(expected) | set(now)):
        if scene not in now:
            diffs.append(f"{scene}: 场景消失")
            continue
        if scene not in expected:
            diffs.append(f"{scene}: 新增场景（基线里没有）")
            continue
        for f in FIELDS:
            got, exp = now[scene].get(f), expected[scene].get(f)
            if got != exp:
                diffs.append(f"{scene}.{f}: 现在 {got}  基线 {exp}")

    print(f"baseline : {baseline_path}  ({base_runs} runs/scene, "
          f"generated {base.get('generated_at')})")
    print(f"elapsed  : {time.time()-t0:.1f}s")
    print()
    print(f"{'scene':<18}{'win':>7}{'clean':>7}{'mower':>7}{'sunL':>9}")
    for scene in sorted(now):
        s = now[scene]
        print(f"{scene:<18}{s['win_rate']:>7.2f}{s['clean_win_rate']:>7.2f}"
              f"{s['avg_mowers_used']:>7.2f}{s['avg_sun_left']:>9.1f}")

    print()
    if diffs:
        print(f"RESULT: FAIL（{len(diffs)} 处偏差，说明平衡/节奏真的变了）")
        for d in diffs[:20]:
            print("  - " + d)
        if len(diffs) > 20:
            print(f"  ... 另有 {len(diffs)-20} 处")
        print()
        print("如果这是有意改动：python scripts/check_calibration.py --update")
        print("如果是意外：回退改动")
        return 1

    print("RESULT: PASS（与基线逐字段一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
