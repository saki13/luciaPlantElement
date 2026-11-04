# -*- coding: utf-8 -*-
"""
可复用的 2D 精灵动画框架（pygame）。
能力：
  - 外部 PNG 精灵表优先加载；文件缺失时自动程序化生成一张占位精灵表（回退，保证永远可运行）。
  - 固定网格约定：每行一个状态，每格 FRAME 像素；行序 idle/walk/attack/hurt。
  - 按毫秒推进切帧，支持循环 / 单次（单次结束自动回 idle）。
  - 程序化动效叠加：呼吸/脚步缩放、攻击 squash & stretch、受击白色剪影、左右朝向翻转。
真图替换：把同尺寸（或同网格）的 PNG 放到同名路径即可，无需改代码；运行中按 R 可热重载。
"""
import os
import sys
import math

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "libs"))
import pygame

FRAME = 64
# 状态 -> (所在行, 帧数, 每帧毫秒, 是否循环)
ANIM_DEF = {
    "idle":   (0, 2, 460, True),
    "walk":   (1, 4, 130, True),
    "attack": (2, 3, 150, False),
    "hurt":   (3, 2, 160, False),
}
ORDER = ["idle", "walk", "attack", "hurt"]
MAX_COLS = 4
BODY = (94, 176, 132)
BODY_D = (58, 130, 96)
DARK = (36, 74, 58)


# ---------------- 程序化占位精灵表 ----------------
def _blob(surf, ox, oy, sx, sy, eye_dx, blink, mouth, lean=0):
    """以 (ox,oy) 为底部锚点画一只原创造型史莱姆，sx/sy 控制挤压、lean 控制前倾。"""
    w, h = int(44 * sx), int(40 * sy)
    cx, base = ox + 32 + lean, oy + 58
    rect = pygame.Rect(cx - w // 2, base - h, w, h)
    pygame.draw.ellipse(surf, BODY_D, rect.move(2, 3))          # 投影式暗边
    pygame.draw.ellipse(surf, BODY, rect)
    pygame.draw.ellipse(surf, tuple(min(255, c + 35) for c in BODY),
                        pygame.Rect(rect.x + 8, rect.y + 6, w // 2, h // 3))
    # 眼睛
    ey = base - int(h * 0.55)
    for s in (-1, 1):
        ex = cx + s * eye_dx + lean
        if blink:
            pygame.draw.line(surf, DARK, (ex - 4, ey), (ex + 4, ey), 2)
        else:
            pygame.draw.circle(surf, (255, 255, 255), (ex, ey), 5)
            pygame.draw.circle(surf, DARK, (ex + 1 + lean // 3, ey), 2)
    # 嘴
    if mouth == "o":
        pygame.draw.circle(surf, DARK, (cx, ey + 8), 3)
    else:
        pygame.draw.arc(surf, DARK, (cx - 6, ey + 4, 12, 10), math.pi, math.tau, 2)


def generate_placeholder_sheet(path):
    sheet = pygame.Surface((FRAME * MAX_COLS, FRAME * len(ORDER)), pygame.SRCALPHA)
    for name in ORDER:
        row, cols, _, _ = ANIM_DEF[name]
        oy = row * FRAME
        for f in range(cols):
            ox = f * FRAME
            if name == "idle":
                _blob(sheet, ox, oy, 1.0 if f == 0 else 1.08, 1.0 if f == 0 else 0.92,
                      9, blink=(f == 1), mouth="arc")
            elif name == "walk":
                lean = (-3, 2, 3, -2)[f]
                _blob(sheet, ox, oy, 1.06 if f % 2 else 0.96, 0.94 if f % 2 else 1.05,
                      9, blink=False, mouth="arc", lean=lean)
            elif name == "attack":
                if f == 0:      # 蓄力：压扁后缩
                    _blob(sheet, ox, oy, 1.22, 0.78, 8, False, "o", lean=-4)
                elif f == 1:    # 突刺：纵向拉伸前冲
                    _blob(sheet, ox, oy, 0.86, 1.18, 10, False, "o", lean=8)
                else:           # 回收
                    _blob(sheet, ox, oy, 1.04, 0.96, 9, False, "arc", lean=2)
            else:  # hurt
                if f == 0:
                    _blob(sheet, ox, oy, 1.1, 0.9, 9, True, "o", lean=-5)
                else:
                    _blob(sheet, ox, oy, 0.95, 1.05, 9, True, "o", lean=-7)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pygame.image.save(sheet, path)
    return path


# ---------------- 精灵表 / 动画 / 角色 ----------------
class SpriteSheet:
    def __init__(self, path):
        if not os.path.exists(path):
            generate_placeholder_sheet(path)
        raw = pygame.image.load(path).convert_alpha()
        self.frames, self.flash = {}, {}
        for name in ORDER:
            row, cols, _, _ = ANIM_DEF[name]
            seq, white = [], []
            for c in range(cols):
                frame = raw.subsurface(pygame.Rect(c * FRAME, row * FRAME, FRAME, FRAME)).copy()
                seq.append(frame)
                fl = frame.copy()
                fl.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)  # 保留形状、整体染白
                white.append(fl)
            self.frames[name] = seq
            self.flash[name] = white


class AnimatedSprite:
    def __init__(self, sheet, x, ground_y, scale=1.0):
        self.sheet = sheet
        self.x, self.ground_y = x, ground_y           # ground_y 为底部锚点
        # 展示缩放：精灵表每格固定 64px，棋盘格是 76px，渲染层按需放大以填满格子。
        # 默认 1.0 保持既有 demo 行为不变；程序化弹性（sx/sy）叠加在它之上。
        self.scale = scale
        self.state, self.facing = "idle", 1
        self.time, self.frame_idx = 0, 0
        self.sx = self.sy = 1.0
        self.flash_timer = 0
        self.note = ""

    def reload(self, sheet):
        self.sheet = sheet

    def play(self, state, force=False):
        if state != self.state or force:
            self.state, self.time, self.frame_idx = state, 0, 0

    def attack(self):
        if self.state not in ("attack", "hurt"):
            self.play("attack")

    def hurt(self):
        self.play("hurt", force=True)
        self.flash_timer = 320

    def _target_scale(self):
        if self.state == "idle":
            b = 0.045 * math.sin(self.time / 240.0)
            return 1.0 - b, 1.0 + b
        if self.state == "walk":
            b = 0.07 * math.sin(self.time / 70.0)
            return 1.0 - b, 1.0 + b
        if self.state == "attack":
            return [(1.22, 0.78), (0.86, 1.18), (1.04, 0.96)][min(self.frame_idx, 2)]
        if self.state == "hurt":
            return [(1.1, 0.9), (0.95, 1.05)][min(self.frame_idx, 1)]
        return 1.0, 1.0

    def update(self, dt, moving=False):
        self.time += dt
        if self.flash_timer > 0:
            self.flash_timer -= dt
        _, cols, interval, loop = ANIM_DEF[self.state]
        self.time  # noqa
        # 帧推进
        self.frame_idx = int(self.time / interval)
        if not loop:
            if self.frame_idx >= cols:
                self.play("idle")
        else:
            self.frame_idx %= cols
        # 移动时切 walk，停止回 idle（attack/hurt 为优先动作，不被打断）
        if self.state in ("idle", "walk"):
            self.play("walk" if moving else "idle")
        # 弹性系数指数回弹到目标
        tx, ty = self._target_scale()
        k = 1 - math.exp(-dt / 55.0)
        self.sx += (tx - self.sx) * k
        self.sy += (ty - self.sy) * k

    def draw(self, surf):
        frames = self.sheet.flash if self.flash_timer > 0 else self.sheet.frames
        frame = frames[self.state][self.frame_idx]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        w = max(1, int(FRAME * self.sx * self.scale))
        h = max(1, int(FRAME * self.sy * self.scale))
        scaled = pygame.transform.smoothscale(frame, (w, h))
        # 椭圆软阴影，随横向缩放变化
        sh = pygame.Surface((w, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 70), sh.get_rect())
        surf.blit(sh, (self.x - w // 2, self.ground_y - 8))
        # 以底部中心为锚点 blit，缩放时不会悬空
        surf.blit(scaled, (self.x - w // 2, self.ground_y - h))
