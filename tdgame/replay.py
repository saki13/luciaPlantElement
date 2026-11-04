# -*- coding: utf-8 -*-
"""确定性回放导出（阶段 1：Godot 只做渲染，Python 仍是唯一事实源）。

设计原则
--------
渲染层绝不能重算任何战斗公式。因此这里不导出"事件+让客户端自己积分位置"，而是导出
**按固定步长 DT 采样的完整状态快照**：Godot 在快照之间做插值即可，位置/血量/胜负全部由
本模块算好，客户端零战斗逻辑。同一 seed 导出结果字节级一致（有单测守底）。

另外附一维离散事件流（spawn/fire/die/mower/breach/place），供渲染层触发攻击动画与音效。

用法：
    python -m tdgame.replay --scene m1_day_10w --seed 1000 --out replays/m1.json
    python -m tdgame.replay --list
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

from . import config as C
from .engine.board import Simulation
from .engine.bot import RuleBot
from .engine.loader import load_registry
from .engine.wavegen import build_schedule, fixed_schedule
from .headless_run import M2_ENTRIES, M2_ROWS, POOL_BASIC, POOL_LATE, POOL_M2

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tdgame" / "data"

FORMAT = "pvz-replay/1"
FRAME_BUDGET = 20000

# 与 animation.py / build_spritesheet.py 的固定网格约定保持一致
ANIM_SPEC = {
    "order": ["idle", "walk", "attack", "hurt"],
    "rows": {"idle": 0, "walk": 1, "attack": 2, "hurt": 3},
    "frames": {"idle": 2, "walk": 4, "attack": 3, "hurt": 2},
    "frame_ms": {"idle": 460, "walk": 130, "attack": 150, "hurt": 160},
    "loop": {"idle": True, "walk": True, "attack": False, "hurt": False},
    "frame_px": 64,
    "cols": 4,
}


# ---------------------------------------------------------------- 场景定义
def _scene_specs(reg, seed: int) -> Dict[str, Dict[str, Any]]:
    """复用 headless_run 的场景常量，避免两处维护。"""
    m1_allowed = ["normal", "fast", "banner", "cone"]
    return {
        "m1_day_10w": dict(
            sched=build_schedule(reg.enemies, 10, seed, allowed=m1_allowed,
                                 wave_cap_fn=lambda w: min(6, 2 + w)),
            pool=POOL_BASIC, start=C.START_RESOURCE, max_seconds=400.0, smart=True,
            note="新手主线 10 波",
        ),
        "m2_shield_smart": dict(
            sched=fixed_schedule(M2_ENTRIES, M2_ROWS),
            pool=POOL_M2, start=200, max_seconds=180.0, smart=True,
            note="格挡考场（带破盾）",
        ),
        "m2_shield_dumb": dict(
            sched=fixed_schedule(M2_ENTRIES, M2_ROWS),
            pool=POOL_BASIC, start=200, max_seconds=180.0, smart=False,
            note="格挡考场（纯直射，应被卡死）",
        ),
        "boss50_late": dict(
            sched=fixed_schedule([(8.0, "normal"), (14.0, "cone"),
                                  (20.0, "bucket"), (28.0, "boss_50"),
                                  (46.0, "cone"), (60.0, "bucket")]),
            pool=POOL_LATE, start=800, max_seconds=320.0, smart=True,
            note="50 轮 Boss 门槛（高配）",
        ),
        "endless_25w": dict(
            sched=build_schedule(reg.enemies, 25, seed,
                                 wave_cap_fn=lambda w: min(10, 3 + w // 2)),
            pool=POOL_LATE, start=100, max_seconds=400.0, smart=True,
            note="无尽中程 25 波",
        ),
    }


SCENE_NAMES = ["m1_day_10w", "m2_shield_smart", "m2_shield_dumb", "boss50_late", "endless_25w"]


# ---------------------------------------------------------------- 采样
def _uid(obj, counter: List[int]) -> int:
    u = getattr(obj, "_replay_uid", None)
    if u is None:
        counter[0] += 1
        u = counter[0]
        obj._replay_uid = u
    return u


def _snapshot(sim: Simulation, counter: List[int]) -> Dict[str, Any]:
    """一帧完整状态。字段用紧凑数组，键名在文件头 anim/meta 里约定。"""
    plants = []
    for p in sim.plants:
        hp = int(round(100 * (p.hp / p.hp_max if p.hp_max else 0)))
        # 第 6 位是累计出手次数：渲染层对它做差分即可精确触发 attack 动画
        plants.append([_uid(p, counter), p.row, p.col, p.key, max(0, hp),
                       p.shot_count + p.strike_count])
    enemies = []
    for e in sim.enemies:
        bod = int(round(100 * (e.hp_body / e.hp_body_max if e.hp_body_max else 0)))
        arm = int(round(100 * (e.armor_hp / e.armor_hp_max))) if e.armor_hp_max else -1
        enemies.append([_uid(e, counter), e.row, round(e.x, 3), e.key, max(0, bod),
                        arm, 1 if e.eating is not None else 0])
    projs = []
    for pr in sim.projectiles:
        projs.append([pr.row, round(pr.x, 3), str(pr.spec.get("key", pr.owner_key)),
                      round(pr.speed, 2)])
    return {
        "t": round(sim.now, 2),
        "sun": sim.sun,
        "lives": sim.lives,
        "m": [1 if sim.mowers.get(r, False) else 0 for r in range(C.ROWS)],
        "p": plants,          # [uid, row, col, key, hp%, shots]
        "e": enemies,         # [uid, row, x_cells, key, body%, armor%(-1 无甲), eating]
        "b": projs,           # [row, x_cells, key, speed_cells_per_sec]
    }


def _events(prev: Dict[str, Any], cur: Dict[str, Any], t: float) -> List[List[Any]]:
    """由相邻快照的差集推导离散事件，供渲染层触发攻击动画/音效。"""
    out: List[List[Any]] = []
    prev_e = {d[0]: d for d in prev["e"]}
    cur_e = {d[0]: d for d in cur["e"]}
    for uid, d in cur_e.items():
        if uid not in prev_e:
            out.append(["spawn", round(t, 2), d[1], d[3]])
    for uid, d in prev_e.items():
        if uid not in cur_e:
            out.append(["die", round(t, 2), d[1], d[3]])
    prev_p = {d[0] for d in prev["p"]}
    for d in cur["p"]:
        if d[0] not in prev_p:
            out.append(["place", round(t, 2), d[1], d[3], d[2]])
    # 新弹道总是追加在列表尾部，前 n_prev 个是本帧之前就存在的
    n_prev, n_cur = len(prev["b"]), len(cur["b"])
    if n_cur > n_prev:
        for d in cur["b"][n_prev:]:
            out.append(["fire", round(t, 2), d[0], d[2]])
    for row in range(C.ROWS):
        if prev["m"][row] == 1 and cur["m"][row] == 0:
            out.append(["mower", round(t, 2), row])
    if cur["lives"] < prev["lives"]:
        out.append(["breach", round(t, 2), cur["lives"]])
    return out


def record(reg, scene: str, seed: int = 1000) -> Dict[str, Any]:
    spec = _scene_specs(reg, seed)[scene]
    sim = Simulation(reg.plants, reg.enemies, spec["sched"], spec["pool"], seed=seed,
                     start_resource=spec["start"], max_seconds=spec["max_seconds"])
    bot = RuleBot(spec["pool"], smart=spec["smart"])
    counter = [0]
    frames: List[Dict[str, Any]] = [_snapshot(sim, counter)]
    events: List[List[Any]] = []
    steps = 0
    while not sim.over and steps < FRAME_BUDGET:
        bot.think(sim)
        sim.step(C.DT)
        cur = _snapshot(sim, counter)
        events.extend(_events(frames[-1], cur, sim.now))
        frames.append(cur)
        steps += 1

    units: Dict[str, Any] = {}
    for key, d in reg.plants.items():
        units[key] = {"kind": "plant", "cn": d.get("cn", key), "sun": int(d.get("sun", 0))}
    for key, d in reg.enemies.items():
        units[key] = {"kind": "enemy", "cn": d.get("cn", key),
                      "hp": int(d.get("hp_body", 0))}

    return {
        "format": FORMAT,
        "meta": {
            "scene": scene,
            "note": spec["note"],
            "seed": seed,
            "dt": C.DT,
            "rows": C.ROWS,
            "cols": C.COLS,
            "layout": {"cell_px": C.CELL, "top_h": C.TOP_H, "gutter_px": C.BOARD_GUTTER},
            "smart": spec["smart"],
            "card_pool": list(spec["pool"]),
            "won": sim.won,
            "duration": round(sim.now, 2),
            "ticks": len(frames),
            "metrics": sim.metrics(),
        },
        "anim": ANIM_SPEC,
        "units": units,
        "frames": frames,
        "events": events,
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="m1_day_10w")
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--out", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--indent", type=int, default=0, help="0 = 紧凑单行（体积最小）")
    args = ap.parse_args(argv)

    if args.list:
        for n in SCENE_NAMES:
            print(n)
        return 0

    if args.scene not in SCENE_NAMES:
        print(f"unknown scene {args.scene}; choose from {SCENE_NAMES}", file=sys.stderr)
        return 2

    reg = load_registry(DATA)
    if reg.errors:
        print(f"loader errors: {reg.errors}", file=sys.stderr)
        return 3

    rep = record(reg, args.scene, args.seed)
    out = Path(args.out) if args.out else ROOT / "replays" / f"{args.scene}_s{args.seed}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.indent:
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=args.indent), encoding="utf-8")
    else:
        out.write_text(json.dumps(rep, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")

    m = rep["meta"]
    size_kb = out.stat().st_size / 1024
    print(f"scene={m['scene']} seed={m['seed']} won={m['won']} "
          f"duration={m['duration']}s ticks={m['ticks']} "
          f"frames={len(rep['frames'])} events={len(rep['events'])} size={size_kb:.1f}KB")
    print("saved:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
