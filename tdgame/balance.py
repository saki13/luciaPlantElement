# -*- coding: utf-8 -*-
"""纯数值平衡逻辑：确定性伤害管线 + power/品阶/代币/三维成本派生。

本模块不导入 pygame，headless 模拟器与未来真机战斗层共用同一组函数，
保证文档（game_balance_design.md v0.2 §3/§4/§6/§7/§8）数值与战斗结果一致、可手算复现。
"""
from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Sequence

from . import config as C

AXES = ("fire", "area", "pierce", "durability", "control")


# ======================================================================
# 一、power score / 品阶（v0.2 §6）
# ======================================================================
def free_chassis_axes(role: str) -> Dict[str, int]:
    """免费底盘隐含起步档：100HP=坦度1；远程整行=打击面2，近战1格=打击面1。"""
    area = 1 if role == "melee" else 2
    return {"fire": 0, "area": area, "pierce": 0, "durability": 1, "control": 0}


def power_score(axes: Mapping[str, int], generic_tag_count: int = 0) -> float:
    """power = Σ b(档)×权重 + 功能标签通用分。"""
    total = 0.0
    for axis in AXES:
        level = int(axes.get(axis, 0))
        total += C.AXIS_BASE_SCORE[level] * C.AXIS_WEIGHTS[axis]
    return round(total + generic_tag_count * C.GENERIC_TAG_SCORE, 4)


def tier_of(power: float) -> int:
    """每 22.5 分一阶，Tn 下界=(n-1)×22.5；结果夹在 1..13。"""
    if power <= 0:
        return 1
    return int(min(C.MAX_TIER, math.floor(power / C.TIER_STEP) + 1))


def tier_bounds(tier: int) -> tuple[float, float]:
    lo = (tier - 1) * C.TIER_STEP
    return lo, lo + C.TIER_STEP


# ======================================================================
# 二、设计代币（v0.2 §7）
# ======================================================================
def token_cost(axes: Mapping[str, int], combat_tags: Sequence[str] = ()) -> int:
    """五轴累计代币 + 破防标签代币；底盘免费（起步档不计，这里只对超出免费档的档位计费由调用方处理）。

    说明：传入的 axes 若已含免费底盘档（坦度1 / 打击面1~2），调用方应先扣除底盘档再计轴代币；
    本函数按"当前档位"直接累计，loader 在装配自定义植物时用 design_token_for_build 做净额计算。
    """
    cost = 0
    for axis in AXES:
        cost += C.TOKEN_AXIS_CUM[int(axes.get(axis, 0))]
    for tag in combat_tags:
        cost += C.TAG_TOKEN_PRICE.get(tag, 0)
    return cost


def design_token_for_build(target_axes: Mapping[str, int], role: str,
                           combat_tags: Sequence[str] = (),
                           generic_tag_count: int = 0) -> Dict[str, Any]:
    """净额计算：扣除免费底盘档后，玩家实际需要花的设计代币。"""
    chassis = free_chassis_axes(role)
    paid_axes = {a: max(0, int(target_axes.get(a, 0)) - chassis.get(a, 0)) for a in AXES}
    axis_tokens = 0
    detail = {}
    for a in AXES:
        t = C.TOKEN_AXIS_CUM[paid_axes[a]]
        detail[a] = {"level": int(target_axes.get(a, 0)), "paid_levels": paid_axes[a], "tokens": t}
        axis_tokens += t
    tag_tokens = sum(C.TAG_TOKEN_PRICE.get(t, 0) for t in combat_tags)
    generic_tokens = sum(
        0 for _ in ())  # 通用战斗标签价格在具体标签 JSON 内声明，这里仅汇总破防标签
    return {
        "axis_tokens": axis_tokens,
        "tag_tokens": tag_tokens,
        "generic_tag_tokens": generic_tokens,
        "total": axis_tokens + tag_tokens + generic_tokens,
        "detail": detail,
        "generic_tag_count": generic_tag_count,
    }


# ======================================================================
# 三、三维成本：阳光 + recharge 派生（v0.2 §8）
# ======================================================================
def sun_cost(tier: int) -> int:
    return C.SUN_BY_TIER[int(min(C.MAX_TIER, max(1, tier)))]


def derive_recharge(tier: int, tags: Sequence[str] = ()) -> float:
    """自制植物 recharge 由品阶 + 强机制标签系统派生，5s 硬下限、玩家不可自由拧零。"""
    tag_set = set(tags)
    if tag_set & C.ULTRA_CD_TAGS:
        return C.RECHARGE_ULTRA
    if tier <= 2:
        base = C.RECHARGE_FAST
    elif tier <= 4:
        base = C.RECHARGE_MID
    elif tier <= 6:
        base = C.RECHARGE_STEADY
    elif tier <= 9:
        base = C.RECHARGE_SLOW
    else:
        base = C.RECHARGE_SLOW + 2.5
    if tag_set & C.LONG_CD_TAGS:
        base = max(base, C.RECHARGE_SLOW)
    return max(C.RECHARGE_FLOOR, round(base, 2))


# ======================================================================
# 四、确定性伤害结算管线（v0.2 §3.1 / §4，逐伤害实例）
# ======================================================================
def _val(o: Any, key: str, default: float = 0.0) -> float:
    if isinstance(o, Mapping):
        return float(o.get(key, default) or 0)
    return float(getattr(o, key, default) or 0)


def _set(o: Any, key: str, value: float) -> None:
    if isinstance(o, Mapping):
        o[key] = value
    else:
        setattr(o, key, value)


def resolve_hit(enemy: Any, raw_damage: float, tags: Sequence[str] = (),
                ap_mult: float | None = None) -> Dict[str, Any]:
    """对单个敌人（Enemy 对象或等价 dict）结算一次伤害实例，就地修改其 hp_body / armor_hp。

    字段：hp_body / armor_hp / armor_reduction / block_flat。
    返回：raw, after_block, shield_broke, blocked_fully, armor_absorbed, body_damage, killed。
    """
    tag_set = set(tags)
    dmg = float(raw_damage)
    detail: Dict[str, Any] = {"raw": dmg, "shield_broke": False, "blocked_fully": False,
                              "armor_absorbed": 0.0, "body_damage": 0.0}

    # 步骤 2：格挡（每实例固定减，可归零；shield_break 跳过）
    block = _val(enemy, "block_flat")
    if block > 0 and "shield_break" not in tag_set:
        dmg = max(0.0, dmg - block)
    elif block > 0 and "shield_break" in tag_set:
        detail["shield_broke"] = True
    detail["after_block"] = round(dmg, 4)

    # 步骤 3：归零短路，不破甲不打本体
    if dmg <= 0:
        detail["blocked_fully"] = True
        detail["killed"] = _val(enemy, "hp_body") <= 0
        return detail

    # 步骤 4：护甲段（穿甲倍率只作用甲段；溢出原始伤害 ×(1-reduction) 进本体）
    armor_hp = _val(enemy, "armor_hp")
    if armor_hp > 0:
        ap = ap_mult if ap_mult is not None else (
            C.AP_MULT_DEFAULT if "armor_pierce" in tag_set else 1.0)
        reduction = _val(enemy, "armor_reduction")
        capacity_raw = armor_hp / ap                     # 当前甲段可吸收的原始伤害当量
        if dmg <= capacity_raw:
            absorbed = dmg * ap
            _set(enemy, "armor_hp", round(armor_hp - absorbed, 6))
            detail["armor_absorbed"] = round(absorbed, 4)
        else:
            _set(enemy, "armor_hp", 0.0)
            detail["armor_absorbed"] = round(armor_hp, 4)
            overflow_raw = dmg - capacity_raw
            body = overflow_raw * (1.0 - reduction)     # 溢出折减后打本体
            _set(enemy, "hp_body", round(_val(enemy, "hp_body") - body, 6))
            detail["body_damage"] = round(body, 4)
    else:
        # 步骤 5：无甲直接扣本体（穿甲倍率不作用裸本体）
        _set(enemy, "hp_body", round(_val(enemy, "hp_body") - dmg, 6))
        detail["body_damage"] = round(dmg, 4)

    detail["killed"] = _val(enemy, "hp_body") <= 0
    return detail


def nominal_hp(enemy: Any) -> float:
    """标称总血量 = 本体上限 + 甲段上限（v0.2 EHP 口径，路障280/铁桶650 守恒校验用）。

    同时兼容运行时 Enemy（*_max 字段）与 JSON 定义（hp_body + armor.hp）。
    """
    if isinstance(enemy, Mapping):
        body = enemy.get("hp_body_max", enemy.get("hp_body", 0))
        armor = enemy.get("armor_hp_max", enemy.get("armor", {}).get("hp", 0))
        return float(body) + float(armor or 0)
    return float(getattr(enemy, "hp_body_max", 0)) + float(getattr(enemy, "armor_hp_max", 0) or 0)


# ======================================================================
# 五、控制结算（v0.2 §4.4）
# ======================================================================
def effective_speed_mult(slow_factor: float, slow_resist: float) -> float:
    """slow_factor 为植物给出的速度乘数（0.5=减速一半）；slow_resist 抵抗减速比例。"""
    slow_amount = max(0.0, 1.0 - slow_factor)
    return round(1.0 - slow_amount * (1.0 - slow_resist), 4)


def knockback_distance(base_cells: float, weight: float, kb_immune: bool) -> float:
    if kb_immune:
        return 0.0
    return round(base_cells / max(1.0, float(weight)), 4)
