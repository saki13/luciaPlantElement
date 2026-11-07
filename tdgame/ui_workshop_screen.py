# -*- coding: utf-8 -*-
"""工坊的 pygame 界面（键鼠都可操作，也支持 --smoke 无头自检）。"""
from __future__ import annotations

import sys
from typing import Optional

from .ui_workshop import (AXES, AXIS_CN, ROLES, ROLE_CN, TAGS, TAG_CN,
                          WorkshopState, render_state)

BG = (28, 32, 40)
FG = (232, 236, 242)
DIM = (140, 150, 165)
OK = (120, 220, 140)
BAD = (240, 120, 120)
ACCENT = (250, 200, 90)
ROW_H = 34
WIN_W, WIN_H = 720, 560


def run(smoke: bool = False, frames: int = 0, shot: Optional[str] = None) -> int:
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("植物工坊")
    from .app_pygame import _load_font
    font, cjk = _load_font(22)
    small, _ = _load_font(18)

    st = WorkshopState()
    rows = [(f"axis:{a}", AXIS_CN[a], a) for a in AXES] + \
           [(f"tag:{t}", f"{TAG_CN[t]}", t) for t in TAGS]
    top = 138
    clock = pygame.time.Clock()
    built = None
    running = True
    n = 0

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_r:
                    st.cycle_role()
                elif ev.key == pygame.K_RETURN and st.can_build:
                    built = st.build()
                    running = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                x, y = ev.pos
                idx = (y - top) // ROW_H
                if 0 <= idx < len(rows):
                    kind, _cn, key = rows[idx]
                    if kind.startswith("axis:"):
                        st.bump(key, +1 if x > WIN_W * 0.6 else -1)
                    else:
                        st.toggle_tag(key)
        if smoke and n > frames:
            break

        screen.fill(BG)
        screen.blit(font.render("植物工坊 —— 设计你自己的植物", True, FG), (24, 18))
        screen.blit(small.render(
            f"阶段 {st.phase}   角色 {ROLE_CN[st.role]}（按 R 切换）   "
            f"代币 {st.tokens}", True, DIM), (24, 46))
        hint = small.render(
            "左键点左侧 -1 / 右侧 +1；点标签切换；回车建造；ESC 退出", True, DIM)
        screen.blit(hint, (24, 70))

        for i, (kind, label, key) in enumerate(rows):
            y = top + i * ROW_H
            is_tag = kind.startswith("tag:")
            if is_tag:
                mark = "√" if key in st.tags else ("×" if st.tag_available(key) else "-")
                color = OK if key in st.tags else (DIM if st.tag_available(key) else (90, 90, 100))
                screen.blit(font.render(f"[{mark}] {label}", True, color), (36, y))
            else:
                lv = st.levels[key]
                cap = 5
                bar = "#" * lv + "." * (cap - lv)
                screen.blit(font.render(f"{label}", True, FG), (36, y))
                screen.blit(font.render(bar, True, ACCENT), (150, y))
                screen.blit(small.render(f"{lv}/{cap}", True, DIM), (320, y))

        cost, why = st.summary()
        yb = WIN_H - 92
        pygame.draw.line(screen, (60, 66, 78), (24, yb - 8), (WIN_W - 24, yb - 8))
        screen.blit(font.render(f"消耗代币 {cost} / {st.tokens}", True,
                                OK if st.affordable else BAD), (24, yb))
        msg = why if why else "按回车建造"
        screen.blit(font.render(msg, True, BAD if why else OK), (24, yb + 26))

        if shot and n == frames:
            pygame.image.save(screen, shot)
        pygame.display.flip()
        clock.tick(60)
        n += 1

    if smoke:
        print(render_state(st))
        if built:
            print("built:", built.get("key"), built.get("tags"))
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(run("--smoke" in sys.argv))
