# -*- coding: utf-8 -*-
"""关卡自动调参器：为每关搜索 (waves, cap_max) 使「时长 >=120s 且胜率达标」。

为什么要有它：手调参数会在「加波数补时长」和「降强度保胜率」之间震荡，
38 关×5 seeds 的组合靠人肉试错不收敛。这里用确定的爬山规则：

  时长不足      -> 波数 +1
  胜率不足      -> 战力上限 -1
  胜率过高(+0.25)-> 战力上限 +1（加压，避免太软）
  两者都达标    -> 停

固定表关卡（m2_* / boss）没有波数概念，改用「时间点拉伸系数」。

输出 tdgame/data/level_tuning.json，由 gen_levels 读取并覆盖生成参数，
保证重新生成时不会丢掉调参结果。
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame.engine.loader import load_registry  # noqa: E402
from tdgame.scenarios import level_run  # noqa: E402

SEEDS = (1000, 1001, 1002, 1003)
TARGET_DUR = 120.0
MARGIN = 0.25
MAX_ITER = 10
LV = ROOT / "tdgame" / "data" / "levels"
OUT = ROOT / "tdgame" / "data" / "level_tuning.json"
REG = load_registry(ROOT / "tdgame" / "data")


def load_levels() -> dict:
    return {json.loads(f.read_text(encoding="utf-8"))["key"]:
            json.loads(f.read_text(encoding="utf-8"))
            for f in LV.glob("*.json")}


def target_win(key: str) -> float:
    """M1/M2 要求高（教学关要稳过）；M3 只要 >0.6。"""
    return 0.8 if key.startswith(("m1_", "m2_")) else 0.6


def evaluate(level: dict, pool_extra=None):
    durs, wins = [], 0
    for s in SEEDS:
        _, m = level_run.run_level(level, REG, seed=s, smart=True,
                                   card_pool=pool_extra)
        wins += bool(m.get("won"))
        durs.append(m.get("duration", 0))
    return statistics.mean(durs), wins / len(SEEDS)


def tune_budget(key: str, base: dict) -> dict:
    sp = base.setdefault("spawn", {})
    waves = int(sp.get("waves", 10))
    cap = int(sp.get("cap_max", 6))
    sp["wave_gap"] = float(sp.get("wave_gap", 13.0))
    best = None
    for _ in range(MAX_ITER):
        base["spawn"] = dict(sp, waves=waves, cap_max=cap)
        dur, win = evaluate(base)
        tw = target_win(key)
        print(f"    waves={waves} cap={cap} -> dur={dur:.0f}s win={win:.2f} (need {tw})", flush=True)
        best = {"waves": waves, "cap_max": cap, "wave_gap": sp["wave_gap"],
                "dur": round(dur, 1), "win": round(win, 2)}
        # 先保胜率，再补时长：胜率不达标时加波数只会越打越输
        if win < tw:
            if cap <= 2:
                break
            cap -= 1
            continue
        if dur < TARGET_DUR:
            waves += 1
            if waves > 40:
                break
            continue
        if win > tw + MARGIN and cap < 20:
            cap += 1
            continue
        break
    return best


def tune_fixed(key: str, base: dict) -> dict:
    """固定表关卡：拉伸时间点直到时长 >=120s。"""
    sp = base.get("spawn") or {}
    entries = sp.get("entries") or []
    if not entries:
        return {"stretch": 1.0, "dur": 0, "win": 0}
    stretch = 1.0
    best = {"stretch": 1.0, "dur": 0, "win": 0}
    for _ in range(MAX_ITER):
        new_entries = [[round(float(t) * stretch, 2), k] for t, k in entries]
        base["spawn"] = dict(sp, entries=new_entries)
        dur, win = evaluate(base)
        tw = target_win(key)
        print(f"    stretch={stretch:.2f} -> dur={dur:.0f}s win={win:.2f} (need {tw})", flush=True)
        best = {"stretch": round(stretch, 2), "dur": round(dur, 1), "win": round(win, 2)}
        if dur < TARGET_DUR:
            stretch += 0.15
            continue
        if win < tw:
            break          # 固定表不好降强度，交给上层处理
        break
    return best


def main(keys=None) -> int:
    levels = load_levels()
    tuning = {}
    if OUT.exists():
        tuning = json.loads(OUT.read_text(encoding="utf-8"))
    for key in sorted(levels):
        if keys and key not in keys:
            continue
        lv = levels[key]
        mode = (lv.get("spawn") or {}).get("mode")
        print(f"[{key}] mode={mode}", flush=True)
        try:
            r = tune_budget(key, lv) if mode == "budget" else tune_fixed(key, lv)
        except Exception as exc:                       # noqa: BLE001
            print(f"    !! {exc.__class__.__name__}: {exc}", flush=True)
            continue
        tuning[key] = r
        OUT.write_text(json.dumps(tuning, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
        print(f"  => {r}", flush=True)
    print("完成，写入", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
