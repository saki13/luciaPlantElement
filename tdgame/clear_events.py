# -*- coding: utf-8 -*-
"""通关事件钩子。

设计目的：通关后要显示「恭喜通关」，而且以后要能在**不改通关界面代码**的前提下
插入新东西——动画、奖励领取、新手教程、跳转门户、甚至一整段新流程。

用法（以后加内容只要注册一个函数）：

    from tdgame.clear_events import Step, register

    @register
    def my_event(ctx):
        if ctx["key"] == "m1_05":
            return Step(title="新植物解锁！", body="向日葵 ×2", kind="unlock")
        return None

钩子函数接收一个 ctx（dict），返回 Step 或 None。
返回多个 Step 时界面会按顺序逐个展示，玩家按回车推进。

ctx 字段（当前版本）：
    key         关卡 key，如 m1_01
    cn          关卡中文名
    won         是否通关
    duration    本局时长（秒）
    coins       本次发放的设计币
    plant       本次解锁的植物 key（可能为 None）
    is_new      True 表示该关是第一次通关
    next_key    下一关 key（没有则 None）
    progress    progression 进度对象本身，可读存档状态
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Step:
    """通关界面上的一屏。"""
    title: str
    body: str = ""
    kind: str = "info"          # info / reward / unlock / tutorial / animation
    color: tuple = (240, 255, 210)
    hold: float = 0.0           # >0 时自动停留这么多秒（给动画用）
    data: dict = field(default_factory=dict)   # 给钩子自己传数据用


CLEAR_EVENTS: list[Callable[[dict], Optional[Step]]] = []


def register(fn: Callable[[dict], Optional[Step]]):
    """注册一个通关事件钩子；可作为装饰器使用。"""
    CLEAR_EVENTS.append(fn)
    return fn


def unregister(fn) -> None:
    if fn in CLEAR_EVENTS:
        CLEAR_EVENTS.remove(fn)


def collect(ctx: dict) -> list[Step]:
    """依次跑所有钩子，收集要展示的步骤。钩子抛错不会影响其它钩子。"""
    steps: list[Step] = []
    for fn in list(CLEAR_EVENTS):
        try:
            got = fn(ctx)
        except Exception as exc:                       # noqa: BLE001
            print(f"[clear_events] {getattr(fn, '__name__', fn)} 出错: {exc}")
            continue
        if got is None:
            continue
        if isinstance(got, Step):
            steps.append(got)
        else:                                          # 允许返回列表
            steps.extend(s for s in got if isinstance(s, Step))
    return steps


# ---------------------------------------------------------------- 内置事件
@register
def _congrats(ctx: dict) -> Optional[Step]:
    if not ctx.get("won"):
        return None
    m, s = divmod(int(ctx.get("duration", 0)), 60)
    return Step(
        title="恭喜通关！",
        body=f"{ctx.get('cn') or ctx.get('key')}    用时 {m}分{s:02d}秒",
        kind="congrats",
        color=(240, 255, 210),
    )


@register
def _reward(ctx: dict) -> Optional[Step]:
    coins = int(ctx.get("coins") or 0)
    if not ctx.get("won") or coins <= 0:
        return None
    return Step(title=f"+{coins} 设计币", body="可以拿去设计自己的植物",
                kind="reward", color=(255, 226, 150))


@register
def _unlock(ctx: dict) -> Optional[Step]:
    plant = ctx.get("plant")
    if not ctx.get("won") or not plant:
        return None
    return Step(title="解锁新植物！", body=str(plant),
                kind="unlock", color=(160, 235, 170))


@register
def _first_clear(ctx: dict) -> Optional[Step]:
    if not ctx.get("won") or not ctx.get("is_new"):
        return None
    if not ctx.get("next_key"):
        return None
    return Step(title="继续前进", body=f"下一关：{ctx['next_key']}",
                kind="info", color=(200, 220, 245))


@register
def _game_over(ctx: dict) -> Optional[Step]:
    if ctx.get("won"):
        return None
    return Step(title="这局没守住", body="按 R 重来，或按 P 回门户换个关",
                kind="info", color=(255, 190, 180))
