# -*- coding: utf-8 -*-
"""
精灵动画演示：单张 PNG 精灵表如何做出灵动效果。
按键：←/→ 移动（走路切帧+朝向翻转）  空格 攻击（squash & stretch）
      H 受击（白色闪白+后仰）  I 回待机  R 热重载贴图  Esc 退出
替换贴图：用同网格（4 行 x 4 列、每格 64px、行序 idle/walk/attack/hurt）的 PNG
覆盖 assets/sprites/blob.png，按 R 即可在运行中看到新图，无需重启。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "libs"))
import pygame
from animation import SpriteSheet, AnimatedSprite, FRAME, ANIM_DEF

WIN_W, WIN_H = 720, 480
GROUND_Y = 380
MOVE_SPEED = 220
SHEET_PATH = os.path.join(HERE, "assets", "sprites", "blob.png")


def make_font(size, bold=False):
    candidates = ([r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"] if bold
                  else [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"])
    for p in candidates:
        if os.path.exists(p):
            return pygame.font.Font(p, size)
    return pygame.font.Font(None, size)


class Demo:
    def __init__(self, sheet_path=SHEET_PATH):
        pygame.init()
        pygame.display.set_caption("精灵动画演示 - 单张贴图的灵动感")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.f18, self.f15, self.f24 = make_font(18), make_font(15), make_font(24, bold=True)
        self.sheet_path = sheet_path
        self.sheet = SpriteSheet(self.sheet_path)
        self.hero = AnimatedSprite(self.sheet, WIN_W // 2, GROUND_Y)
        self.moving = False

    def reload_sheet(self):
        self.hero.reload(SpriteSheet(self.sheet_path))

    def handle_key(self, key):
        if key == pygame.K_SPACE:
            self.hero.attack()
        elif key == pygame.K_h:
            self.hero.hurt()
        elif key == pygame.K_i:
            self.hero.play("idle", force=True)
        elif key == pygame.K_r:
            self.reload_sheet()

    def update(self, dt, left=False, right=False):
        dx = (1 if right else 0) - (1 if left else 0)
        self.moving = dx != 0 and self.hero.state in ("idle", "walk")
        if dx != 0 and self.hero.state in ("idle", "walk"):
            self.hero.facing = dx
            self.hero.x = max(40, min(WIN_W - 40, self.hero.x + dx * MOVE_SPEED * dt / 1000))
        self.hero.update(dt, moving=self.moving)

    def draw(self):
        # 背景渐变
        for y in range(WIN_H):
            t = y / WIN_H
            col = (int(214 - 40 * t), int(232 - 40 * t), int(245 - 60 * t))
            pygame.draw.line(self.screen, col, (0, y), (WIN_W, y))
        # 地面
        pygame.draw.rect(self.screen, (124, 160, 96), (0, GROUND_Y + 4, WIN_W, WIN_H - GROUND_Y))
        pygame.draw.line(self.screen, (96, 128, 74), (0, GROUND_Y + 4), (WIN_W, GROUND_Y + 4), 3)
        self.hero.draw(self.screen)
        # 顶部信息
        panel = pygame.Surface((WIN_W, 78), pygame.SRCALPHA)
        panel.fill((28, 36, 48, 210))
        self.screen.blit(panel, (0, 0))
        title = self.f24.render("单张贴图的灵动效果", True, (255, 255, 255))
        self.screen.blit(title, (18, 8))
        help_txt = "←→ 移动   空格 攻击   H 受击   I 待机   R 热重载贴图   Esc 退出"
        self.screen.blit(self.f15.render(help_txt, True, (205, 214, 224)), (18, 44))
        st = self.f18.render("状态：%s   帧：%d   缩放：%.2f / %.2f   %s"
                             % (self.hero.state, self.hero.frame_idx,
                                self.hero.sx, self.hero.sy,
                                "闪白中" if self.hero.flash_timer > 0 else ""),
                             True, (244, 196, 48))
        self.screen.blit(st, (18, WIN_H - 30))
        pygame.display.flip()

    def run(self):
        while True:
            dt = self.clock.tick(60)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    return
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_ESCAPE:
                        pygame.quit()
                        return
                    self.handle_key(e.key)
            keys = pygame.key.get_pressed()
            self.update(dt, keys[pygame.K_LEFT], keys[pygame.K_RIGHT])
            self.draw()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default=SHEET_PATH,
                    help="精灵表 PNG 路径（同 4x4、64px 网格），默认 assets/sprites/blob.png")
    args = ap.parse_args()
    Demo(os.path.abspath(args.sheet)).run()
