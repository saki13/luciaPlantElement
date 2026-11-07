# -*- coding: utf-8 -*-
"""档位点体系 v3 的数据结构与结算规则（纯数据 + 纯函数，不依赖渲染）。

口径来源：docs/TIER_SYSTEM_V3.md（由设计方逐条确认）。

核心概念：
- 每株植物 = 一堆「档位点」的分配；每升一档花 1 点。
- 硬数值轴基础 1 档（必占 1 点）；量化能力基础 0 档。
- 总档位点决定阶位：取「上限 ≥ 总点数」的最大阶位。
- 阶位决定基础阳光与基础 CD；阳光/CD 还能用档位点再下调。

本模块**不修改**战斗引擎，只提供可被引擎与工坊共同调用的纯函数，
便于先把规则钉死、再加测试、最后接进 board.py。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# ---------------------------------------------------------------- 阶位表
# (阶位, 阳光基础, 档位上限, 基础 CD 秒)
TIER_TABLE: Tuple[Tuple[int, int, int, float], ...] = (
    (1, 50, 5, 7.5), (2, 75, 6, 7.5), (3, 100, 7, 7.5), (4, 125, 8, 7.5),
    (5, 150, 9, 7.5), (6, 250, 10, 10.0), (7, 300, 12, 10.0), (8, 350, 14, 10.0),
    (9, 450, 16, 13.0), (10, 500, 18, 16.0), (11, 550, 23, 20.0),
    (12, 600, 26, 25.0), (13, 700, 30, 30.0),
)
TIER_SUN = {t: sun for t, sun, _cap, _cd in TIER_TABLE}
TIER_CAP = {t: cap for t, _sun, cap, _cd in TIER_TABLE}
TIER_CD = {t: cd for t, _sun, _cap, cd in TIER_TABLE}

# ---------------------------------------------------------------- 硬数值轴
# 索引 = 档位（0 表示未投点/不适用；1..5 正常；6 = 破格）
DPS_BY_LEVEL = {0: 0, 1: 0, 2: 20, 3: 40, 4: 80, 5: 120, 6: 180}
HP_BY_LEVEL = {0: 0, 1: 300, 2: 1200, 3: 4000, 4: 8000, 5: 20000, 6: 30000}
SUN_REDUCTION_BY_LEVEL = {0: 0, 1: 0, 2: -50, 3: -100, 4: -150, 5: -200, 6: -300}
CD_REDUCTION_BY_LEVEL = {0: 0.0, 1: 0.0, 2: -1.5, 3: -3.0, 4: -4.5, 5: -6.0, 6: -9.0}

# 攻速：7 档，独立计价（占 1 档位点）；4 档 = 原版豌豆 1.4s
ATTACK_INTERVAL_BY_LEVEL = {1: 3.50, 2: 2.60, 3: 1.90, 4: 1.40,
                            5: 1.10, 6: 0.85, 7: 0.50}

CD_FLOOR = 7.5          # 卡片 CD 硬下限（= 原版豌豆）

# ---------------------------------------------------------------- 一次性爆炸
# 参照原版樱桃炸弹的比例反推：樱桃 150 阳光 / 50s CD / 1800 伤害，
# 对比豌豆 100 阳光 / 7.5s CD -> 阳光 1.5x、CD 6.67x、伤害 90x DPS。
# 设计方要求「花费减少、CD 加长」，故取 阳光 1.2x、CD 10x。
ONE_SHOT_DAMAGE_MULT = 100      # 爆炸伤害 = DPS x 100
ONE_SHOT_SUN_MULT = 0.8         # 阳光 = 该阶基础 x 0.8（比常规植物便宜）
ONE_SHOT_CD_MULT = 4.0          # CD = 该阶基础 x 4
ONE_SHOT_CD_MIN = 40.0
ONE_SHOT_CD_MAX = 90.0
# 一次性植物的「坦度」平替为「范围」：不付坦度基础点，改付范围轴
RANGE_REPLACES_HP = True

# ---------------------------------------------------------------- 量化能力轴
SHIELD_BREAK_BY_LEVEL = {0: 0, 1: 20, 2: 30, 3: 40, 4: 60, 5: 80, 6: 120}
# (减速比例, 持续秒)
SLOW_BY_LEVEL = {0: (0.0, 0.0), 1: (0.25, 2.0), 2: (0.30, 2.5), 3: (0.50, 4.0),
                 4: (0.75, 7.0), 5: (0.95, 10.0), 6: (1.42, 15.0)}
ARMOR_PIERCE_BY_LEVEL = {0: 1.0, 1: 1.2, 2: 1.4, 3: 1.6, 4: 1.9, 5: 2.2, 6: 3.3}
TARGETS_BY_LEVEL = {0: 1, 1: 1, 2: 2, 3: 3, 4: 5, 5: 10, 6: 15}
KNOCKBACK_BY_LEVEL = {0: 0.0, 1: 0.2, 2: 0.4, 3: 0.8, 4: 1.2, 5: 2.0, 6: 3.0}
FORCE_BY_LEVEL = {0: 0, 1: 20, 2: 40, 3: 60, 4: 80, 5: 100, 6: 150}

# 攻速越慢，单次打击力道越强（4 档为基准，无加成）
# 4 档为基准；比基准慢 -> 加成（+70/+30/+10）；
# 比基准快 -> **每提一档力道 −15%**（设计方给定）
FORCE_ATTACK_SPEED_MULT = {1: 1.70, 2: 1.30, 3: 1.10, 4: 1.00,
                           5: 0.85, 6: 0.70, 7: 0.55}

# 治疗（3/4/5 档才有；治疗量 = 攻击力×2，频率 = 攻速）
HEAL_RADIUS_BY_LEVEL = {3: 0, 4: 1, 5: 2}   # 0=1x1, 1=2x2, 2=3x3（半径）

# ---------------------------------------------------------------- 机制能力固定价
MECHANIC_COST: Dict[str, int] = {
    "economy": 3,        # 生产阳光
    "shell": 6,          # 外挂壳（护甲壳）
    "aura": 15,          # 光环
    "overclock": 4,      # 破格（允许一个轴到 6 档）
    "one_shot": 4,       # 一次性爆炸
    "spike": 3,          # 地刺/陷阱
    "summon": 5,         # 召唤单位
    "disarm": 4,         # 卸甲/磁力
    "lane_shift": 4,     # 换行/变角
    "anti_air": 2,       # 反空
    "transform": 6,      # 变身/升级
    "fullscreen": 12,    # 全屏清场
    "shield": 8,         # 护盾/无敌
}

# 基础必占的硬数值轴（各 1 点）
BASE_AXES = ("dps", "hp", "sun", "cd")

# ---------------------------------------------------------------- 敌人韧性表
# (档位, 韧性, 减速效果乘数, 控制时间扣减秒)
TENACITY_TABLE: Tuple[Tuple[str, int, float, float], ...] = (
    ("T0", 0, 1.00, 0.0),      # 普通僵尸
    ("T1", 20, 1.00, 0.0),     # 旗手 / 报纸
    ("T2", 50, 0.90, 0.0),     # 撑杆跳
    ("T3", 80, 0.80, 0.0),     # 橄榄球
    ("T4", 105, 0.60, 1.0),    # 车类
    ("T5", 150, 0.50, 3.0),    # 巨人
    ("SP", 300, 0.30, 6.0),    # 小 Boss
    ("SP+", 999, 0.00, 8.0),   # 大 Boss（免疫控制）
)
TENACITY_BY_TIER = {k: (t, eff, cut) for k, t, eff, cut in TENACITY_TABLE}

FORCE_THRESHOLD = 0.8          # 力道 < 韧性 × 80% -> 击退/眩晕无效
SPLASH_EFFECT_RATIO = 0.25     # 溅射给非直击目标的效果折算


# ================================================================ 纯函数
def tier_for_slots(total: int) -> int:
    """总档位点 -> 阶位：取「上限 >= 总点数」的**最低**阶位。"""
    if total <= 0:
        return 1
    for tier, _sun, cap, _cd in TIER_TABLE:
        if cap >= total:
            return tier
    return TIER_TABLE[-1][0]      # 超过 T13 上限，按 T13 处理


def total_slots(levels: Dict[str, int], mechanics: Tuple[str, ...] = (),
                attacking: bool = True,
                hp_replaced_by_range: bool = False) -> int:
    """把一株植物的档位分配折算成总档位点。

    levels: 轴名 -> 档位（硬数值轴缺省按 1 档算；能力轴缺省 0）
    硬数值轴 4 条各至少 1 点。**攻速不占档位点**（设计方确认）：
    它只是把同样的 DPS 重新分配到"多发小额"或"少发大额"上，不改变总量。
    """
    total = 0
    for axis in BASE_AXES:
        if axis == "hp" and hp_replaced_by_range:
            # 一次性植物的坦度平替为范围（它不靠耐久站场）
            total += int(levels.get("range", 0))
            continue
        total += max(1, int(levels.get(axis, 1)))
    for axis in ("shield_break", "slow", "armor_pierce", "targets",
                 "knockback", "heal"):
        total += int(levels.get(axis, 0))
    for key in mechanics:
        if key not in MECHANIC_COST:
            raise KeyError(f"未知机制能力：{key}")
        total += MECHANIC_COST[key]
    return total


@dataclass
class PlantPlan:
    """一株植物的档位分配结果。"""
    levels: Dict[str, int]
    mechanics: Tuple[str, ...] = ()
    attacking: bool = True
    explicit_sun: int | None = None      # 允许单独设定（例如坚果 50）
    # 一次性植物：坦度平替为范围，且阳光/CD 走一次性系数
    one_shot: bool = False

    @property
    def slots(self) -> int:
        return total_slots(self.levels, self.mechanics, self.attacking,
                           hp_replaced_by_range=self.one_shot)

    @property
    def tier(self) -> int:
        return tier_for_slots(self.slots)

    @property
    def sun(self) -> int:
        if self.explicit_sun is not None:
            return int(self.explicit_sun)
        if self.one_shot:
            return one_shot_sun(self.tier)
        return TIER_SUN[self.tier] + SUN_REDUCTION_BY_LEVEL[
            int(self.levels.get("sun", 1))]

    @property
    def cooldown(self) -> float:
        if self.one_shot:
            return one_shot_cd(self.tier)
        base = TIER_CD[self.tier]
        cut = CD_REDUCTION_BY_LEVEL[int(self.levels.get("cd", 1))]
        return max(CD_FLOOR, base + cut)

    @property
    def dps(self) -> int:
        return DPS_BY_LEVEL[int(self.levels.get("dps", 1))]

    @property
    def interval(self) -> float:
        if not self.attacking:
            return 0.0
        return ATTACK_INTERVAL_BY_LEVEL[int(self.levels.get("attack_speed", 4))]

    @property
    def damage_per_hit(self) -> float:
        return round(self.dps * self.interval, 3)

    def validate(self) -> Tuple[bool, List[str]]:
        errs: List[str] = []
        for axis, lv in self.levels.items():
            if axis == "attack_speed":
                if not (1 <= int(lv) <= 7):
                    errs.append(f"attack_speed={lv} 超出 1..7")
                continue
            if not (0 <= int(lv) <= 6):
                errs.append(f"{axis}={lv} 超出 0..6")
            elif int(lv) == 6 and "overclock" not in self.mechanics:
                errs.append(f"{axis} 取 6 档但没有「破格」")
        cap = TIER_CAP[self.tier]
        if self.slots > cap:
            errs.append(f"总点数 {self.slots} 超过 T{self.tier} 上限 {cap}")
        return (not errs), errs


# ---------------------------------------------------------------- 韧性结算
def slow_after_tenacity(ratio: float, duration: float,
                        tenacity_tier: str) -> Tuple[float, float]:
    """减速经韧性折算：比例按乘法削，时长按 flat 扣。返回 (比例, 时长)。"""
    if tenacity_tier not in TENACITY_BY_TIER:
        raise KeyError(tenacity_tier)
    t, eff, cut = TENACITY_BY_TIER[tenacity_tier]
    if eff <= 0.0:                  # SP+ 免疫控制
        return 0.0, 0.0
    return round(ratio * eff, 4), max(0.0, round(duration - cut, 3))


def knockback_effective(force: int, tenacity_tier: str) -> bool:
    """力道是否够推动该韧性档的敌人。"""
    t, _eff, _cut = TENACITY_BY_TIER[tenacity_tier]
    return force >= t * FORCE_THRESHOLD


def force_with_attack_speed(force: int, attack_speed_level: int) -> float:
    """攻速对力道的影响：4 档基准；越慢越重，越快每档 −15%。"""
    mult = FORCE_ATTACK_SPEED_MULT[int(attack_speed_level)]
    return round(force * mult, 3)


def one_shot_damage(dps: float) -> float:
    """一次性爆炸的伤害 = DPS x 100。"""
    return round(dps * ONE_SHOT_DAMAGE_MULT, 1)


def one_shot_sun(tier: int) -> int:
    """一次性植物的阳光：该阶基础 x 1.2，取整到 25 的倍数。"""
    raw = TIER_SUN[int(tier)] * ONE_SHOT_SUN_MULT
    return int(round(raw / 25.0)) * 25


def one_shot_cd(tier: int) -> float:
    """一次性植物的 CD：该阶基础 x 10，夹在 60..120s。"""
    raw = TIER_CD[int(tier)] * ONE_SHOT_CD_MULT
    return round(min(ONE_SHOT_CD_MAX, max(ONE_SHOT_CD_MIN, raw)), 1)


def splash_effect(value: float) -> float:
    """溅射到非直击目标时的折算。"""
    return round(value * SPLASH_EFFECT_RATIO, 4)
