# -*- coding: utf-8 -*-
"""波次预算生成：把 8+4×w 预算点展开成确定性 spawn 时间表 (t, enemy_key, row)。"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import config as C

Schedule = List[Tuple[float, str, Optional[int]]]


def unlock_for_wave(w: int) -> Dict[str, int]:
    """第 w 波（0 起）可出的怪与权重，对齐 v0.2 §15 解锁节奏。"""
    pool: Dict[str, int] = {"normal": 3, "fast": 2}
    if w >= 2:
        pool["cone"] = 2
    if w >= 4:
        pool["bucket"] = 1
    if w >= 9:
        pool["giant"] = 1
    return pool


def build_schedule(enemy_defs: Dict[str, Dict[str, Any]], waves: int, seed: int,
                   spawn_gap: float = C.SPAWN_GAP, wave_gap: float = C.WAVE_GAP,
                   extra_pool: Optional[Sequence[str]] = None,
                   allowed: Optional[Sequence[str]] = None,
                   first_spawn_at: float = 12.0,
                   wave_cap_fn=None) -> Schedule:
    """把威胁预算展开成时间表。

    预算是【上限】而非必须花满：新手期每波出怪数受 cap 约束（默认 3+w），
    避免把整波预算全兑成 budget1 小怪造成刷屏；无尽模式可传更大的 wave_cap_fn 放量。
    allowed 给出怪白名单：新手主线据此隔离铁桶/巨人/盾兵等中后期怪物。
    """
    rng = random.Random(seed)
    out: Schedule = []
    t = float(first_spawn_at)
    cap_fn = wave_cap_fn or (lambda w: 3 + w)
    allowed_set = set(allowed) if allowed else None
    for w in range(waves):
        pool = unlock_for_wave(w)
        for k in (extra_pool or []):
            pool.setdefault(k, 1)
        if allowed_set is not None:
            pool = {k: wt for k, wt in pool.items() if k in allowed_set}
        # 前两波单路教学，随后每两波多开一路，到 w8 铺满 5 行
        active_rows = min(C.ROWS, 1 + w // 2)
        # 旗手不占预算，波首标记
        if "banner" in enemy_defs:
            out.append((round(t, 2), "banner", rng.randrange(active_rows)))
        budget = 8 + 4 * w
        cap = int(cap_fn(w))
        count = 0
        wave_clock = 0.0
        while budget > 0 and count < cap:
            afford = {k: wt for k, wt in pool.items()
                      if enemy_defs[k]["budget"] <= budget}
            if not afford:
                break
            keys = list(afford.keys())
            pick = rng.choices(keys, weights=[afford[k] for k in keys], k=1)[0]
            out.append((round(t + wave_clock, 2), pick, rng.randrange(active_rows)))
            budget -= enemy_defs[pick]["budget"]
            wave_clock += spawn_gap
            count += 1
        # 估算本波时长后跳到下一波
        t += max(6.0, wave_clock) + wave_gap
    return sorted(out, key=lambda z: z[0])


def fixed_schedule(entries: Sequence[Tuple[float, str]], rows: Optional[Sequence[int]] = None) -> Schedule:
    """关卡脚本直指定点出怪：entries=[(t,key),...]，rows 等长或为空（随机行）。"""
    rows = list(rows) if rows else [None] * len(entries)
    return [(round(float(t), 2), key, rows[i]) for i, (t, key) in enumerate(entries)]
