# -*- coding: utf-8 -*-
"""植物工坊界面：左侧配能力，右侧实时看外观 + 预览 + 一键生成。

布局：
  左半  —— 轴位增减、标签开关、角色切换
  右半  —— 根据能力实时推导的外观描述、当前精灵表预览、「生成外观」按钮
  底部  —— 代币消耗与校验提示

设计说明：外观描述随能力实时变化，让玩家一眼看出「我这么配，它会长成什么样」，
这正是本作"自己设计植物"的核心体验。
"""
from __future__ import annotations

import sys
from typing import Optional

from .ui_workshop import (AXES, AXIS_CN, ROLE_CN, TAGS, TAG_CN,
                          ArtGenerator, WorkshopState, render_state)

BG = (26, 30, 38)
PANEL = (36, 42, 52)
FG = (232, 236, 242)
DIM = (140, 150, 165)
OK = (120, 220, 140)
BAD = (240, 120, 120)
ACCENT = (250, 200, 90)

WIN_W, WIN_H = 1000, 620
ROW_H = 34
LEFT_TOP = 150
RIGHT_X = 520


def _wrap(text: str, font, width: int) -> list:
    """按像素宽度折行（中文没有空格，只能逐字试）。"""
    lines, cur = [], ""
    for ch in text:
        if font.size(cur + ch)[0] > width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def run(smoke: bool = False, frames: int = 0, shot: Optional[str] = None,
        keep_display: bool = False) -> int:
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("植物工坊")
    from .app_pygame import _load_font
    font, _cjk = _load_font(22)
    small, _ = _load_font(17)
    tiny, _ = _load_font(15)

    st = WorkshopState()
    gen = ArtGenerator(st)
    rows = [(f"axis:{a}", AXIS_CN[a], a) for a in AXES] + \
           [(f"tag:{t}", TAG_CN[t], t) for t in TAGS]

    BTN = pygame.Rect(RIGHT_X, WIN_H - 150, 440, 42)
    preview = None
    preview_loaded_for = None
    built = None
    running = True
    n = 0
    clock = pygame.time.Clock()

    def load_preview():
        nonlocal preview, preview_loaded_for
        if not st.has_sprite():
            preview, preview_loaded_for = None, None
            return
        key = st.plant_key()
        if preview_loaded_for == key:
            return
        try:
            img = pygame.image.load(str(st.sprite_path())).convert_alpha()
            preview = pygame.transform.smoothscale(img, (120, 120))
            preview_loaded_for = key
        except Exception:            # noqa: BLE001
            preview, preview_loaded_for = None, None

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_r:
                    st.cycle_role()
                elif ev.key == pygame.K_g:
                    gen.state = st
                    gen.start()
                elif ev.key == pygame.K_RETURN and st.can_build and not gen.busy:
                    built = st.build(save=True)
                    running = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if BTN.collidepoint(ev.pos):
                    gen.state = st
                    gen.start()
                else:
                    idx = (ev.pos[1] - LEFT_TOP) // ROW_H
                    if 0 <= idx < len(rows) and ev.pos[0] < RIGHT_X - 20:
                        kind, _cn, key = rows[idx]
                        if kind.startswith("axis:"):
                            st.bump(key, +1 if ev.pos[0] > 250 else -1)
                        else:
                            st.toggle_tag(key)

        if gen.status == ArtGenerator.OK:
            load_preview()
            gen.status = ArtGenerator.IDLE      # 只处理一次

        if smoke and n > frames:
            break

        screen.fill(BG)
        screen.blit(font.render("植物工坊 —— 设计你自己的植物", True, FG), (24, 16))
        screen.blit(small.render(
            f"阶段 {st.phase}   角色 {ROLE_CN[st.role]}（R 切换）   代币 {st.tokens}",
            True, DIM), (24, 46))
        screen.blit(tiny.render(
            "左键点数值左侧 -1 / 右侧 +1；点标签开关；G 生成外观；回车建造；ESC 退出",
            True, DIM), (24, 72))

        # ---------------- 左：能力
        screen.blit(small.render("能力配置", True, ACCENT), (36, 116))
        for i, (kind, label, key) in enumerate(rows):
            y = LEFT_TOP + i * ROW_H
            if kind.startswith("tag:"):
                mark = "√" if key in st.tags else ("×" if st.tag_available(key) else "-")
                color = OK if key in st.tags else (DIM if st.tag_available(key) else (90, 90, 100))
                screen.blit(font.render(f"[{mark}] {label}", True, color), (36, y))
            else:
                lv = st.levels[key]
                bar = "#" * lv + "." * (5 - lv)
                screen.blit(font.render(label, True, FG), (36, y))
                screen.blit(font.render(bar, True, ACCENT), (140, y))
                screen.blit(small.render(f"{lv}", True, DIM), (300, y))

        # ---------------- 右：外观
        pygame.draw.rect(screen, PANEL, (RIGHT_X - 16, 108, WIN_W - RIGHT_X, WIN_H - 268))
        screen.blit(small.render("外观（随能力实时变化）", True, ACCENT), (RIGHT_X, 116))
        for i, ln in enumerate(_wrap(st.appearance_prompt(), tiny, WIN_W - RIGHT_X - 32)[:7]):
            screen.blit(tiny.render(ln, True, FG), (RIGHT_X, 146 + i * 21))

        py0 = 328
        pygame.draw.rect(screen, (20, 24, 30), (RIGHT_X, py0, 120, 120))
        if preview:
            screen.blit(preview, (RIGHT_X, py0))
        else:
            screen.blit(tiny.render("还没有外观", True, DIM), (RIGHT_X + 14, py0 + 50))
        screen.blit(tiny.render(f"key: {st.plant_key()}", True, DIM),
                    (RIGHT_X + 140, py0 + 4))
        status_color = {"running": ACCENT, "ok": OK, "fail": BAD}.get(gen.status, DIM)
        msg = gen.message or ("按 G 或点下方按钮生成外观"
                              if not st.has_sprite() else "已有外观，可重新生成")
        for i, ln in enumerate(_wrap(msg, tiny, 220)[:3]):
            screen.blit(tiny.render(ln, True, status_color),
                        (RIGHT_X + 140, py0 + 28 + i * 19))

        # ---------------- 底部
        pygame.draw.rect(screen, ACCENT if not gen.busy else (80, 80, 90), BTN,
                         border_radius=8)
        label = "生成中…" if gen.busy else "生成外观（G）"
        tw = small.size(label)[0]
        screen.blit(small.render(label, True, (20, 20, 20)),
                    (BTN.x + (BTN.w - tw) // 2, BTN.y + 12))

        cost, why = st.summary()
        yb = WIN_H - 92
        pygame.draw.line(screen, (60, 66, 78), (24, yb - 8), (WIN_W - 24, yb - 8))
        screen.blit(font.render(f"消耗代币 {cost} / {st.tokens}", True,
                                OK if st.affordable else BAD), (24, yb))
        hint = why if why else ("按回车建造" if not gen.busy else "生成外观中，稍候…")
        screen.blit(font.render(hint, True, BAD if why else OK), (24, yb + 26))

        if shot and n == frames:
            pygame.image.save(screen, shot)
        pygame.display.flip()
        clock.tick(60)
        n += 1

    if smoke:
        print(render_state(st))
        if built:
            print("built:", built.get("key"), built.get("tags"))
    if not keep_display:
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(run("--smoke" in sys.argv))
