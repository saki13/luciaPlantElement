# -*- coding: utf-8 -*-
"""M2 聚焦考场单局诊断：smart/dumb 终局残留、选牌与僵持原因。"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame.engine.loader import load_registry
from tdgame.engine.board import Simulation
from tdgame.engine.wavegen import fixed_schedule
from tdgame.engine.bot import RuleBot
from tdgame.headless_run import POOL_BASIC, POOL_M2, M2_ENTRIES, M2_ROWS

reg = load_registry(ROOT / "tdgame" / "data")


def run(pool, smart):
    sched = fixed_schedule(M2_ENTRIES, M2_ROWS)
    sim = Simulation(reg.plants, reg.enemies, sched, pool, seed=1000,
                     start_resource=200, max_seconds=180)
    placed, deaths = [], []
    orig_place, orig_die = sim.place_plant, None
    def hook(key, row, col):
        ok = orig_place(key, row, col)
        if ok:
            placed.append((round(sim.now, 1), key, row, col))
        return ok
    sim.place_plant = hook
    bot = RuleBot(pool, smart=smart)
    step = 0
    while not sim.over:
        bot.think(sim)
        sim.step()
        step += 1
        if step % 100 == 0:
            pk = Counter(p.key for p in sim.plants)
            ek = Counter(e.key for e in sim.enemies)
            print(f"  t={sim.now:5.0f} sun={sim.sun:4d} plants={dict(pk)} enemies={dict(ek)}")
    print(" placed:", placed)
    print(" residual enemies:", [(e.key, e.row, round(e.x, 2), round(e.hp_body, 1), e.block_flat)
                                  for e in sim.enemies])
    print(" result:", sim.metrics())
    print(" events:", sim.event_log)


for name, pool, smart in [("SMART", POOL_M2, True), ("DUMB", POOL_BASIC, False)]:
    print("====", name, "====")
    run(pool, smart)
