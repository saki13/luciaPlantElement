# -*- coding: utf-8 -*-
"""关卡运行器：data/levels/*.json -> 出怪表 -> Simulation，headless 与未来真机共用。

关卡 JSON schema：
{
  "key","phase","name","cn",
  "start_resource":100, "max_seconds":300,
  "card_pool":["sunbloom", ...],
  "spawn": {
     "mode":"budget", "waves":10, "allowed":["normal", ...],
     "first_spawn_at":12, "cap_base":2, "cap_grow":1, "cap_max":6
   } | {
     "mode":"fixed", "entries":[[t,"key"], ...], "rows":[1,2,...]
   },
  "reward":{"design_tokens":0, "unlock":[]}
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..engine.board import Simulation
from ..engine.bot import RuleBot
from ..engine.wavegen import build_schedule, fixed_schedule


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_levels(levels_dir: str | Path) -> Dict[str, Dict[str, Any]]:
    levels_dir = Path(levels_dir)
    out: Dict[str, Dict[str, Any]] = {}
    if not levels_dir.exists():
        return out
    for p in sorted(levels_dir.glob("*.json")):
        d = _read_json(p)
        out[d["key"]] = d
    return out


def build_schedule_from_level(level: Dict[str, Any], enemy_defs: Dict[str, Dict[str, Any]],
                              seed: int):
    sp = level["spawn"]
    if sp["mode"] == "fixed":
        return fixed_schedule([(float(t), k) for t, k in sp["entries"]], sp.get("rows"))
    cap_base = int(sp.get("cap_base", 2))
    cap_grow = int(sp.get("cap_grow", 1))
    cap_max = int(sp.get("cap_max", 6))
    return build_schedule(
        enemy_defs, int(sp["waves"]), seed,
        allowed=sp.get("allowed"),
        first_spawn_at=float(sp.get("first_spawn_at", 12.0)),
        wave_cap_fn=lambda w, b=cap_base, g=cap_grow, m=cap_max: min(m, b + g * w),
    )


def run_level(level: Dict[str, Any], reg, card_pool: Optional[Sequence[str]] = None,
              seed: int = 1000, smart: bool = True, bot: Optional[RuleBot] = None):
    """跑一关并返回 (Simulation, metrics)。card_pool 默认取关卡声明，bot 可注入自定义。"""
    pool = list(card_pool if card_pool is not None else level["card_pool"])
    sched = build_schedule_from_level(level, reg.enemies, seed)
    sim = Simulation(reg.plants, reg.enemies, sched, pool, seed=seed,
                     start_resource=int(level.get("start_resource", 100)),
                     max_seconds=float(level.get("max_seconds", 300)),
                     rescue=bool(level.get("rescue", False)))
    actor = bot or RuleBot(pool, smart=smart)
    metrics = sim.run_to_end(actor)
    return sim, metrics
