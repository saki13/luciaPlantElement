# -*- coding: utf-8 -*-
"""阶段进度 / 设计代币 / 解锁流（P1→P4，纯数据 + 查询函数）。

对齐用户确认的主线：
P1 新手白天约 10 关（上限双发射手）→ 首通给 200 设计代币；
P2 能力挑战关（每种麻烦能力一个教学考场），通关持续赚代币、开放植物定制；
P3 进阶约 10 关 + 复数能力阶段 Boss；
P4 无尽/爬塔，每 50 轮一个 T10 门槛 Boss，通关 50 轮解锁僵尸编辑器（M5）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .customizer import FIRST_CLEAR_TOKENS


@dataclass
class PhaseDef:
    code: str
    name: str
    levels: int
    token_reward_total: int
    unlocks: List[str] = field(default_factory=list)
    notes: str = ""


PHASES: Dict[str, PhaseDef] = {
    "P1": PhaseDef("P1", "新手白天主线", 10, 0,
                   ["peashooter", "sunbloom", "wallnut", "morningglory", "repeater"],
                   "教学：经济→单路→多线，最强只到双发射手"),
    "P2": PhaseDef("P2", "能力挑战/植物定制", 6, FIRST_CLEAR_TOKENS,
                   ["plant_customizer", "shield_break"],
                   "首通 200 代币=火力3档120+破盾80，随后每种能力一关持续奖励"),
    "P3": PhaseDef("P3", "进阶主线+阶段Boss", 10, 300,
                   ["melonpult", "winter_melon", "armor_pierce", "boss_stage"],
                   "二阶植物与复数能力 Boss"),
    "P4": PhaseDef("P4", "无尽/爬塔", 0, 0,
                   ["endless", "climb_tower", "zombie_editor_at_50"],
                   "每50轮一个T10门槛Boss；50轮成就解锁僵尸编辑器"),
}

def phase_of_level(level_key: str) -> Optional[str]:
    # 关卡键前缀用 M1..M4，阶段码用 P1..P4，这里统一映射
    prefix = level_key.split("_", 1)[0].upper().replace("M", "P")
    return prefix if prefix in PHASES else None


def reward_for_level(level_key: str, first_clear: bool = True,
                     levels: Optional[Dict[str, Dict]] = None) -> Dict[str, int]:
    """返回该关首通/重复通关的设计代币奖励。

    **奖励以关卡 JSON 为唯一来源**（`levels[key]["reward"]["design_tokens"]`）。
    早期这里另存了一份 `CHALLENGE_TOKEN_REWARD` 硬编码表，与关卡数据双写，改 JSON 不生效，
    已删除。调用方必须传入 `levels`，否则一律按 0 处理。
    """
    if not first_clear:
        return {"design_tokens": 0}
    if levels and level_key in levels:
        reward = (levels[level_key].get("reward") or {})
        return {"design_tokens": int(reward.get("design_tokens", 0) or 0)}
    return {"design_tokens": 0}


class PlayerProgress:
    """内存态玩家进度（持久化序列化为 JSON 的工作留给上层存档模块）。

    `levels` 传 `level_run.load_levels()` 的结果；奖励只从关卡 JSON 读。
    """

    def __init__(self, levels: Optional[Dict[str, Dict]] = None) -> None:
        self.levels = levels
        self.cleared: List[str] = []
        self.design_tokens = 0
        self.unlocked = set(PHASES["P1"].unlocks)

    def clear_level(self, level_key: str) -> int:
        first = level_key not in self.cleared
        reward = reward_for_level(level_key, first, self.levels)["design_tokens"]
        if first:
            self.cleared.append(level_key)
            self.design_tokens += reward
            phase = phase_of_level(level_key)
            if phase:
                self.unlocked.update(PHASES[phase].unlocks)
        return reward

    def spend(self, amount: int) -> bool:
        if amount > self.design_tokens:
            return False
        self.design_tokens -= amount
        return True

    def reached_phase(self) -> str:
        have = set(self.cleared)
        if any(k.startswith("m3") for k in have):
            return "P4" if any(k.startswith("m4") for k in have) else "P3"
        if any(k.startswith("m2") for k in have):
            return "P2"
        return "P1"
