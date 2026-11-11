# -*- coding: utf-8 -*-
"""门户界面：启动先进这里，再进各个功能。

当前提供：
    继续（上次那关）/ 主线 M1 / 挑战 M2 / 对抗 M3 / 植物工坊 / 退出
以后加新功能（图鉴、教程、设置、成就）只需往 SECTIONS 里加一项。
"""
from __future__ import annotations

import os

import pygame

WIN_W, WIN_H = 1000, 620
BG = (15, 19, 24)
PANEL = (24, 30, 38)
LINE = (52, 64, 78)
FG = (232, 238, 245)
DIM = (140, 155, 170)
ACCENT = (245, 200, 92)
OK = (120, 210, 140)


def _load_font(size: int, bold: bool = False) -> pygame.font.Font:
    cands = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttf" if bold else "C:/Windows/Fonts/msyh.ttf",
        "C:/Windows/Fonts/simhei.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ]
    for p in cands:
        if os.path.exists(p):
            try:
                return pygame.font.Font(p, size)
            except Exception:                      # noqa: BLE001
                continue
    return pygame.font.SysFont("arial", size)


class Portal:
    """门户。SECTIONS 是数据驱动的菜单项，方便以后插新功能。"""

    # (id, 标题, 说明, 需要的关卡前缀)
    SECTIONS = [
        ("continue", "继续", "回到上次玩的那一关", None),
        ("m1", "主线 · 新手白天", "M1 共 18 关", "m1_"),
        ("m2", "挑战 · 四种能力考场", "M2 共 4 关，需顺序解锁", "m2_"),
        ("m3", "对抗 · 高压关卡", "M3 共 15 关 + Boss", "m3_"),
        ("workshop", "植物工坊", "自己设计植物（按 G 也可进入）", None),
        ("quit", "退出", "", None),
    ]

    def __init__(self, progress, levels: dict, last_key: str = "m1_01"):
        self.progress = progress
        self.levels = levels
        self.last_key = last_key
        self.idx = 0
        self.f_title = _load_font(40, bold=True)
        self.f_mid = _load_font(21)
        self.f_small = _load_font(16)
        self.f_big = _load_font(26, bold=True)
        self.rects: list[pygame.Rect] = []

    # ---------------------------------------------------------------- 兼容
    def _is_cleared(self, key: str) -> bool:
        """progress 里的 cleared 是列表（不是方法），这里统一入口。"""
        cl = getattr(self.progress, "cleared", None)
        if isinstance(cl, (set, list, tuple)):
            return key in cl
        if callable(cl):
            return bool(cl(key))
        return False

    # ---------------------------------------------------------------- 数据
    def _cleared_count(self, prefix: str) -> tuple[int, int]:
        keys = [k for k in self.levels if k.startswith(prefix)]
        done = sum(1 for k in keys if self._is_cleared(k))
        return done, len(keys)

    def _section_label(self, sid: str, title: str) -> str:
        if sid == "continue":
            return f"继续 · {self.last_key}"
        return title

    def _section_sub(self, sid: str, desc: str) -> str:
        prefixes = {"m1": "m1_", "m2": "m2_", "m3": "m3_"}
        if sid in prefixes:
            done, total = self._cleared_count(prefixes[sid])
            pct = int(done / total * 100) if total else 0
            return f"{desc}    已通关 {done}/{total}（{pct}%）"
        return desc

    # ---------------------------------------------------------------- 输入
    def handle(self, ev) -> tuple[str, str | None] | None:
        """返回 (动作, 关卡key) 或 None。"""
        if ev.type == pygame.QUIT:
            return ("quit", None)
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_UP, pygame.K_w):
                self.idx = (self.idx - 1) % len(self.SECTIONS)
            elif ev.key in (pygame.K_DOWN, pygame.K_s):
                self.idx = (self.idx + 1) % len(self.SECTIONS)
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self._activate(self.SECTIONS[self.idx][0])
            elif ev.key == pygame.K_g:
                return ("workshop", None)
            elif ev.key == pygame.K_q:
                return ("quit", None)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for i, r in enumerate(self.rects):
                if r.collidepoint(ev.pos):
                    self.idx = i
                    return self._activate(self.SECTIONS[i][0])
        return None

    def _activate(self, sid: str) -> tuple[str, str | None]:
        if sid == "quit":
            return ("quit", None)
        if sid == "workshop":
            return ("workshop", None)
        if sid == "continue":
            return ("play", self.last_key)
        prefix = {"m1": "m1_", "m2": "m2_", "m3": "m3_"}.get(sid)
        if prefix:
            # 选该组里第一个没通关的；都通了就回第一关
            keys = sorted(k for k in self.levels if k.startswith(prefix))
            if sid == "m2":
                keys = [k for k in keys if k in getattr(self.progress, "challenge_state", {})
                        or k.startswith("m2_")]
            for k in keys:
                if not self._is_cleared(k):
                    return ("play", k)
            return ("play", keys[0]) if keys else ("continue", self.last_key)
        return ("play", self.last_key)

    # ---------------------------------------------------------------- 绘制
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(BG)
        # 顶部
        t = self.f_title.render("植物工坊", True, ACCENT)
        surf.blit(t, (52, 34))
        sub = self.f_small.render("选一个入口（↑↓ 或鼠标，回车进入）", True, DIM)
        surf.blit(sub, (56, 84))

        # 右上角统计
        total = len(self.levels)
        done = sum(1 for k in self.levels if self._is_cleared(k))
        tokens = getattr(self.progress, "design_tokens", 0)
        stat = self.f_mid.render(f"总进度 {done}/{total}    设计币 {tokens}", True, FG)
        surf.blit(stat, (WIN_W - 52 - stat.get_width(), 44))

        # 菜单
        y = 130
        self.rects = []
        for i, (sid, title, desc, _prefix) in enumerate(self.SECTIONS):
            r = pygame.Rect(52, y, WIN_W - 104, 62)
            self.rects.append(r)
            active = i == self.idx
            pygame.draw.rect(surf, PANEL if not active else (34, 42, 52), r, border_radius=10)
            pygame.draw.rect(surf, ACCENT if active else LINE, r, 2 if active else 1,
                             border_radius=10)
            label = self.f_big.render(self._section_label(sid, title), True,
                                      FG if active else (200, 210, 220))
            surf.blit(label, (r.x + 18, r.y + 6))
            sub2 = self.f_small.render(self._section_sub(sid, desc), True, DIM)
            surf.blit(sub2, (r.x + 18, r.y + 36))
            if active:
                arrow = self.f_mid.render(">", True, ACCENT)
                surf.blit(arrow, (r.right - 32, r.y + 18))
            y += 70

        foot = self.f_small.render(
            "↑↓ 选择 · 回车进入 · G 工坊 · Q 退出", True, (100, 114, 128))
        surf.blit(foot, (52, WIN_H - 40))


def run(progress, levels: dict, last_key: str = "m1_01",
        screen: pygame.Surface | None = None, smoke: bool = False,
        frames: int = 0) -> tuple[str, str | None]:
    """展示门户，返回 (动作, 关卡key)。"""
    portal = Portal(progress, levels, last_key)
    if smoke:
        return portal._activate("continue")
    own = screen is None
    if own:
        screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("植物工坊 · 门户")
    pygame.display.flip()
    clock = pygame.time.Clock()
    frame = 0
    while True:
        for ev in pygame.event.get():
            act = portal.handle(ev)
            if act:
                return act
        portal.draw(screen)
        pygame.display.flip()
        frame += 1
        if frames and frame >= frames:
            return portal._activate("continue")
        clock.tick(60)
