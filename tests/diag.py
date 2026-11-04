# -*- coding: utf-8 -*-
"""诊断：时间线快照 + 单行靶场，定位 headless 失守根因。"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame import config as C
from tdgame.engine.loader import load_registry
from tdgame.engine.board import Simulation
from tdgame.engine.entities import Enemy
from tdgame.engine.wavegen import build_schedule
from tdgame.engine.bot import RuleBot
from tdgame.headless_run import POOL_BASIC

reg = load_registry(ROOT / "tdgame" / "data")


def timeline():
    print("==== m1 10w 单局时间线 (seed1000, 新手白名单/新节奏) ====")
    allowed = ["normal", "fast", "banner", "cone"]
    sched = build_schedule(reg.enemies, 10, 1000, allowed=allowed,
                           wave_cap_fn=lambda w: min(6, 2 + w))
    sim = Simulation(reg.plants, reg.enemies, sched, POOL_BASIC, seed=1000, max_seconds=200)
    placed = []
    orig = sim.place_plant
    def hook(key, row, col):
        ok = orig(key, row, col)
        if ok:
            placed.append((round(sim.now, 1), key, row, col, sim.sun))
        return ok
    sim.place_plant = hook
    bot = RuleBot(POOL_BASIC, smart=True)
    step = 0
    while not sim.over:
        bot.think(sim)
        sim.step()
        step += 1
        if step % 50 == 0:
            pk = Counter(p.key for p in sim.plants)
            ek = Counter(e.key for e in sim.enemies)
            print(f"t={sim.now:6.1f} sun={sim.sun:4d} plants={dict(pk)} enemies={dict(ek)} "
                  f"mowers={sum(1 for v in sim.mowers.values() if not v)} lives={sim.lives}")
    print("place events (t,key,row,col,sun_after):", placed)
    print("END", sim.metrics())
    print("events:", sim.event_log)


def firing_range():
    print("\n==== 单行靶场：1 株 peashooter(col2) vs 1 只 normal，无墙 ====")
    sim = Simulation(reg.plants, reg.enemies, [], POOL_BASIC, seed=1, max_seconds=200,
                     sky_sun=False)
    sim.sun = 999
    assert sim.place_plant("peashooter", 0, 2)
    e = Enemy("normal", 0, reg.enemies["normal"], C.COLS + 0.5)
    sim.enemies.append(e)
    shots0 = 0
    plant = sim.plant_at(0, 2)
    steps = 0
    while not e.dead and steps < 2000:
        before = plant.shot_count
        sim.step()
        if plant.shot_count > before:
            shots0 += 1
        steps += 1
    print(f"enemy dead={e.dead} at x={e.x:.2f}, shots_fired={shots0}, time={sim.now:.1f}s, "
          f"plant hp={plant.hp:.0f}")


def economy_check():
    print("\n==== 纯经济：两株向阳花+天降，60s 阳光产出（用远端怪防止空表即胜）====")
    sched = [(300.0, "normal")]
    from tdgame.engine.wavegen import fixed_schedule
    sim = Simulation(reg.plants, reg.enemies, fixed_schedule(sched), ["sunbloom"], seed=1,
                     max_seconds=120)
    sim.place_plant("sunbloom", 0, 0)
    sim.cooldown_left.clear()
    sim.place_plant("sunbloom", 1, 0)
    for _ in range(int(60 / C.DT)):
        sim.step()
    print("60s sun_earned (2 sunbloom + sky):", sim.sun_earned, "sun now:", sim.sun,
          "expect sky 150 + flowers ~350")


if __name__ == "__main__":
    firing_range()
    economy_check()
    timeline()
