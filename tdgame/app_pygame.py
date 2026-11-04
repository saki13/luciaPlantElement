# -*- coding: utf-8 -*-
"""pygame 薄渲染壳（M1：接入精灵表动画）。

职责边界（与 HANDOVER §3 一致）：headless 引擎（balance/engine/scenarios）承载全部确定性
逻辑与数值；本文件**只读** Registry 数据并把它画到屏幕上，绝不重算任何战斗公式。
棋盘上摆的植物/敌人是**纯展示场景**（固定格位、无 Simulation 步进），用于验证渲染通路。

本版相对 M0 色块版新增：
- key→精灵表路径映射：植物 `anim_demo/assets/sprites/<key>.png`，
  敌人 `anim_demo/assets/sprites/enemies/<key>.png`；
- 卡栏缩略图、棋盘植物、演示敌人全部走 `animation.SpriteSheet / AnimatedSprite`，
  带 idle/walk/attack 状态与底部锚点；
- 三级降级：精灵表缺失 → 色块占位；animation 模块导入失败 → 全局色块模式；
  `--no-sprites` 可强制色块模式做对照回归。

冒烟：
    set SDL_VIDEODRIVER=dummy && python -m tdgame.app_pygame --smoke --frames 3 --shot out.png
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pygame

from . import config as C
from .engine.loader import load_registry

# 绿色系卡板配色（避免大面积靛蓝/紫）
COL_GRASS_A = (124, 196, 92)
COL_GRASS_B = (108, 180, 80)
COL_PANEL = (236, 244, 226)
COL_LINE = (255, 255, 255)
COL_CARD = (214, 234, 196)
COL_PLANT = (64, 150, 72)
COL_ENEMY = (150, 74, 66)
COL_TEXT = (34, 60, 34)

ROOT = Path(__file__).resolve().parents[1]
ANIM_DIR = ROOT / "anim_demo"
SPRITE_ROOT = ANIM_DIR / "assets" / "sprites"

# 棋盘展示场景：5 行摆满全部 13 种植物的代表位（纯视图状态，不含战斗逻辑）
DEMO_PLANTS = [
    (0, 0, "sunbloom"), (0, 2, "peashooter"), (0, 4, "repeater"),
    (1, 0, "sunbloom"), (1, 2, "frostbell"), (1, 4, "melonpult"),
    (2, 0, "sunbloom"), (2, 2, "leafdancer"), (2, 4, "winter_melon"),
    (3, 0, "wallnut"), (3, 2, "bamboo"), (3, 4, "bombberry"),
    (4, 0, "pine_needler"), (4, 2, "morningglory"), (4, 4, "custom_shieldbreaker"),
]
# 敌人展示：8 种全部出场，混合 walk/idle/attack 三种状态
DEMO_ENEMIES = [
    (0, 7, "normal", "walk"), (0, 8, "cone", "walk"),
    (1, 6, "fast", "walk"), (1, 7, "banner", "idle"),
    (2, 5, "giant", "walk"), (2, 7, "bucket", "attack"),
    (3, 6, "shield_cadet", "walk"),
    (4, 6, "boss_50", "attack"),
]

PLANT_SCALE = C.CELL / 64 * 0.94      # 精灵表每格 64px，放大到填满 76px 棋盘格
ENEMY_SCALE = C.CELL / 64 * 1.06
GROUND_INSET = 6                      # 底部锚点离格底内缩，留一点草地


def _load_animation_module():
    """惰性导入 anim_demo/animation.py（它自己会把自包含 libs/ 插进 sys.path）。"""
    if str(ANIM_DIR) not in sys.path:
        sys.path.insert(0, str(ANIM_DIR))
    import animation  # noqa: WPS433 (运行期按需导入)
    return animation


class SpriteLibrary:
    """key → SpriteSheet 的缓存与降级。表缺失时返回 None，由调用方画色块。"""

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
        except Exception as exc:  # noqa: BLE001 - 任何导入问题都降级到色块
            self.enabled = False
            self.failed.append(("animation", repr(exc)))

    def path_for(self, key: str, kind: str = "plant") -> Path:
        sub = SPRITE_ROOT / "enemies" if kind == "enemy" else SPRITE_ROOT
        return sub / f"{key}.png"

    def sheet(self, key: str, kind: str = "plant"):
        if not self.enabled:
            return None
        path = self.path_for(key, kind)
        if path in self._cache:
            return self._cache[path]
        # 必须先判存在：SpriteSheet 在文件缺失时会**写字占位表**，渲染层不能落盘。
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

    def icon(self, key: str, kind: str, size: tuple[int, int]):
        """卡栏用静态缩略图（取 idle 首帧）。"""
        sheet = self.sheet(key, kind)
        if sheet is None:
            return None
        frame = sheet.frames["idle"][0]
        return pygame.transform.smoothscale(frame, size)

    def loaded_count(self) -> int:
        return sum(1 for v in self._cache.values() if v is not None)


class GameApp:
    def __init__(self, data_dir: str | Path | None = None, use_sprites: bool = True) -> None:
        pygame.init()
        pygame.display.set_caption("PVZ-like 薄壳（M1 精灵表渲染）")
        self.screen = pygame.display.set_mode((C.BOARD_W, C.TOP_H + C.ROWS * C.CELL))
        self.clock = pygame.time.Clock()
        data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
        self.registry = load_registry(data_dir)
        # 用内置默认字体，避免 SysFont 在部分 Windows 环境枚举系统字体崩溃；仅渲染英文 key/数字
        self.font = pygame.font.Font(None, 18)
        self.card_keys = list(self.registry.plants.keys())[: 8]
        # 精灵表必须在 set_mode 之后加载（convert_alpha 需要已建立视频模式）
        self.sprites = SpriteLibrary(use_sprites)
        self._icon_cache: dict[tuple[str, str, int, int], object] = {}
        self.scene_plants: list[dict] = []
        self.scene_enemies: list[dict] = []
        self._build_demo_scene()

    # ---- 展示场景（纯视图状态）----
    def _ground_y(self, row: int) -> int:
        return C.TOP_H + row * C.CELL + C.CELL - GROUND_INSET

    def _cell_cx(self, col: int) -> int:
        return col * C.CELL + C.CELL // 2

    def _build_demo_scene(self) -> None:
        anim = self.sprites.module
        for row, col, key in DEMO_PLANTS:
            sprite = None
            sheet = self.sprites.sheet(key, "plant")
            if sheet is not None:
                sprite = anim.AnimatedSprite(sheet, self._cell_cx(col), self._ground_y(row),
                                             scale=PLANT_SCALE)
            self.scene_plants.append(
                {"row": row, "col": col, "key": key, "sprite": sprite})
        for row, col, key, hint in DEMO_ENEMIES:
            sprite = None
            sheet = self.sprites.sheet(key, "enemy")
            if sheet is not None:
                sprite = anim.AnimatedSprite(sheet, self._cell_cx(col), self._ground_y(row),
                                             scale=ENEMY_SCALE)
                sprite.facing = -1                      # 敌人朝左前进
                if hint == "attack":
                    sprite.play("attack", force=True)
            self.scene_enemies.append(
                {"row": row, "col": col, "key": key, "hint": hint, "sprite": sprite})

    def advance(self, ms: int = 16) -> None:
        """推进动画时钟（不动任何战斗状态）。"""
        for item in self.scene_plants:
            if item["sprite"] is not None:
                item["sprite"].update(ms, moving=False)
        for item in self.scene_enemies:
            sp = item["sprite"]
            if sp is None:
                continue
            if item["hint"] == "attack":
                if sp.state != "attack":
                    sp.play("attack")
                sp.update(ms, moving=False)
            else:
                sp.update(ms, moving=item["hint"] == "walk")

    # ---- 绘制 ----
    def _board_rect(self, row: int, col: int):
        return pygame.Rect(col * C.CELL, C.TOP_H + row * C.CELL, C.CELL, C.CELL)

    def draw(self) -> None:
        self.screen.fill(COL_PANEL)
        self._draw_cards()
        self._draw_board()
        for item in self.scene_plants:
            if item["sprite"] is not None:
                item["sprite"].draw(self.screen)
            else:
                self._plant_dot(item["row"], item["col"])
        for item in self.scene_enemies:
            if item["sprite"] is not None:
                item["sprite"].draw(self.screen)
            else:
                self._enemy_dot(item["row"], item["col"])
        pygame.display.flip()

    def _draw_cards(self) -> None:
        pygame.draw.rect(self.screen, COL_PANEL, (0, 0, C.BOARD_W, C.TOP_H))
        for i, key in enumerate(self.card_keys):
            r = pygame.Rect(8 + i * 82, 10, 74, C.TOP_H - 20)
            pygame.draw.rect(self.screen, COL_CARD, r, border_radius=8)
            icon = self._card_icon(key)
            if icon is not None:
                self.screen.blit(icon, (r.x + (r.width - icon.get_width()) // 2, r.y + 3))
            else:
                pygame.draw.rect(self.screen, COL_PLANT, (r.x + 23, r.y + 6, 28, 28),
                                 border_radius=6)
            sun = self.registry.plants[key].get("sun", 0)
            self._text(str(sun), (r.x + 5, r.y + 47))
            self._text(key[:9], (r.x + 5, r.y + 59))

    def _card_icon(self, key: str):
        size = (44, 44)
        cache_key = (key, "plant", size[0], size[1])
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        icon = self.sprites.icon(key, "plant", size)
        self._icon_cache[cache_key] = icon
        return icon

    def _draw_board(self) -> None:
        for row in range(C.ROWS):
            for col in range(C.COLS):
                color = COL_GRASS_A if (row + col) % 2 == 0 else COL_GRASS_B
                pygame.draw.rect(self.screen, color, self._board_rect(row, col))
                pygame.draw.rect(self.screen, COL_LINE, self._board_rect(row, col), 1)

    def _plant_dot(self, row: int, col: int) -> None:
        r = self._board_rect(row, col)
        pygame.draw.circle(self.screen, COL_PLANT, r.center, C.CELL // 3)
        pygame.draw.circle(self.screen, (230, 255, 220),
                           (r.centerx - 8, r.centery - 8), 6)

    def _enemy_dot(self, row: int, col: int) -> None:
        r = self._board_rect(row, col)
        pygame.draw.circle(self.screen, COL_ENEMY, r.center, C.CELL // 3)
        pygame.draw.circle(self.screen, (255, 220, 210),
                           (r.centerx + 6, r.centery - 4), 4)

    def _text(self, s: str, pos) -> None:
        img = self.font.render(s, True, COL_TEXT)
        self.screen.blit(img, pos)

    # ---- 主循环 ----
    def run(self, frames_limit: int | None = None) -> None:
        frame = 0
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            # TODO(M1+)：在此接入 Simulation.step(DT) 与点选落子，用真实实体替换展示场景
            self.advance(16)
            self.draw()
            self.clock.tick(30)
            frame += 1
            if frames_limit is not None and frame >= frames_limit:
                running = False
        pygame.quit()

    def save_snapshot(self, path: str | Path, warmup_ms: int = 480) -> Path:
        """先把动画推进一小段，截图才不会全是第 0 帧。"""
        for _ in range(max(1, warmup_ms // 16)):
            self.advance(16)
        self.draw()
        path = Path(path)
        pygame.image.save(self.screen, str(path))
        return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="有限帧冒烟（可配合 dummy 驱动）")
    ap.add_argument("--frames", type=int, default=3)
    ap.add_argument("--shot", default="", help="冒烟截图保存路径")
    ap.add_argument("--no-sprites", action="store_true", help="强制色块占位（对照回归用）")
    args = ap.parse_args(argv)
    if args.smoke:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    app = GameApp(use_sprites=not args.no_sprites)
    lib = app.sprites
    print(f"sprites: enabled={lib.enabled} loaded={lib.loaded_count()} "
          f"missing={len(lib.missing)} failed={len(lib.failed)}")
    for item in lib.missing:
        print(f"  [missing] {item}")
    for key, err in lib.failed:
        print(f"  [failed] {key}: {err}")
    if args.shot:
        out = app.save_snapshot(args.shot)
        print("snapshot:", out)
    if args.smoke:
        app.run(frames_limit=args.frames)
    else:
        app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
