# -*- coding: utf-8 -*-
"""打印当前注册表内置植物/敌人花名册（直接读 data JSON，含派生 tier/EHP）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame.engine.loader import load_registry
from tdgame import balance


def main() -> None:
    reg = load_registry(ROOT / "tdgame" / "data")
    print("== loader errors:", reg.errors or "none")
    print("\n=== 植物（%d）===" % len(reg.plants))
    for k in sorted(reg.plants):
        d = reg.plants[k]
        c = d.get("combat", {})
        proj = c.get("projectile", {})
        axes = d.get("axes", {})
        ax = "/".join(str(axes.get(a, 0)) for a in
                      ("fire", "area", "pierce", "durability", "control"))
        print(f"{k:20s} | {d.get('cn',''):8s} | {d.get('role',''):7s} | T{d.get('tier')} "
              f"| 阳光{d.get('sun'):>3} CD{d.get('recharge'):>4}s HP{d.get('hp'):>4} "
              f"| 五轴[{ax}] | 标签{sorted(d.get('tags', []))} "
              f"| 伤{c.get('damage','-')}/每{c.get('atk_interval','-')}s 命中{proj.get('hit','-')}")

    print("\n=== 敌人（%d）===" % len(reg.enemies))
    for k in sorted(reg.enemies):
        e = reg.enemies[k]
        armor = e.get("armor", {}) or {}
        print(f"{k:14s} | {e.get('cn',''):10s} | 本体{e.get('hp_body'):>5} "
              f"| 甲{armor.get('hp',0):>4}(减伤{armor.get('reduction',0)}) "
              f"| 格挡{e.get('block_flat',0):>2} 回血{e.get('regen',0)} "
              f"| 速{e.get('speed'):>3} 啃{e.get('bite_dps')} 预算{e.get('budget')} "
              f"| 重{e.get('weight')} 抗缓{e.get('slow_resist',0)} 免推{e.get('kb_immune',False)} "
              f"| EHP{balance.nominal_hp(e):.0f} | {sorted(e.get('tags', []))}")


if __name__ == "__main__":
    main()
