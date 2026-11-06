# -*- coding: utf-8 -*-
"""M2 植物定制器（纯逻辑，不依赖 pygame / 网络）。

把玩家在工坊里的"五轴档位 + 功能标签 + 设计代币预算 + 所处阶段"装配成一张
可被 engine.loader 注册、可直接进 headless 战斗的植物定义 dict。

口径全部来自 game_balance_design.md v0.2 §6/§7/§8 与 tdgame.balance：
- 代币净额调用 balance.design_token_for_build（扣免费底盘）；
- power/tier/sun/recharge 由 balance 派生，前端不可绕过；
- 阶段准入逐期开放单轴上限与标签，P2 首通 200 代币正好够"火力3 + 破盾"。

combat 数值为 headless 可跑的【草案映射】，美术/手感在工坊步骤继续打磨，
正式真机数值以 headless 校准报告回填为准。
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .. import balance
from .. import config as C

# 火力档 -> 单发伤害（fire2=20 锚定豌豆射手；草案，待 headless 校准）
FIRE_DAMAGE = [0, 12, 20, 30, 45, 60]
# 坦度档 -> 生命值（dur1=100 为免费底盘；wall 职业可另行加高）
DUR_HP = [100, 100, 200, 400, 800, 1200]
DEFAULT_INTERVAL = 1.0

# 各阶段准入：单轴最高档、可用战斗标签、单轴外的品阶天花板
PHASE_RULES: Dict[str, Dict[str, Any]] = {
    "P2": {"max_axis": 3, "max_tier": 3, "tags": {"shield_break"}},
    "P3": {"max_axis": 4, "max_tier": 6,
           "tags": {"shield_break", "armor_pierce", "control", "aoe", "pierce", "fragments"}},
    "P4": {"max_axis": 5, "max_tier": C.MAX_TIER,
           "tags": {"shield_break", "armor_pierce", "control", "aoe", "pierce",
                    "fragments", "one_shot", "hard_cc", "summon", "fullscreen",
                    "manual_ultimate"}},
}
# 新手主线首通奖励（v0.2 §7）
FIRST_CLEAR_TOKENS = 200


class BuildError(ValueError):
    """配装不合法（超档/超预算/阶段未解锁）。"""


def _clean_axes(role: str, axes: Mapping[str, int]) -> Dict[str, int]:
    chassis = balance.free_chassis_axes(role)
    out = dict(chassis)
    for a in balance.AXES:
        out[a] = int(axes.get(a, chassis[a]))
    return out


def quote_tokens(role: str, axes: Mapping[str, int], tags: Sequence[str]) -> Dict[str, Any]:
    """返回代币报价明细（净额，已扣免费底盘）。"""
    clean = _clean_axes(role, axes)
    return balance.design_token_for_build(clean, role, combat_tags=tuple(tags))


def validate_build(role: str, axes: Mapping[str, int], tags: Sequence[str],
                   phase: str, token_budget: int) -> Tuple[bool, List[str], Dict[str, Any]]:
    """校验一次配装；返回 (是否合法, 错误列表, 代币报价)。"""
    errs: List[str] = []
    if phase not in PHASE_RULES:
        errs.append(f"unknown phase {phase}")
        return False, errs, {}
    rule = PHASE_RULES[phase]
    if role not in ("ranged", "melee"):
        errs.append(f"customizer combat role must be ranged/melee, got {role}")
    clean = _clean_axes(role, axes)
    for a, lv in clean.items():
        if not (0 <= lv <= C.AXIS_LEVELS):
            errs.append(f"axis {a} out of 0..5: {lv}")
        if lv > rule["max_axis"]:
            errs.append(f"axis {a}={lv} exceeds phase {phase} cap {rule['max_axis']}")
    for t in tags:
        if t not in rule["tags"]:
            errs.append(f"tag {t} not unlocked in phase {phase}")
    q = quote_tokens(role, clean, tags)
    if q["total"] > int(token_budget):
        errs.append(f"token cost {q['total']} over budget {token_budget}")
    power = balance.power_score(clean, len([t for t in tags if t in C.COMBAT_TAGS]))
    tier = balance.tier_of(power)
    if tier > rule["max_tier"]:
        errs.append(f"result tier {tier} exceeds phase {phase} tier cap {rule['max_tier']}")
    return (not errs), errs, q


def _combat_spec(role: str, clean: Mapping[str, int], tags: Sequence[str]) -> Dict[str, Any]:
    """由五轴生成 headless 可跑的最小战斗规格（草案）。"""
    damage = FIRE_DAMAGE[int(clean["fire"])]
    if role == "melee":
        rng = {"type": "melee", "cells": 1}
        speed = 0
    else:
        rng = {"type": "row", "cells": 9}
        speed = 320
    hit = "single"
    pierce_lv = int(clean.get("pierce", 0))
    if pierce_lv >= 1:
        hit = f"pierce:{min(3, pierce_lv)}"
    projectile = {"key": "custom_dart", "speed": speed, "hit": hit}
    if int(clean.get("control", 0)) >= 1 and role == "ranged":
        projectile["slow"] = {"factor": 0.5, "duration": 2.5}
    return {
        "atk_interval": DEFAULT_INTERVAL,
        "damage": damage,
        "range": rng,
        "projectile": projectile,
    }


def build_plant_definition(key: str, cn: str, role: str, axes: Mapping[str, int],
                           tags: Sequence[str], phase: str,
                           token_budget: int, art_prompt: str = "") -> Dict[str, Any]:
    """装配并返回一张完整、自洽、可被 loader 注册的植物定义。失败抛 BuildError。"""
    ok, errs, q = validate_build(role, axes, tags, phase, token_budget)
    if not ok:
        raise BuildError("; ".join(errs))
    clean = _clean_axes(role, axes)
    tag_list = list(tags)
    power = balance.power_score(clean, len([t for t in tag_list if t in C.COMBAT_TAGS]))
    tier = balance.tier_of(power)
    return {
        "key": key,
        "cn": cn,
        "role": role,
        "axes": clean,
        "tags": tag_list,
        "tier": tier,
        "recharge": balance.derive_recharge(tier, tag_list),
        "sun": balance.sun_cost(tier),
        "hp": DUR_HP[int(clean["durability"])],
        "design_token": {
            "phase": phase,
            "axis_tokens": q["axis_tokens"],
            "tag_tokens": q["tag_tokens"],
            "total": q["total"],
            "budget": int(token_budget),
        },
        "art_prompt": art_prompt or f"Q版粗描边卡通手游原创植物，{cn}，白底纯白背景，明快绿色平涂",
        "combat": _combat_spec(role, clean, tag_list),
    }
