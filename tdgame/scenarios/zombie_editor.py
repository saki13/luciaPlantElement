# -*- coding: utf-8 -*-
"""M5 僵尸编辑器（纯逻辑）：玩家通关无尽 50 轮后解锁，自定义僵尸。

敌人四维 速度/防御/血量/再生，各 0..5 档，采用与植物对称的点数预算；
格挡/免控/精英啃咬等能力作为额外标签购点。产出的 dict 直接走 engine.loader
validate_enemy 终检，保证 reduction<1、字段齐全，能进 headless 与"我是僵尸"玩法。

数值为草案，映射锚定内置 normal/fast/cone/bucket/giant，headless 校准后回填。
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .. import config as C

# 四维 0..5 档累计点数（与植物 TOKEN_AXIS_CUM 对称的量级）
ENEMY_AXIS_CUM = [0, 30, 60, 100, 150, 220]
# 能力标签价格
ENEMY_TAG_PRICE = {"block": 80, "kb_immune": 100, "slow_resist": 80, "elite_bite": 90}
DEFAULT_POINT_CAP = 600          # 编辑器初始总点预算（成就/爬塔可再放宽）

SPEED_LEVELS = [0, 25, 34, 45, 55, 65]                 # px/s，档2=普通34、档5≈65 超快步
BODY_LEVELS = [80, 100, 140, 220, 360, 600]            # 本体血量，档1=普通100
# 防御档 -> (护甲血量, 减伤率)；0/1 档无甲，档5≈铁桶级
DEFENSE_ARMOR = [(0, 0.0), (0, 0.0), (120, 0.10), (240, 0.15), (400, 0.20), (550, 0.25)]
REGEN_LEVELS = [0, 0, 1, 2, 4, 8]                      # 每秒回血
BLOCK_FLAT_VALUE = 20
SLOW_RESIST_VALUE = 0.5


class EnemyBuildError(ValueError):
    pass


def quote_points(axes: Mapping[str, int], tags: Sequence[str]) -> int:
    total = 0
    for a in ("speed", "defense", "body", "regen"):
        total += ENEMY_AXIS_CUM[int(axes.get(a, 0))]
    for t in tags:
        total += ENEMY_TAG_PRICE.get(t, 0)
    return total


def _derive_budget(axes: Mapping[str, int], tags: Sequence[str]) -> int:
    """由总点数派生出场威胁预算点（1..9，巨人级 weight 单独处理）。"""
    pts = quote_points(axes, tags)
    return max(1, min(9, round(pts / 110)))


def validate_enemy_build(axes: Mapping[str, int], tags: Sequence[str] = (),
                         point_cap: int = DEFAULT_POINT_CAP) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    for a in ("speed", "defense", "body", "regen"):
        lv = int(axes.get(a, 0))
        if not (0 <= lv <= 5):
            errs.append(f"axis {a} out of 0..5: {lv}")
    for t in tags:
        if t not in ENEMY_TAG_PRICE:
            errs.append(f"unknown enemy tag {t}")
    if quote_points(axes, tags) > point_cap:
        errs.append("point budget exceeded")
    if int(axes.get("speed", 0)) == 0:
        errs.append("speed level 0 means immobile, disallowed")
    return (not errs), errs


def build_enemy_definition(key: str, cn: str, axes: Mapping[str, int],
                           tags: Sequence[str] = (), point_cap: int = DEFAULT_POINT_CAP,
                           art_prompt: str = "") -> Dict[str, Any]:
    ok, errs = validate_enemy_build(axes, tags, point_cap)
    if not ok:
        raise EnemyBuildError("; ".join(errs))
    tag_list = list(tags)
    armor_hp, reduction = DEFENSE_ARMOR[int(axes["defense"])]
    body = BODY_LEVELS[int(axes["body"])]
    heavy = int(axes["defense"]) >= 4 or body >= 360
    return {
        "key": key,
        "cn": cn,
        "hp_body": body,
        "armor": {"hp": armor_hp, "reduction": reduction},
        "block_flat": BLOCK_FLAT_VALUE if "block" in tag_list else 0,
        "regen": REGEN_LEVELS[int(axes["regen"])],
        "speed": SPEED_LEVELS[int(axes["speed"])],
        "bite_dps": C.ELITE_BITE_DPS if "elite_bite" in tag_list else C.DEFAULT_BITE_DPS,
        "budget": _derive_budget(axes, tag_list),
        "weight": 99 if ("kb_immune" in tag_list or heavy) else 1,
        "slow_resist": SLOW_RESIST_VALUE if "slow_resist" in tag_list else (0.5 if heavy else 0),
        "kb_immune": "kb_immune" in tag_list,
        "tags": tag_list + (["heavy"] if heavy and "kb_immune" not in tag_list else []),
        "unlock_stage": "M5",
        "art_prompt": art_prompt or f"Q版粗描边卡通手游原创怪物，{cn}，白底纯白背景，可爱不恐怖",
    }
