# -*- coding: utf-8 -*-
"""pygame 版可玩客户端（M1 交互层）。

职责边界（与 HANDOVER §3 一致）：headless 引擎承载全部战斗逻辑与数值，
本文件只做两件事——**把鼠标/键盘事件翻译成 `PlaySession` 的调用**，
以及**把 `session.status()/cards()/entities()` 画出来**。绝不重算任何战斗公式。

玩法：
    点卡栏选卡 -> 点格子种下；点铲子再点植物可铲除；R 重开；Q 退出。

命令：
    python -m tdgame.app_pygame                                      # 开窗口玩
    python -m tdgame.app_pygame --level m2_shield                    # 指定关卡
    python -m tdgame.app_pygame --smoke --frames 60 --shot out.png   # 离屏冒烟
    python -m tdgame.app_pygame --no-sprites                         # 色块降级对照
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pygame

from . import config as C
from .engine.loader import load_registry
from .engine.bot import RuleBot
from .engine.session import SHOVEL, PlaySession
from .scenarios.i_zombie import ZombieBot, ZombiePlaySession
from .scenarios.savegame import default_save_path, load_from, save_to
from .scenarios.level_run import load_levels

# ---- 配色 ----
COL_A = (126, 196, 95)
COL_B = (115, 185, 86)
COL_SEAM = (64, 112, 48)
COL_BORDER = (56, 97, 43)
COL_DIRT = (115, 92, 67)
COL_DIRT_D = (89, 70, 50)
COL_PANEL_BG = (242, 240, 222)
COL_PANEL_EDGE = (173, 168, 138)
COL_CARD = (254, 252, 240)
COL_CARD_DIM = (216, 216, 208)
COL_TEXT = (33, 61, 23)
COL_TEXT_DIM = (115, 115, 112)
COL_SUN = (251, 211, 73)
COL_SUN_RIM = (208, 160, 37)
COL_MOWER = (217, 64, 56)
COL_PROJ = (46, 82, 31)
COL_SHOVEL = (176, 132, 84)

TOP_H = C.TOP_H
CELL = C.CELL
ROWS = C.ROWS
COLS = C.COLS
GUTTER = C.BOARD_GUTTER
BOARD_W = COLS * CELL
WIN_W = GUTTER + BOARD_W
BAR_H = 26
WIN_H = TOP_H + ROWS * CELL + BAR_H

PLANT_SCALE = CELL / 64.0 * 0.94
ENEMY_SCALE = CELL / 64.0 * 1.06
GROUND_INSET = 6


def _load_animation_module():
    anim_dir = Path(__file__).resolve().parents[1] / "anim_demo"
    if str(anim_dir) not in sys.path:
        sys.path.insert(0, str(anim_dir))
    import animation  # noqa: WPS433
    return animation


def _load_font(size: int):
    """优先用系统中文字体；拿不到就退回内置字体并标记 cjk=False（改用英文文案）。"""
    for cand in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhl.ttc",
                 "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc",
                 "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"):
        if os.path.exists(cand):
            try:
                return pygame.font.Font(cand, size), True
            except Exception:  # noqa: BLE001
                continue
    return pygame.font.Font(None, size), False


class SpriteLibrary:
    """key -> SpriteSheet 的缓存与降级。表缺失时返回 None，由调用方画色块。"""

    SPRITE_ROOT = Path(__file__).resolve().parents[1] / "anim_demo" / "assets" / "sprites"

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.module = None
        self.missing: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self._cache: dict[Path, object] = {}
        if not enabled:
            return
        try:
            self.module = _load_animation_module()
        except Exception as exc:  # noqa: BLE001
            self.enabled = False
            self.failed.append(("animation", repr(exc)))

    def path_for(self, key: str, kind: str = "plant") -> Path:
        sub = self.SPRITE_ROOT / "enemies" if kind == "enemy" else self.SPRITE_ROOT
        return sub / f"{key}.png"

    def sheet(self, key: str, kind: str = "plant"):
        if not self.enabled:
            return None
        path = self.path_for(key, kind)
        if path in self._cache:
            return self._cache[path]
        # 必须先判存在：SpriteSheet 在文件缺失时会往磁盘写占位表
        if not path.exists():
            self.missing.append(f"{kind}:{key}")
            self._cache[path] = None
            return None
        try:
            sheet = self.module.SpriteSheet(str(path))
        except Exception as exc:  # noqa: BLE001
            self.failed.append((f"{kind}:{key}", repr(exc)))
            sheet = None
        self._cache[path] = sheet
        return sheet

    def loaded_count(self) -> int:
        return sum(1 for v in self._cache.values() if v is not None)


def _load_izombie_levels(directory: Path) -> dict:
    """读 M5 我是僵尸关卡（结构与主线关卡不同，单独一个加载器）。"""
    import json
    out = {}
    if not directory.is_dir():
        return out
    for f in sorted(directory.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:      # noqa: BLE001
            print(f"[izombie] 跳过 {f.name}: {exc}")
            continue
        out[d.get("key", f.stem)] = d
    return out


class GameApp:
    def __init__(self, data_dir: str | Path | None = None, use_sprites: bool = True,
                 level_key: str = "m1_01", seed: int = 1000, autoplay: bool = False,
                 mode: str = "play", save_path: str | Path | None = None) -> None:
        pygame.init()
        self.mode = mode
        pygame.display.set_caption(
            "PVZ-like 可玩版（M5 我是僵尸）" if mode == "izombie"
            else "PVZ-like 可玩版（M1）")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
        self.registry = load_registry(data_dir)
        if mode == "izombie":
            self.levels = _load_izombie_levels(data_dir / "izombie")
            default_key = "zombie_01"
        else:
            self.levels = load_levels(data_dir / "levels")
            default_key = "m1_01"
        if not self.levels:
            raise SystemExit(f"没有读到关卡：{data_dir}")
        self.level_key = level_key if level_key in self.levels else (
            default_key if default_key in self.levels else sorted(self.levels)[0])
        self.seed = seed
        self.autoplay = autoplay
        self.font, self.cjk = _load_font(18)
        self.big_font, _ = _load_font(56)
        if self.cjk:
            self.lbl_plants, self.lbl_enemies = "植物", "僵尸"
            self.lbl_restart = "R 重开  [ ] 换关  Q 退出"
            self.reason_text = {
                "no_sun": "阳光不足", "recharging": "卡片冷却中",
                "occupied": "这格已经有植物", "no_selection": "先选一张卡",
                "empty": "这格没有植物", "out_of_board": "超出棋盘",
                "over": "本局已结束",
            }
        else:
            self.lbl_plants, self.lbl_enemies = "plants", "zombies"
            self.lbl_restart = "R restart  [ ] level  Q quit"
            self.reason_text = {
                "no_sun": "not enough sun", "recharging": "recharging",
                "occupied": "occupied", "no_selection": "pick a card first",
                "empty": "nothing here", "out_of_board": "out of board",
                "over": "round over",
            }
        # 存档：坏档不会炸游戏，load_from 兜底成新档 + 一条 warning
        # 允许注入存档路径：测试必须用临时目录，否则会污染玩家真实存档
        self.save_path = Path(save_path) if save_path else default_save_path()
        self.progress, self.save_warning = load_from(self.save_path, self.levels)
        # 挑战关引导文案（救援通关后提示去工坊造克制植物）
        self.guide = ""
        self._recorded = False
        self.sprites = SpriteLibrary(use_sprites)
        self._build_visual_resources()
        self.cards_rect: list[tuple[pygame.Rect, str]] = []
        self.shovel_rect = pygame.Rect(0, 0, 0, 0)
        self.running = True
        self.message = ""
        self.message_t = 0.0
        self.new_game()

    # ------------------------------------------------------------------ 局
    def new_game(self) -> None:
        self.level = self.levels[self.level_key]
        if self.mode == "izombie":
            self.session = ZombiePlaySession(self.level, self.registry, seed=self.seed)
            self.bot = ZombieBot() if self.autoplay else None
        else:
            self.session = PlaySession(self.level, self.registry, seed=self.seed)
            self.bot = RuleBot(self.session.pool, smart=True) if self.autoplay else None
        self.views: dict[int, object] = {}
        self.message = ""
        self.message_t = 0.0
        self._recorded = False

    def open_workshop(self) -> None:
        """就地打开工坊；造完植物后重新开局本关。"""
        try:
            from . import ui_workshop_screen
            ui_workshop_screen.run(smoke=False, keep_display=True)
        except Exception as exc:              # noqa: BLE001 - 工坊崩了不该影响对局
            self.guide = f"工坊打不开：{exc.__class__.__name__}"
            return
        # 工坊刚写入了新的植物 JSON，必须重载注册表，否则新植物进不了卡池
        try:
            self.registry = load_registry(Path(__file__).parent / "data")
        except Exception:            # noqa: BLE001
            pass
        # 工坊改过显示尺寸/状态，回来后必须重建窗口，否则渲染会失效
        try:
            import pygame as _pg
            self.screen = _pg.display.set_mode((WIN_W, WIN_H))
            _pg.display.set_caption("PVZ-like")
        except Exception:            # noqa: BLE001
            pass
        self.guide = "已回到关卡。新造的植物已写入卡池，重打本关试试。"
        self.new_game()

    def _record_clear_if_needed(self) -> None:
        """通关时记一次进度并落盘。每局只记一次，避免每帧重复写文件。"""
        if self._recorded or not self.session.over or not self.session.won:
            return
        self._recorded = True
        if self.mode == "izombie":
            return          # M5 关卡不参与主线阶段解锁
        try:
            self.progress.clear_level(self.level_key)
            sim = getattr(self.session, "sim", None)
            rescues = int(getattr(sim, "rescues", 0)) if sim is not None else 0
            self.progress.record_challenge_result(self.level_key, True, rescues)
            if self.progress.needs_refight(self.level_key):
                self.guide = ("你被首车救援救了下来 —— 这一关还不算过。"
                              "按 G 去工坊造一株带「破盾」的植物，再回来重打本关。")
            elif self.progress.challenge_state.get(self.level_key) == "clean":
                self.guide = "干净通关！按 [ / ] 进入下一关。"
            save_to(self.save_path, self.progress)
        except Exception as exc:      # noqa: BLE001 - 存档失败不该影响玩
            self.save_warning = f"存档写入失败：{exc.__class__.__name__}"

    def level_available(self, key: str) -> bool:
        """挑战关必须按顺序解锁；已干净通关的可随时重打。"""
        from .scenarios.progression import CHALLENGE_LEVELS
        if key not in CHALLENGE_LEVELS:
            return True
        if self.progress.challenge_cleared(key):
            return True
        return self.progress.can_enter_challenge(key)

    def cycle_level(self, step: int) -> None:
        """按 [ / ] 在当前模式的关卡列表里前后切换（跳过未解锁的挑战关）。"""
        keys = [k for k in sorted(self.levels) if self.level_available(k)]
        if not keys:
            return
        if not keys:
            return
        try:
            idx = keys.index(self.level_key)
        except ValueError:
            idx = 0
        self.level_key = keys[(idx + step) % len(keys)]
        self.new_game()

    # ------------------------------------------------------------------ 素材
    def _build_visual_resources(self) -> None:
        self.grass = self._make_grass()
        self.panel = self._make_gradient((247, 245, 230), (226, 224, 201), 4, 64)
        self.panel_shadow = self._make_gradient((60, 60, 50, 56), (60, 60, 50, 0), 4, 32)
        self.shadow = self._make_radial_shadow()

    def _make_grass(self):
        import random
        rnd = random.Random(20261104)
        surf = pygame.Surface((96, 96), pygame.SRCALPHA)
        for _ in range(1400):
            x, y = rnd.randrange(96), rnd.randrange(96)
            a = rnd.randrange(8, 34)
            pygame.draw.circle(surf, (0, 0, 0, a), (x, y), rnd.choice((1, 1, 2, 3)))
        return pygame.transform.smoothscale(surf, (BOARD_W, ROWS * CELL))

    @staticmethod
    def _make_gradient(top, bottom, w, h):
        top = tuple(top) + ((255,) if len(top) == 3 else ())
        bottom = tuple(bottom) + ((255,) if len(bottom) == 3 else ())
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            k = y / max(1, h - 1)
            col = tuple(int(top[i] + (bottom[i] - top[i]) * k) for i in range(4))
            pygame.draw.line(surf, col, (0, y), (w, y))
        return surf

    def _make_radial_shadow(self):
        size = 64
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for r in range(size // 2, 0, -1):
            a = int(90 * (1 - r / (size / 2)) ** 0.7)
            pygame.draw.circle(surf, (0, 0, 0, a), (size // 2, size // 2), r)
        return surf

    # ------------------------------------------------------------------ 坐标
    def cell_rect(self, row: int, col: int) -> pygame.Rect:
        return pygame.Rect(GUTTER + col * CELL, TOP_H + row * CELL, CELL, CELL)

    def cell_at(self, pos):
        x, y = pos
        if x < GUTTER or y < TOP_H:
            return None
        col = (x - GUTTER) // CELL
        row = (y - TOP_H) // CELL
        if 0 <= row < ROWS and 0 <= col < COLS:
            return int(row), int(col)
        return None

    # ------------------------------------------------------------------ 输入
    def handle_event(self, ev) -> None:
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_g:
                self.open_workshop()
            elif ev.key in (pygame.K_q, pygame.K_ESCAPE):
                self.running = False
            elif ev.key == pygame.K_r:
                self.new_game()
            elif ev.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                self.cycle_level(-1 if ev.key == pygame.K_LEFTBRACKET else 1)
            elif ev.key == pygame.K_x:
                self.session.toggle_shovel()
            elif pygame.K_1 <= ev.key <= pygame.K_9:
                idx = ev.key - pygame.K_1
                cards = self.session.cards()
                if idx < len(cards):
                    self.session.select(cards[idx]["key"])
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self._on_click(ev.pos)

    def _on_click(self, pos) -> None:
        for rect, key in self.cards_rect:
            if rect.collidepoint(pos):
                self.session.select(key)
                return
        if self.shovel_rect.collidepoint(pos):
            self.session.toggle_shovel()
            return
        cell = self.cell_at(pos)
        if cell is None:
            return
        ok, reason = self.session.click_cell(*cell)
        if not ok:
            self.message = self.reason_text.get(reason, reason)
            self.message_t = 2.0

    # ------------------------------------------------------------------ 主循环
    def advance(self, dt_seconds: float) -> None:
        if self.bot is not None and not self.session.over:
            target = self.session.core if self.mode == "izombie" else self.session.sim
            self.bot.think(target)
        self.session.tick(dt_seconds)
        self._record_clear_if_needed()
        if self.message_t > 0:
            self.message_t -= dt_seconds
            if self.message_t <= 0:
                self.message = ""

    def run(self, frames_limit: int | None = None, dt_seconds: float = 1 / 60) -> None:
        frame = 0
        while self.running:
            for ev in pygame.event.get():
                self.handle_event(ev)
            self.advance(dt_seconds)
            self.draw()
            self.clock.tick(60)
            frame += 1
            if frames_limit is not None and frame >= frames_limit:
                self.running = False
        pygame.quit()

    # ------------------------------------------------------------------ 绘制
    def draw(self) -> None:
        s = self.screen
        s.fill(COL_PANEL_BG)
        self._draw_top_panel()
        self._draw_board()
        self._draw_entities()
        self._draw_bottom_bar()
        self._draw_overlay()
        pygame.display.flip()

    def _draw_top_panel(self) -> None:
        s = self.screen
        s.blit(self.panel, (0, 0))
        pygame.draw.line(s, COL_PANEL_EDGE, (0, TOP_H), (WIN_W, TOP_H), 2)

        cards = self.session.cards()
        n = max(1, len(cards))
        gap = 6
        card_w = min(64, (BOARD_W - 100 - (n - 1) * gap) / n)
        card_h = TOP_H - 20
        total = n * card_w + (n - 1) * gap
        x0 = GUTTER + (BOARD_W - total) / 2
        self.cards_rect = []

        for i, card in enumerate(cards):
            cx = int(x0 + i * (card_w + gap))
            rect = pygame.Rect(cx, 10, int(card_w), int(card_h))
            self.cards_rect.append((rect, card["key"]))
            usable = card["affordable"] and card["ready"]
            pygame.draw.rect(s, COL_CARD if usable else COL_CARD_DIM, rect, border_radius=6)
            pygame.draw.rect(s, (60, 60, 50) if card["selected"] else COL_PANEL_EDGE,
                             rect, 3 if card["selected"] else 1, border_radius=6)

            icon_kind = "enemy" if self.mode == "izombie" else "plant"
            sheet = self.sprites.sheet(card["key"], icon_kind)
            icon_size = max(8, int(card_w - 10))
            if sheet is not None:
                frame = sheet.frames["idle"][0]
                icon = pygame.transform.smoothscale(frame, (icon_size, icon_size))
                if not usable:
                    icon = icon.copy()
                    icon.fill((110, 110, 110), special_flags=pygame.BLEND_RGB_SUB)
                s.blit(icon, (rect.x + 5, rect.y + 3))
            else:
                pygame.draw.rect(s, (64, 150, 72),
                                 (rect.x + 12, rect.y + 8, icon_size - 8, icon_size - 8),
                                 border_radius=4)

            if card["cd"] > 0 and card["cd_max"] > 0:
                k = min(1.0, card["cd"] / card["cd_max"])
                h = int(rect.height * k)
                mask = pygame.Surface((rect.width, h), pygame.SRCALPHA)
                mask.fill((20, 30, 20, 140))
                s.blit(mask, (rect.x, rect.y + rect.height - h))

            # 价格标签：右下角胶囊底 + 数字，完全落在卡内
            # （早先是直接 blit 在 (x+4, bottom-16)，数字会被卡框裁掉半截）
            small, _ = _load_font(15)
            txt = small.render(str(card["sun"]), True,
                               COL_TEXT if usable else COL_TEXT_DIM)
            pad_x, pad_y = 5, 1
            pill_w = txt.get_width() + pad_x * 2
            pill_h = txt.get_height() + pad_y * 2
            pill = pygame.Rect(rect.right - pill_w - 3, rect.bottom - pill_h - 3,
                               pill_w, pill_h)
            badge = pygame.Surface((pill.width, pill.height), pygame.SRCALPHA)
            badge.fill((250, 244, 222, 225) if usable else (208, 204, 192, 200))
            s.blit(badge, pill.topleft)
            pygame.draw.rect(s, COL_PANEL_EDGE, pill, 1, border_radius=6)
            s.blit(txt, (pill.x + pad_x, pill.y + pad_y))

        if self.mode == "izombie":
            # 我是僵尸：植物是预置的，没有铲子这回事
            self.shovel_rect = pygame.Rect(0, 0, 0, 0)
            return
        self.shovel_rect = pygame.Rect(int(x0 + total + 8), 10, 40, int(card_h))
        sel = self.session.selected == SHOVEL
        pygame.draw.rect(s, (240, 226, 196) if sel else COL_CARD, self.shovel_rect,
                         border_radius=6)
        pygame.draw.rect(s, (60, 60, 50) if sel else COL_PANEL_EDGE, self.shovel_rect,
                         3 if sel else 1, border_radius=6)
        cx, cy = self.shovel_rect.center
        pygame.draw.rect(s, COL_SHOVEL, (cx - 3, cy - 9, 6, 14), border_radius=2)
        pygame.draw.rect(s, (120, 90, 56), (cx - 8, cy + 5, 16, 4), border_radius=2)

    def _draw_board(self) -> None:
        s = self.screen
        for r in range(ROWS):
            for c in range(COLS):
                pygame.draw.rect(s, COL_A if (r + c) % 2 == 0 else COL_B, self.cell_rect(r, c))
        s.blit(self.grass, (GUTTER, TOP_H))
        for r in range(1, ROWS):
            y = TOP_H + r * CELL
            pygame.draw.line(s, COL_SEAM, (GUTTER, y), (GUTTER + BOARD_W, y), 1)
        for c in range(1, COLS):
            x = GUTTER + c * CELL
            pygame.draw.line(s, COL_SEAM, (x, TOP_H), (x, TOP_H + ROWS * CELL), 1)

        pygame.draw.rect(s, COL_DIRT, (0, TOP_H, GUTTER, ROWS * CELL))
        pygame.draw.line(s, COL_DIRT_D, (GUTTER, TOP_H), (GUTTER, TOP_H + ROWS * CELL), 2)
        pygame.draw.rect(s, COL_BORDER, (GUTTER, TOP_H, BOARD_W, ROWS * CELL), 2)
        s.blit(self.panel_shadow, (GUTTER, TOP_H))

        for r in range(ROWS):
            if r < self.session.lives:
                cx, cy = GUTTER // 2, TOP_H + r * CELL + CELL // 2
                pygame.draw.circle(s, COL_MOWER, (cx, cy), 10)
                pygame.draw.circle(s, COL_SUN, (cx, cy), 6)
                pygame.draw.circle(s, (70, 48, 36), (cx, cy), 2)

    def _sprite_for(self, uid: int, key: str, kind: str):
        if uid in self.views:
            return self.views[uid]
        sheet = self.sprites.sheet(key, kind)
        if sheet is None:
            self.views[uid] = None
            return None
        scale = PLANT_SCALE if kind == "plant" else ENEMY_SCALE
        sprite = self.sprites.module.AnimatedSprite(sheet, 0, 0, scale=scale)
        if kind == "enemy":
            sprite.facing = -1
        self.views[uid] = sprite
        return sprite

    def _draw_entities(self) -> None:
        s = self.screen
        data = self.session.entities()
        alive = set()

        for p in data["plants"]:
            uid = hash(("p", p["row"], p["col"], p["key"]))
            alive.add(uid)
            sprite = self._sprite_for(uid, p["key"], "plant")
            if sprite is None:
                r = self.cell_rect(p["row"], p["col"])
                pygame.draw.circle(s, (64, 150, 72), r.center, CELL // 3)
                continue
            sprite.x = GUTTER + int((p["col"] + 0.5) * CELL)
            sprite.ground_y = TOP_H + p["row"] * CELL + CELL - GROUND_INSET
            sprite.update(16, moving=False)
            sprite.draw(s)

        for e in data["enemies"]:
            uid = hash(("e", e["row"], e["key"], round(e["x"], 1)))
            alive.add(uid)
            sprite = self._sprite_for(uid, e["key"], "enemy")
            px = GUTTER + int((e["x"] + 0.4) * CELL)
            py = TOP_H + e["row"] * CELL + CELL - GROUND_INSET
            if sprite is None:
                pygame.draw.circle(s, (150, 74, 66), (px, py - CELL // 3), CELL // 3)
                continue
            sprite.x = px
            sprite.ground_y = py
            if e["eating"]:
                if sprite.state != "attack":
                    sprite.play("attack")
                sprite.update(16, moving=False)
            else:
                sprite.update(16, moving=True)
            sprite.draw(s)

        for old in list(self.views):
            if old not in alive:
                self.views.pop(old, None)

        for pr in data["projectiles"]:
            px = GUTTER + int(pr["x"] * CELL)
            py = TOP_H + pr["row"] * CELL + CELL // 2
            pygame.draw.circle(s, (255, 255, 255), (px, py), 5)
            pygame.draw.circle(s, COL_PROJ, (px, py), 4)

    def _draw_bottom_bar(self) -> None:
        s = self.screen
        y = TOP_H + ROWS * CELL
        s.blit(self.panel, (0, y))
        pygame.draw.line(s, COL_PANEL_EDGE, (0, y), (WIN_W, y), 2)
        cy = y + BAR_H // 2
        pygame.draw.circle(s, COL_SUN, (18, cy), 9)
        pygame.draw.circle(s, COL_SUN_RIM, (18, cy), 9, 2)
        s.blit(self.font.render(str(self.session.sun), True, COL_TEXT), (31, cy - 7))

        st = self.session.status()
        info = (f"{st['level']}  t={st['time']:.0f}s  "
                f"{self.lbl_plants} {st['plants']}  {self.lbl_enemies} {st['enemies']}")
        s.blit(self.font.render(info, True, (76, 86, 66)), (92, cy - 7))

        if self.message:
            img = self.font.render(self.message, True, (170, 60, 40))
            s.blit(img, (WIN_W - img.get_width() - 120, cy - 7))

        # 进度 HUD：已通关数 / 设计币 / 爬塔层数（来自存档）
        if self.mode != "izombie":
            cleared = len(self.progress.cleared)
            total = len(self.levels)
            hud = f"{cleared}/{total}  币 {self.progress.design_tokens}"
        if self.guide:
            hud += "   " + self.guide
            if getattr(self.progress, "tower_floor", 0) > 0:
                hud += f"  塔 {self.progress.tower_floor}"
            img = self.font.render(hud, True, (60, 76, 52))
            s.blit(img, (WIN_W - img.get_width() - 130, cy - 7))

        for i in range(max(0, self.session.lives)):
            cx = WIN_W - 16 - i * 18
            pygame.draw.circle(s, COL_MOWER, (cx, cy), 7)
            pygame.draw.circle(s, COL_SUN, (cx, cy), 4)

    def _draw_overlay(self) -> None:
        if not self.session.over:
            return
        s = self.screen
        veil = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        veil.fill((10, 20, 10, 150))
        s.blit(veil, (0, 0))
        win = self.session.won
        title = "CLEARED" if win else "GAME OVER"
        col = (240, 255, 210) if win else (255, 190, 180)
        img = self.big_font.render(title, True, col)
        s.blit(img, (WIN_W // 2 - img.get_width() // 2, WIN_H // 2 - 46))
        hint = self.font.render(self.lbl_restart, True, (230, 230, 220))
        s.blit(hint, (WIN_W // 2 - hint.get_width() // 2, WIN_H // 2 + 10))

    def save_snapshot(self, path: str | Path, warmup_frames: int = 30) -> Path:
        for _ in range(warmup_frames):
            self.advance(1 / 60)
        self.draw()
        path = Path(path)
        pygame.image.save(self.screen, str(path))
        return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="m1_01")
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--smoke", action="store_true", help="有限帧冒烟（可配合 dummy 驱动）")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--shot", default="", help="冒烟截图保存路径")
    ap.add_argument("--no-sprites", action="store_true", help="强制色块占位（对照回归用）")
    ap.add_argument("--autoplay", action="store_true", help="用 RuleBot 自动对局（截图/演示用）")
    ap.add_argument("--warmup", type=float, default=0.5, help="截图前先推进几秒")
    ap.add_argument("--mode", default="play", choices=("play", "izombie", "workshop"),
                    help="play=主线守关；izombie=M5 我是僵尸（攻防反转）")
    args = ap.parse_args(argv)

    if args.smoke:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    if args.mode == "workshop":
        from . import ui_workshop_screen
        return ui_workshop_screen.run(smoke=args.smoke,
                                     frames=getattr(args, "frames", 0),
                                     shot=getattr(args, "shot", None))

    app = GameApp(use_sprites=not args.no_sprites, level_key=args.level, seed=args.seed,
                  autoplay=args.autoplay, mode=args.mode)
    lib = app.sprites
    print(f"level={app.level_key} sprites_enabled={lib.enabled} loaded={lib.loaded_count()} "
          f"missing={len(lib.missing)} failed={len(lib.failed)}")
    for item in lib.missing:
        print(f"  [missing] {item}")
    for key, err in lib.failed:
        print(f"  [failed] {key}: {err}")

    if args.shot:
        if args.warmup > 0:
            steps = max(1, int(args.warmup * 60))
            for _ in range(steps):
                app.advance(1 / 60)
        app.draw()
        out = app.save_snapshot(args.shot, warmup_frames=1)
        print("snapshot:", out)
    if args.smoke:
        app.run(frames_limit=args.frames)
    else:
        app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
