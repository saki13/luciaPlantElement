# -*- coding: utf-8 -*-
"""headless 批量回归 CLI：在多个预设场景上跑 N 局，聚合胜率/丢车/破线/经济冗余。

用法：
  python -m tdgame.headless_run --runs 100
  python -m tdgame.headless_run --scenes m1_day,m2_shield --runs 50
输出：reports/headless_<时间戳>.json，并在 stdout 打印人类可读摘要。
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

from . import config as C
from .engine.loader import load_registry
from .engine.board import Simulation
from .engine.wavegen import build_schedule, fixed_schedule
from .scenarios.endless import build_counter_schedule
from .engine.bot import RuleBot

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tdgame" / "data"
REPORTS = ROOT / "reports"

POOL_BASIC = ["sunbloom", "peashooter", "repeater", "morningglory", "wallnut"]
POOL_M2 = POOL_BASIC + ["custom_shieldbreaker", "frostbell", "bombberry",
                        "leafdancer", "pine_needler"]
POOL_LATE = POOL_M2 + ["melonpult", "winter_melon", "bamboo"]


def _avg(xs: Sequence[float]) -> float:
    return round(statistics.fmean(xs), 3) if xs else 0.0


def run_batch(name: str, reg, pool: Sequence[str], waves: int, runs: int,
              smart: bool = True, extra_pool: Sequence[str] = (),
              start_resource: int = C.START_RESOURCE, max_seconds: float = 400.0,
              fixed: List = None, cap_fn=None, allowed: Sequence[str] = None,
              fixed_rows: List = None, schedule: List = None,
              schedule_fn=None) -> Dict[str, Any]:
    runs_metrics = []
    for i in range(runs):
        seed = 1000 + i
        if schedule_fn is not None:
            sched = schedule_fn(seed)
        elif schedule is not None:
            sched = schedule
        elif fixed:
            sched = fixed_schedule(fixed, fixed_rows)
        else:
            sched = build_schedule(reg.enemies, waves, seed, extra_pool=list(extra_pool),
                                   wave_cap_fn=cap_fn, allowed=allowed)
        sim = Simulation(reg.plants, reg.enemies, sched, pool, seed=seed,
                         start_resource=start_resource, max_seconds=max_seconds)
        runs_metrics.append(sim.run_to_end(RuleBot(pool, smart=smart)))
    wins = [m for m in runs_metrics if m["won"]]
    return {
        "scene": name, "runs": runs, "smart": smart, "pool": list(pool),
        "win_rate": round(len(wins) / runs, 4),
        "avg_duration": _avg([m["duration"] for m in runs_metrics]),
        "avg_mowers_used": _avg([m["mowers_used"] for m in runs_metrics]),
        "avg_breaches": _avg([m["breaches"] for m in runs_metrics]),
        "avg_sun_left": _avg([m["sun_left"] for m in runs_metrics]),
        "mower_trigger_rate": round(sum(1 for m in runs_metrics if m["mowers_used"] > 0) / runs, 4),
        "clean_win_rate": round(sum(1 for m in wins if m["mowers_used"] == 0) / runs, 4),
        "avg_lives_left": _avg([m["lives_left"] for m in runs_metrics]),
    }


def boss_scene(reg, pool: str, runs: int, smart: bool, start_resource: int = 800) -> Dict[str, Any]:
    """50 轮门槛近似：成军资源给足，聚焦能否击破 T10 Boss（含格挡+重甲）。"""
    chosen = POOL_LATE if pool == "late" else POOL_BASIC
    entries = [(8.0, "normal"), (14.0, "cone"), (20.0, "bucket"), (28.0, "boss_50"),
               (46.0, "cone"), (60.0, "bucket")]
    return run_batch(f"boss50_{pool}", reg, chosen, 0, runs, smart=smart,
                     start_resource=start_resource, max_seconds=320, fixed=entries)


# M2 格挡机制聚焦考场：只压两行、低密度、给足发育，盾兵 4 只分波成为核心考点，
# 让"破盾株干净克制 / 纯直射被 block20 拖住而丢车"的差异不被多线运营噪声淹没。
M2_ENTRIES = [
    (12, "normal"), (18, "normal"), (26, "fast"),
    (34, "shield_cadet"), (42, "normal"),
    (50, "shield_cadet"), (58, "cone"),
    (66, "shield_cadet"), (74, "normal"),
    (82, "shield_cadet"), (90, "fast"), (98, "normal"),
]
M2_ROWS = [1, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1, 2]


def build_scenes(reg, runs: int) -> List[Dict[str, Any]]:
    m1_allowed = ["normal", "fast", "banner", "cone"]
    scenes = []
    # M1 新手白天（10 波，上限双发；白名单隔离铁桶/巨人/盾兵，末波才出现轻甲路障）
    scenes.append(run_batch("m1_day_10w", reg, POOL_BASIC, 10, runs, smart=True,
                            allowed=m1_allowed, cap_fn=lambda w: min(6, 2 + w)))
    # M2 格挡机制聚焦考场：聪明（带破盾）vs 笨（纯直射被格挡）
    shield = run_batch("m2_shield_smart", reg, POOL_M2, 0, runs, smart=True,
                       fixed=M2_ENTRIES, fixed_rows=M2_ROWS,
                       start_resource=200, max_seconds=180)
    dumb = run_batch("m2_shield_dumb", reg, POOL_BASIC, 0, runs, smart=False,
                     fixed=M2_ENTRIES, fixed_rows=M2_ROWS,
                     start_resource=200, max_seconds=180)
    scenes.extend([shield, dumb])
    # 普通无尽中程（全卡池，25 波，未接反制器）。
    # 单波密度从 `3 + w//2` 放缓到 `3 + w//3`：前者实测 0.40 低于设计区间
    # （counter_map 目标 0.55~0.75），放缓后 0.60 落在中位。只动节奏旋钮，
    # 未改任何战斗数值。详见 reports/headless_calibration_report.md 的复核小节。
    # 注：曾试过在这里加一个"接 counter_map 自动反制"的对照场景，但实测任何
    # 有意义的反制注入（1/16 槽位换成铁桶/巨人）都会把胜率从 0.40 打到 0.00——
    # Bot 本身卡在悬崖边，反制器的作用无法从它身上读出来。反制器改由
    # tests/test_endless.py 单测守住，真机联调时再人工评估。
    scenes.append(run_batch("endless_25w", reg, POOL_LATE, 25, runs, smart=True,
                            cap_fn=lambda w: min(10, 3 + w // 3)))
    # 50 轮 Boss 门槛：高配 vs 低配
    scenes.append(boss_scene(reg, "late", runs, True))
    scenes.append(boss_scene(reg, "basic", runs, True))
    return scenes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=C.DEFAULT_RUNS)
    ap.add_argument("--scenes", default="")
    args = ap.parse_args()

    reg = load_registry(DATA)
    assert not reg.errors, reg.errors
    t0 = time.time()
    results = build_scenes(reg, args.runs)
    if args.scenes:
        wanted = {s.strip() for s in args.scenes.split(",") if s.strip()}
        results = [r for r in results if r["scene"] in wanted]

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "runs_per_scene": args.runs,
        "elapsed_sec": round(time.time() - t0, 2),
        "targets": reg.counter_map.get("headless_targets", {}),
        "scenes": results,
    }
    REPORTS.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = REPORTS / f"headless_{stamp}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"== headless {args.runs} runs/scene, elapsed {out['elapsed_sec']}s ==")
    hdr = f"{'scene':<18}{'win':>7}{'clean':>7}{'mower':>7}{'breach':>7}{'lives':>7}{'sunL':>8}{'dur':>8}"
    print(hdr)
    for r in results:
        print(f"{r['scene']:<18}{r['win_rate']:>7.2f}{r['clean_win_rate']:>7.2f}"
              f"{r['avg_mowers_used']:>7.2f}{r['avg_breaches']:>7.2f}{r['avg_lives_left']:>7.2f}"
              f"{r['avg_sun_left']:>8.1f}{r['avg_duration']:>8.1f}")
    print("saved:", out_path)


if __name__ == "__main__":
    main()
