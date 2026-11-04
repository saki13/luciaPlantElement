# -*- coding: utf-8 -*-
"""`board.step` 逐步一致性门禁（E-02）：把整局模拟的每一步状态与基线逐字段比对。

与 check_calibration 的区别：那边比的是聚合指标（胜率/时长），这边比的是
**每一步的行/坐标/血量/弹道**，所以"某一步算错但最后结果碰巧一样"的 bug 也能抓到。
改动引擎后需要显式 --update 重新基线化，和 calibration 一样。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame.engine.trace import TRACE_FORMAT, run_all  # noqa: E402

DEFAULT_BASELINE = ROOT / "reports" / "board_trace_baseline.json"


def first_diff(a: list, b: list) -> tuple[int, dict | None, dict | None]:
    """返回第一个不同的下标与两侧元素。"""
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return i, a[i], b[i]
    if len(a) != len(b):
        long_side = a if len(a) > len(b) else b
        return min(len(a), len(b)), None, long_side[min(len(a), len(b))]
    return -1, None, None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="重新生成基线")
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE))
    ap.add_argument("--godot-exe", default="",
                    help="给了就同时跑 GDScript 侧的逐步比对")
    args = ap.parse_args(argv)

    baseline_path = Path(args.baseline)
    current = run_all()

    if args.update or not baseline_path.exists():
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
        total = sum(s["steps"] for s in current["scenarios"].values())
        print(f"baseline written: {baseline_path}  "
              f"({len(current['scenarios'])} 场景 / {total} 步)")
        return 0

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if baseline.get("format") != TRACE_FORMAT:
        print(f"RESULT: FAIL（基线 format={baseline.get('format')!r} 与当前 {TRACE_FORMAT!r} 不一致）")
        return 1

    fails = []
    base_sc = baseline.get("scenarios", {})
    cur_sc = current["scenarios"]

    if set(base_sc) != set(cur_sc):
        fails.append(f"场景集合变了：新增 {sorted(set(cur_sc) - set(base_sc))}，"
                     f"缺失 {sorted(set(base_sc) - set(cur_sc))}")

    for name in sorted(set(base_sc) & set(cur_sc)):
        b, c = base_sc[name], cur_sc[name]
        if b["steps"] != c["steps"]:
            fails.append(f"{name}: 步数 {b['steps']} -> {c['steps']}")
            continue
        idx, bf, cf = first_diff(b["frames"], c["frames"])
        if idx >= 0:
            fails.append(f"{name}: 第 {idx} 步起不一致")
            if bf is not None and cf is not None:
                for k in sorted(set(bf) | set(cf)):
                    if bf.get(k) != cf.get(k):
                        fails.append(f"    {k}: {bf.get(k)} -> {cf.get(k)}")

    total = sum(s["steps"] for s in cur_sc.values())
    if fails:
        print(f"RESULT: FAIL（{len(fails)} 处偏差）")
        for f in fails[:20]:
            print(f"  - {f}")
        return 1
    print(f"RESULT: PASS（{len(cur_sc)} 场景 / {total} 步逐步一致）")

    if args.godot_exe:
        return _run_godot(args.godot_exe, total)
    return 0


def _run_godot(exe: str, total: int) -> int:
    """把 trace 同步给 Godot 项目，再跑 GDScript 侧的逐步比对。"""
    import shutil
    import subprocess

    exe_path = Path(exe)
    if not exe_path.exists():
        print(f"RESULT: SKIP（找不到 Godot：{exe}）")
        return 0
    dst = ROOT / "godot" / "tests" / "golden_board_trace.json"
    shutil.copyfile(DEFAULT_BASELINE, dst)
    proc = subprocess.run(
        [str(exe_path), "--headless", "--path", str(ROOT / "godot"),
         "--script", "res://tests/run_board_trace.gd"],
        capture_output=True, text=True, timeout=300,
        encoding="utf-8", errors="replace")
    tail = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()][-6:]
    for ln in tail:
        print(f"  [godot] {ln}")
    if proc.returncode == 0:
        print(f"GODOT_PORT: PASS（GDScript 侧与 {total} 步 Python trace 逐步一致）")
        return 0
    print("GODOT_PORT: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
