# -*- coding: utf-8 -*-
"""M0 冒烟：加载注册表 -> 生成波次 -> 规则 Bot 跑一局 -> 校验确定性复现。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame.engine.loader import load_registry
from tdgame.engine.board import Simulation
from tdgame.engine.wavegen import build_schedule
from tdgame.engine.bot import RuleBot

DATA = ROOT / "tdgame" / "data"
CUSTOM = ROOT / "anim_demo" / "assets" / "plants"


def banner(t):
    print("\n=== %s ===" % t)


def main():
    reg = load_registry(DATA, custom_plant_dirs=[CUSTOM])
    banner("registry")
    print("plants:", len(reg.plants), sorted(reg.plants))
    print("enemies:", len(reg.enemies), sorted(reg.enemies))
    print("errors:", reg.errors)
    print("warnings:", reg.warnings)

    banner("derived stats spot check")
    csb = reg.plants["custom_shieldbreaker"]
    print("shieldbreaker power/tier/recharge/sun:",
          csb["_power"], csb["_tier"], csb["recharge"], csb["sun"], csb.get("_tier_mismatch"))
    for k in ("cone", "bucket", "giant", "boss_50"):
        e = reg.enemies[k]
        print(k, "nominal_hp=", e["_nominal_hp"])

    banner("one full run (4 waves, smart bot, basic pool)")
    pool = ["sunbloom", "peashooter", "repeater", "wallnut", "bombberry"]
    sched = build_schedule(reg.enemies, waves=4, seed=7)
    print("spawn entries:", len(sched), "first:", sched[:3], "last:", sched[-1])

    def run(seed):
        sim = Simulation(reg.plants, reg.enemies, sched, pool, seed=seed)
        bot = RuleBot(pool, smart=True)
        return sim.run_to_end(bot)

    m1 = run(7)
    m2 = run(7)
    m3 = run(99)
    print("metrics seed7:", json.dumps(m1, ensure_ascii=False))
    print("determinism seed7 equal:", m1 == m2)
    print("different seed differs:", m1 != m3)

    banner("dumb bot vs shield cadet (expect mower use / harder)")
    from tdgame.engine.wavegen import fixed_schedule
    fs = fixed_schedule([(3.0, "shield_cadet"), (10.0, "shield_cadet"), (17.0, "shield_cadet"),
                         (24.0, "shield_cadet"), (31.0, "shield_cadet")])
    basic = ["sunbloom", "peashooter", "repeater", "wallnut"]
    sim = Simulation(reg.plants, reg.enemies, fs, basic, seed=3, max_seconds=120)
    md = sim.run_to_end(RuleBot(basic, smart=False))
    print("dumb metrics:", json.dumps(md, ensure_ascii=False))


if __name__ == "__main__":
    main()
