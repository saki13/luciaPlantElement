# -*- coding: utf-8 -*-
"""通关 / 失败界面：显示钩子产出的步骤，并决定下一步去哪。"""
from __future__ import annotations

import os

import pygame

from .clear_events import Step, collect

WIN_W, WIN_H = 1000, 620
BG = (16, 22, 18)
PANEL = (26, 34, 28)
LINE = (60, 78, 64)
FG = (232, 238, 230)
DIM = (150, 165, 155)
ACCENT = (245, 200, 92)


def _load_font(size: int, bold: bool = False) -> pygame.font.Font:
    cands = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttf" if bold else "C:/Windows/Fonts/msyh.ttf",
        "C:/Windows/Fonts/simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    for p in cands:
        if os.path.exists(p):
            try:
                return pygame.font.Font(p, size)
            except Exception:                          # noqa: BLE001
                continue
    return pygame.font.SysFont("arial", size)


class ClearScreen:
    """一屏一屏展示 Step，最后给出可选动作。"""

    def __init__(self, ctx: dict):
        self.ctx = ctx
        self.steps: list[Step] = collect(ctx)
        if not self.steps:
            self.steps = [Step(title="恭喜通关！" if ctx.get("won") else "这局没守住")]
        self.idx = 0
        self.f_big = _load_font(46, bold=True)
        self.f_mid = _load_font(24)
        self.f_small = _load_font(17)
        self.actions: list[tuple[str, str]] = []      # (key, label)
        self._rebuild_actions()

    # ---------------------------------------------------------------- 动作
    def _rebuild_actions(self) -> None:
        self.actions = []
        if self.idx < len(self.steps) - 1:
            self.actions.append(("next", "回车 继续"))
        else:
            if self.ctx.get("won") and self.ctx.get("next_key"):
                self.actions.append(("level", "回车 进入下一关"))
            self.actions.append(("portal", "P 回门户"))
            self.actions.append(("restart", "R 重开本关"))
            self.actions.append(("workshop", "G 植物工坊"))
            self.actions.append(("quit", "Q 退出"))

    # ---------------------------------------------------------------- 输入
    def handle(self, ev) -> str | None:
        """返回动作名；None 表示继续停留。"""
        if ev.type == pygame.QUIT:
            return "quit"
        if ev.type != pygame.KEYDOWN:
            return None
        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if self.idx < len(self.steps) - 1:
                self.idx += 1
                self._rebuild_actions()
                return None
            return "level" if (self.ctx.get("won") and self.ctx.get("next_key")) else "restart"
        if ev.key in (pygame.K_p, pygame.K_ESCAPE):
            return "portal"
        if ev.key == pygame.K_r:
            return "restart"
        if ev.key == pygame.K_g:
            return "workshop"
        if ev.key == pygame.K_q:
            return "quit"
        # 数字键直达第 N 屏（调试/以后做动画跳转用）
        if pygame.K_1 <= ev.key <= pygame.K_9:
            n = ev.key - pygame.K_1
            if n < len(self.steps):
                self.idx = n
                self._rebuild_actions()
        return None

    # ---------------------------------------------------------------- 绘制
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(BG)
        pygame.draw.rect(surf, PANEL, (40, 36, WIN_W - 80, WIN_H - 72), border_radius=14)
        pygame.draw.rect(surf, LINE, (40, 36, WIN_W - 80, WIN_H - 72), 2, border_radius=14)

        st = self.steps[self.idx]
        cx = WIN_W // 2

        title = self.f_big.render(st.title, True, st.color)
        surf.blit(title, (cx - title.get_width() // 2, 96))

        y = 180
        for line in (st.body or "").split("\n"):
            img = self.f_mid.render(line, True, FG)
            surf.blit(img, (cx - img.get_width() // 2, y))
            y += 34

        # 进度点
        if len(self.steps) > 1:
            total_w = len(self.steps) * 22
            x = cx - total_w // 2
            for i in range(len(self.steps)):
                col = ACCENT if i == self.idx else (70, 84, 74)
                pygame.draw.circle(surf, col, (x + 11 + i * 22, 300), 5)
        else:
            pygame.draw.circle(surf, ACCENT, (cx, 300), 5)

        # 动作提示
        y = WIN_H - 150
        for _key, label in self.actions:
            img = self.f_small.render(label, True, DIM)
            surf.blit(img, (cx - img.get_width() // 2, y))
            y += 26

        foot = self.f_small.render(
            f"{self.ctx.get('key', '')}   {self.idx + 1}/{len(self.steps)}", True, (90, 104, 94))
        surf.blit(foot, (52, WIN_H - 62))


def run(ctx: dict, screen: pygame.Surface | None = None,
        smoke: bool = False, frames: int = 0) -> str:
    """展示通关界面，返回动作：level/portal/restart/workshop/quit。"""
    cs = ClearScreen(ctx)
    if smoke:
        return "level" if (ctx.get("won") and ctx.get("next_key")) else "restart"

    own = screen is None
    if own:
        screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("植物工坊 · 通关")
    clock = pygame.time.Clock()
    frame = 0
    while True:
        for ev in pygame.event.get():
            act = cs.handle(ev)
            if act:
                return act
        cs.draw(screen)
        pygame.display.flip()
        frame += 1
        if frames and frame >= frames:
            return "level" if (ctx.get("won") and ctx.get("next_key")) else "restart"
        clock.tick(60)
