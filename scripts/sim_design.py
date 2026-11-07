# -*- coding: utf-8 -*-
"""设计层自洽推演：用新档位体系反算一批代表植物，检查是否有崩坏点。

只依赖 tdgame/design_slots.py（规则已确认），不碰战斗引擎。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame import design_slots as D  # noqa: E402

print("=" * 78)
print("一、代表植物在档位体系下的落位")
print("=" * 78)
print(f"{'植物':<14}{'档位':>5}{'总点':>5}{'阶位':>5}{'阳光':>6}{'CD':>7}{'DPS':>6}{'单发':>7}")

CASES = [
    ("豌豆射手", {"dps": 2, "sun": 1, "cd": 1}, (), False),
    ("寒冰射手", {"dps": 2, "slow": 1, "sun": 1, "cd": 1}, (), False),
    ("三线射手", {"dps": 2, "targets": 1, "sun": 1, "cd": 1}, (), False),
    ("大嘴花",   {"dps": 4, "sun": 1, "cd": 1}, (), False),
    ("坚果墙",   {"dps": 1, "hp": 3, "sun": 3, "cd": 1}, (), True),
    ("西瓜投手", {"dps": 4, "sun": 1, "cd": 1},
     ("one_shot",) * 0, False),
    ("樱桃炸弹", {"dps": 2, "range": 2, "sun": 1, "cd": 1}, ("one_shot",), True),
]

for name, lv, mech, no_attack in CASES:
    p = D.PlantPlan(levels=lv, mechanics=mech, attacking=not no_attack,
                    one_shot=("one_shot" in mech))
    print(f"{name:<14}{p.slots:>5}{p.slots:>5}{p.tier:>5}{p.sun:>6}"
          f"{p.cooldown:>7}{p.dps:>6}{p.damage_per_hit:>7}")

print()
print("=" * 78)
print("二、机制型植物的落位")
print("=" * 78)
print(f"{'植物':<14}{'机制':<14}{'总点':>5}{'阶位':>5}{'阳光':>6}{'CD':>7}")
MECH_CASES = [
    ("护甲壳南瓜", {"hp": 2, "sun": 1, "cd": 1}, ("shell",)),
    ("战歌光环",   {"sun": 1, "cd": 1}, ("aura",)),
    ("治疗植物",   {"dps": 2, "heal": 3, "sun": 1, "cd": 1}, ()),
    ("生产阳光",   {"hp": 1, "sun": 1, "cd": 1}, ("economy",)),
]
for name, lv, mech in MECH_CASES:
    p = D.PlantPlan(levels=lv, mechanics=mech, attacking=(lv.get("dps", 1) > 1))
    print(f"{name:<14}{str(mech):<14}{p.slots:>5}{p.tier:>5}{p.sun:>6}{p.cooldown:>7}")

print()
print("=" * 78)
print("三、抛射僵尸 vs 治疗植物（伤害 60 / 2.5s）")
print("=" * 78)
lobber_dps = 60 / 2.5
heal = D.PlantPlan(levels={"dps": 2, "heal": 3, "sun": 1, "cd": 1})
heal_per_hit = heal.dps * 2
heal_hps = heal_per_hit / heal.interval
print(f"  抛射压力      : {lobber_dps:.1f} HP/s")
print(f"  治疗（3档）   : 每次 {heal_per_hit} HP / {heal.interval}s = {heal_hps:.1f} HP/s")
print(f"  结论          : {'治疗能压住 1 只' if heal_hps > lobber_dps else '压不住'}"
      f"；压住 2 只需 {heal_hps / lobber_dps:.2f} 株等效")

print()
print("=" * 78)
print("四、亵渎光环（1.5%/s）对各坦度的实际杀伤")
print("=" * 78)
print(f"{'坦度档':<8}{'HP':>8}{'每秒损失':>10}{'清空满血':>10}")
for lv, hp in D.HP_BY_LEVEL.items():
    if lv == 0:
        continue
    dps = hp * 0.015
    print(f"T{lv:<7}{hp:>8}{dps:>10.1f}{hp / dps:>9.0f}s")

print()
print("  注意：治疗是固定值（攻击力×2），光环是百分比 ->")
print("        治疗对低血量植物更有效，光环对高血量植物更狠，天然惩罚堆肉盾。")

print()
print("=" * 78)
print("五、击退与力道：攻速/破格能否推动各韧性档")
print("=" * 78)
print(f"{'韧性档':<8}{'韧性':>6}{'门槛':>8}{'5档100':>8}{'破格150':>9}{'5档+慢攻速(170)':>18}")
for key in ("T0", "T1", "T2", "T3", "T4", "T5", "SP", "SP+"):
    t, _eff, _cut = D.TENACITY_BY_TIER[key]
    need = t * D.FORCE_THRESHOLD
    a = "OK" if D.knockback_effective(100, key) else "-"
    b = "OK" if D.knockback_effective(150, key) else "-"
    c = "OK" if D.knockback_effective(D.force_with_attack_speed(100, 1), key) else "-"
    print(f"{key:<8}{t:>6}{need:>8.0f}{a:>8}{b:>9}{c:>18}")
