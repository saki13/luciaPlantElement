# -*- coding: utf-8 -*-
"""
原创塔防游戏原型 —— pygame 精美渲染版（依赖随项目自带在 ./libs，无需额外安装/任何外部素材）
玩法与三大核心机制同 tkinter 版完全一致（波次点数预算 / 弹道数据表 / 单一资源经济），
本文件只重做表现层：渐变草坪、阴影高光、发光弹道与能量块、命中粒子、半透明 UI。

运行：D:\\ProgramData\\anaconda3\\python.exe tower_defense_pygame.py
操作：鼠标点顶部按钮选防御塔 -> 点格子放置；点金色能量块收集；空格暂停，R 重开。
"""
import os
import sys
import math
import random

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "libs"))
import pygame

# ---------------- 基础配置 ----------------
ROWS, COLS = 5, 9
CELL = 76
TOP_H = 96
BOARD_W, BOARD_H = COLS * CELL, ROWS * CELL
WIN_W, WIN_H = BOARD_W, BOARD_H + TOP_H
FRAME_MS = 1000 // 60

TOWER_TYPES = {
    "shooter": {"name": "速射塔", "cost": 50,  "cooldown": 900,  "range": BOARD_W, "proj": "pea"},
    "cannon":  {"name": "重炮塔", "cost": 100, "cooldown": 2200, "range": BOARD_W, "proj": "shell"},
    "frost":   {"name": "冰霜塔", "cost": 75,  "cooldown": 1300, "range": BOARD_W, "proj": "frost"},
}
PROJECTILE_TYPES = {
    "pea":   {"speed": 320, "damage": 25, "slow": 0,   "color": (159, 209, 106), "glow": (214, 240, 180), "r": 7},
    "shell": {"speed": 240, "damage": 70, "slow": 0,   "color": (224, 164, 88), "glow": (245, 214, 168), "r": 9},
    "frost": {"speed": 300, "damage": 15, "slow": 0.5, "color": (143, 214, 225), "glow": (214, 244, 250), "r": 7},
}
ENEMY_TYPES = {
    "normal": {"hp": 100, "speed": 34, "cost": 1, "reward": 25, "color": (155, 89, 182),  "dark": (106, 58, 127),  "r": 17},
    "fast":   {"hp": 60,  "speed": 60, "cost": 1, "reward": 25, "color": (224, 90, 78),   "dark": (165, 56, 48),   "r": 14},
    "tank":   {"hp": 280, "speed": 24, "cost": 3, "reward": 60, "color": (127, 140, 141), "dark": (80, 90, 92),    "r": 21},
}
TOWER_ART = {
    "shooter": ((79, 134, 198), (53, 97, 143), (169, 200, 236)),
    "cannon":  ((224, 138, 46), (181, 103, 29), (243, 192, 138)),
    "frost":   ((63, 179, 172), (44, 131, 127), (167, 227, 222)),
}
TOTAL_WAVES, START_RESOURCE, START_LIVES = 8, 150, 5
SUN_INTERVAL, SUN_VALUE, SPAWN_GAP, WAVE_GAP = 8000, 25, 1100, 6000


# ---------------- 绘制辅助 ----------------
def vgradient(surf, rect, top, bottom):
    h = rect.height
    for i in range(h):
        t = i / max(1, h - 1)
        col = [int(top[c] + (bottom[c] - top[c]) * t) for c in range(3)]
        pygame.draw.line(surf, col, (rect.x, rect.y + i), (rect.right - 1, rect.y + i))


def rrect(surf, rect, color, radius=10, width=0):
    pygame.draw.rect(surf, color, rect, width=width, border_radius=radius)


def soft_shadow(surf, cx, cy, rx, ry, alpha=70):
    sh = pygame.Surface((rx * 2, ry * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, alpha), sh.get_rect())
    surf.blit(sh, (cx - rx, cy - ry))


_FONT_CACHE = {}


def make_font(size, bold=False):
    """直接按文件加载中文字体，绕开 pygame 2.6 SysFont 在部分 Windows 上的枚举 bug。"""
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = ([r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"] if bold
                  else [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                        r"C:\Windows\Fonts\simsun.ttc"])
    font = None
    for path in candidates:
        if os.path.exists(path):
            try:
                font = pygame.font.Font(path, size)
                break
            except Exception:
                continue
    if font is None:
        font = pygame.font.Font(None, size)
    _FONT_CACHE[key] = font
    return font


def glow_circle(surf, cx, cy, r, core, glow, layers=5):
    for i in range(layers, 0, -1):
        rr = int(r * (1 + 0.55 * i / layers))
        a = int(28 * (layers - i + 1) / layers) + 12
        s = pygame.Surface((rr * 2, rr * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*glow, a), (rr, rr), rr)
        surf.blit(s, (cx - rr, cy - rr), special_flags=pygame.BLEND_PREMULTIPLIED)
    pygame.draw.circle(surf, glow, (cx, cy), r + 2)
    pygame.draw.circle(surf, core, (cx, cy), r)
    hl = pygame.Surface((r, r), pygame.SRCALPHA)
    pygame.draw.circle(hl, (255, 255, 255, 90), (r // 2, r // 2), max(2, r // 2))
    surf.blit(hl, (cx - r // 2, cy - r // 2))


class Particle:
    def __init__(self, x, y, color):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(40, 170)
        self.vx, self.vy = math.cos(ang) * spd, math.sin(ang) * spd - 40
        self.x, self.y = x, y
        self.life = random.uniform(280, 520)
        self.max_life = self.life
        self.color = color
        self.r = random.uniform(2.5, 5)

    def update(self, dt):
        self.x += self.vx * dt / 1000
        self.y += self.vy * dt / 1000
        self.vy += 260 * dt / 1000
        self.life -= dt

    def draw(self, surf):
        k = max(0, self.life / self.max_life)
        r = max(1, int(self.r * k))
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, int(220 * k)), (r, r), r)
        surf.blit(s, (self.x - r, self.y - r))


# ---------------- 游戏对象 ----------------
class Tower:
    def __init__(self, row, col, kind):
        self.row, self.col, self.kind = row, col, kind
        self.cx = col * CELL + CELL // 2
        self.cy = row * CELL + CELL // 2 + TOP_H
        self.timer = 0
        self.recoil = 0.0

    def update(self, dt, game):
        self.timer -= dt
        self.recoil = max(0.0, self.recoil - dt / 180.0)
        if self.timer <= 0:
            targets = [e for e in game.enemies if e.row == self.row and not e.dead and e.x >= self.cx]
            if targets:
                tgt = min(targets, key=lambda e: e.x)
                if tgt.x - self.cx <= TOWER_TYPES[self.kind]["range"]:
                    game.spawn_projectile(self)
                    self.timer = TOWER_TYPES[self.kind]["cooldown"]
                    self.recoil = 1.0

    def draw(self, surf):
        base, dark, light = TOWER_ART[self.kind]
        soft_shadow(surf, self.cx, self.cy + 22, 26, 11)
        # 底座
        rrect(surf, pygame.Rect(self.cx - 25, self.cy - 25, 50, 50), dark, 12)
        rrect(surf, pygame.Rect(self.cx - 22, self.cy - 28, 44, 44), (48, 58, 68), 11)
        # 炮管（带后坐位移）
        rec = int(self.recoil * 4)
        barrel_color = dark if self.kind != "frost" else (210, 240, 242)
        if self.kind == "cannon":
            rrect(surf, pygame.Rect(self.cx + 6 - rec, self.cy - 8, 26, 16), barrel_color, 6)
            pygame.draw.circle(surf, (30, 36, 42), (self.cx + 30 - rec, self.cy), 7)
        elif self.kind == "frost":
            rrect(surf, pygame.Rect(self.cx + 4 - rec, self.cy - 5, 24, 10), barrel_color, 4)
        else:
            rrect(surf, pygame.Rect(self.cx + 8 - rec, self.cy - 5, 24, 10), barrel_color, 4)
        # 主体
        pygame.draw.circle(surf, dark, (self.cx, self.cy), 20)
        pygame.draw.circle(surf, base, (self.cx, self.cy), 17)
        pygame.draw.circle(surf, light, (self.cx - 5, self.cy - 6), 7)
        if self.kind == "frost":  # 冰晶标记
            pts = [(self.cx, self.cy - 11), (self.cx + 4, self.cy), (self.cx, self.cy + 11),
                   (self.cx - 4, self.cy)]
            pygame.draw.polygon(surf, (235, 252, 253), pts)
        # 冷却环
        if self.timer > 0:
            pct = self.timer / TOWER_TYPES[self.kind]["cooldown"]
            arc = pygame.Surface((44, 44), pygame.SRCALPHA)
            pygame.draw.arc(arc, (255, 255, 255, 110), arc.get_rect(),
                            -math.pi / 2, -math.pi / 2 + math.tau * pct, 3)
            surf.blit(arc, (self.cx - 22, self.cy - 22))


class Enemy:
    def __init__(self, row, kind):
        self.row, self.kind = row, kind
        d = ENEMY_TYPES[kind]
        self.max_hp = self.hp = d["hp"]
        self.base_speed, self.r = d["speed"], d["r"]
        self.x = BOARD_W + d["r"]
        self.y = row * CELL + CELL // 2 + TOP_H
        self.dead = False
        self.slow_timer, self.slow_factor, self.rewarded = 0, 1.0, False
        self.bob = random.uniform(0, math.tau)

    def update(self, dt, game):
        self.bob += dt / 120.0
        if self.slow_timer > 0:
            self.slow_timer -= dt
            speed = self.base_speed * self.slow_factor
        else:
            self.slow_factor, speed = 1.0, self.base_speed
        self.x -= speed * dt / 1000.0
        if self.x < 10:
            self.dead = True
            game.lose_life()

    def take_damage(self, damage, slow, game):
        self.hp -= damage
        game.burst(self.x, self.y, ENEMY_TYPES[self.kind]["color"], 4)
        if slow:
            self.slow_factor, self.slow_timer = slow, 2500
        if self.hp <= 0:
            self.dead = True
            game.burst(self.x, self.y, ENEMY_TYPES[self.kind]["color"], 14)

    def draw(self, surf):
        d = ENEMY_TYPES[self.kind]
        bob_y = int(math.sin(self.bob) * 2)
        cy = self.y + bob_y
        soft_shadow(surf, self.x, self.y + self.r - 2, self.r, self.r // 2 + 2, 60)
        if self.slow_factor < 1:  # 冰冻光环
            ice = pygame.Surface((self.r * 2 + 10, self.r * 2 + 10), pygame.SRCALPHA)
            pygame.draw.circle(ice, (143, 214, 225, 90), (self.r + 5, self.r + 5), self.r + 5)
            surf.blit(ice, (self.x - self.r - 5, cy - self.r - 5))
        if self.kind == "tank":  # 护甲外环
            pygame.draw.circle(surf, d["dark"], (self.x, cy), self.r + 3)
        pygame.draw.circle(surf, d["dark"], (self.x, cy), self.r)
        pygame.draw.circle(surf, d["color"], (self.x, cy - 1), self.r - 2)
        pygame.draw.circle(surf, tuple(min(255, c + 45) for c in d["color"]),
                           (self.x - 5, cy - 6), self.r // 3)
        # 眼睛
        for dx in (-6, 6):
            pygame.draw.circle(surf, (255, 255, 255), (self.x + dx, cy - 2), 4)
            pygame.draw.circle(surf, (30, 30, 30), (self.x + dx + 1, cy - 2), 2)
        if self.kind == "fast":  # 尖刺
            pygame.draw.polygon(surf, d["dark"], [(self.x - self.r, cy - self.r + 2),
                                                  (self.x - self.r - 7, cy - self.r - 4),
                                                  (self.x - self.r + 4, cy - self.r + 6)])
        # 血条
        w = self.r * 2
        ratio = max(0, self.hp / self.max_hp)
        rrect(surf, pygame.Rect(self.x - self.r, cy - self.r - 11, w, 6), (30, 34, 38), 3)
        rrect(surf, pygame.Rect(self.x - self.r + 1, cy - self.r - 10, int((w - 2) * ratio), 4),
              (80, 220, 120), 2)


class Projectile:
    def __init__(self, tower):
        p = PROJECTILE_TYPES[TOWER_TYPES[tower.kind]["proj"]]
        self.x, self.y = tower.cx + 16, tower.cy
        self.row = tower.row
        self.kind = TOWER_TYPES[tower.kind]["proj"]
        self.speed, self.damage, self.slow = p["speed"], p["damage"], p["slow"]
        self.color, self.glow, self.r = p["color"], p["glow"], p["r"]
        self.dead = False

    def update(self, dt, game):
        self.x += self.speed * dt / 1000.0
        if self.x > BOARD_W + 20:
            self.dead = True
            return
        for e in game.enemies:
            if e.dead or e.row != self.row:
                continue
            if abs(e.x - self.x) < ENEMY_TYPES[e.kind]["r"] + self.r:
                e.take_damage(self.damage, self.slow, game)
                self.dead = True
                break

    def draw(self, surf):
        glow_circle(surf, int(self.x), int(self.y), self.r, self.color, self.glow)


class FallingResource:
    def __init__(self):
        self.col, self.row = random.randrange(COLS), random.randrange(ROWS)
        self.target_x = self.col * CELL + CELL // 2
        self.target_y = self.row * CELL + CELL // 2 + TOP_H
        self.x, self.y = self.target_x, TOP_H - 12
        self.life, self.dead, self.t = 9000, False, 0

    def update(self, dt):
        self.t += dt
        if self.y < self.target_y:
            self.y = min(self.target_y, self.y + 130 * dt / 1000.0)
        else:
            self.life -= dt
            if self.life <= 0:
                self.dead = True

    def hit(self, mx, my):
        return abs(mx - self.x) < 22 and abs(my - self.y) < 22

    def draw(self, surf, now):
        pulse = 1 + 0.08 * math.sin(now / 260.0 + self.col)
        r = int(17 * pulse)
        halo = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        pygame.draw.circle(halo, (255, 211, 77, 55), (r * 2, r * 2), r * 2)
        surf.blit(halo, (self.x - r * 2, self.y - r * 2))
        pygame.draw.circle(surf, (243, 156, 18), (self.x, self.y), r + 2)
        pygame.draw.circle(surf, (255, 211, 77), (self.x, self.y), r)
        pygame.draw.circle(surf, (255, 236, 160), (self.x - 5, self.y - 6), 6)


# ---------------- 主控制器 ----------------
class Game:
    def __init__(self, headless=False):
        pygame.init()
        pygame.display.set_caption("原创塔防原型 - pygame 版")
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.font = make_font(20)
        self.font_b = make_font(22, bold=True)
        self.font_s = make_font(15)
        self.font_big = make_font(38, bold=True)
        self.headless = headless
        self.reset()

    def reset(self):
        self.res, self.lives = START_RESOURCE, START_LIVES
        self.selected, self.over, self.win, self.paused = None, False, False, False
        self.towers, self.enemies, self.projectiles, self.particles, self.suns = [], [], [], [], []
        self.plan_waves()
        self.wave_index, self.state, self.state_timer = -1, "gap", 3000
        self.spawn_queue, self.spawn_timer, self.sun_timer = [], 0, SUN_INTERVAL
        self.now = 0

    def plan_waves(self):
        self.waves = []
        for w in range(TOTAL_WAVES):
            budget, queue, kinds = 8 + w * 4, [], list(ENEMY_TYPES.keys())
            while budget > 0:
                afford = [k for k in kinds if ENEMY_TYPES[k]["cost"] <= budget]
                if not afford:
                    break
                weights = [1 + (3 if k == "tank" and w >= 3 else 0) for k in afford]
                pick = random.choices(afford, weights=weights, k=1)[0]
                queue.append(pick)
                budget -= ENEMY_TYPES[pick]["cost"]
            self.waves.append(queue)

    def burst(self, x, y, color, n):
        for _ in range(n):
            self.particles.append(Particle(x, y, color))

    def spawn_projectile(self, tower):
        self.projectiles.append(Projectile(tower))

    def lose_life(self):
        self.lives -= 1
        if self.lives <= 0:
            self.end_game(False)

    def end_game(self, win):
        self.over, self.win = True, win

    def button_rects(self):
        # 第二行：三个按钮左对齐，固定高度，点击命中与绘制共用同一来源
        rects, x = [], 20
        for kind in TOWER_TYPES:
            rects.append((kind, pygame.Rect(x, 50, 132, 38)))
            x += 142
        return rects

    def handle_click(self, pos):
        if self.over:
            return
        mx, my = pos
        for kind, r in self.button_rects():
            if r.collidepoint(mx, my):
                if self.res >= TOWER_TYPES[kind]["cost"]:
                    self.selected = None if self.selected == kind else kind
                return
        for s in self.suns:
            if not s.dead and s.hit(mx, my):
                self.res += SUN_VALUE
                s.dead = True
                self.burst(s.x, s.y, (255, 211, 77), 10)
                return
        if self.selected is None or my < TOP_H:
            return
        col, row = mx // CELL, (my - TOP_H) // CELL
        if 0 <= col < COLS and 0 <= row < ROWS:
            if any(t.row == row and t.col == col for t in self.towers):
                return
            cost = TOWER_TYPES[self.selected]["cost"]
            if self.res >= cost:
                self.res -= cost
                self.towers.append(Tower(row, col, self.selected))
                self.selected = None

    def update_waves(self, dt):
        self.state_timer -= dt
        if self.state == "gap":
            if self.state_timer <= 0:
                self.wave_index += 1
                self.spawn_queue = list(self.waves[self.wave_index])
                self.state, self.spawn_timer = "spawn", 0
        elif self.state == "spawn":
            self.spawn_timer -= dt
            if self.spawn_timer <= 0 and self.spawn_queue:
                self.enemies.append(Enemy(random.randrange(ROWS), self.spawn_queue.pop(0)))
                self.spawn_timer = SPAWN_GAP
            if not self.spawn_queue:
                self.state = "clear"
        elif self.state == "clear" and not self.enemies:
            if self.wave_index >= TOTAL_WAVES - 1:
                self.end_game(True)
            else:
                self.state, self.state_timer = "gap", WAVE_GAP

    def update(self, dt):
        if self.over or self.paused:
            return
        self.now += dt
        self.sun_timer -= dt
        if self.sun_timer <= 0:
            self.suns.append(FallingResource())
            self.sun_timer = SUN_INTERVAL
        self.update_waves(dt)
        for t in self.towers:
            t.update(dt, self)
        for e in self.enemies:
            e.update(dt, self)
        for p in self.projectiles:
            p.update(dt, self)
        for s in self.suns:
            s.update(dt)
        for pt in self.particles:
            pt.update(dt)
        for e in self.enemies:
            if e.dead and e.hp <= 0 and not e.rewarded:
                self.res += ENEMY_TYPES[e.kind]["reward"]
                e.rewarded = True
        self.enemies = [e for e in self.enemies if not e.dead]
        self.projectiles = [p for p in self.projectiles if not p.dead]
        self.suns = [s for s in self.suns if not s.dead]
        self.particles = [p for p in self.particles if p.life > 0]

    # ---------- 渲染 ----------
    def draw_board(self):
        for r in range(ROWS):
            for c in range(COLS):
                rect = pygame.Rect(c * CELL, TOP_H + r * CELL, CELL, CELL)
                if (r + c) % 2 == 0:
                    vgradient(self.screen, rect, (143, 196, 84), (124, 179, 70))
                else:
                    vgradient(self.screen, rect, (132, 184, 74), (115, 168, 62))
        danger = pygame.Surface((8, BOARD_H), pygame.SRCALPHA)
        danger.fill((220, 60, 50, 150))
        self.screen.blit(danger, (0, TOP_H))

    def draw_ui(self):
        ui = pygame.Surface((WIN_W, TOP_H), pygame.SRCALPHA)
        vgradient(ui, ui.get_rect(), (34, 44, 56), (26, 34, 44))
        self.screen.blit(ui, (0, 0))
        # ---- 第一行：资源（左） + 生命心形 ----
        glow_circle(self.screen, 26, 27, 11, (255, 211, 77), (255, 236, 160), 3)
        self.screen.blit(self.font_b.render(str(self.res), True, (255, 236, 160)), (44, 14))
        hx = 158
        for i in range(START_LIVES):
            col = (231, 76, 60) if i < self.lives else (70, 78, 86)
            cx = hx + i * 18
            pygame.draw.circle(self.screen, col, (cx, 27), 6)
            pygame.draw.circle(self.screen, col, (cx + 7, 27), 6)
            pygame.draw.polygon(self.screen, col, [(cx - 6, 30), (cx + 13, 30), (cx + 3, 41)])
        # ---- 第二行：塔按钮（左） + 波次（右） ----
        mouse = pygame.mouse.get_pos()
        for kind, rct in self.button_rects():
            cfg = TOWER_TYPES[kind]
            affordable = self.res >= cfg["cost"]
            base, dark, _ = TOWER_ART[kind]
            hover = rct.collidepoint(*mouse)
            if self.selected == kind:
                rrect(self.screen, rct, (244, 196, 48), 9)
                rrect(self.screen, rct.inflate(-6, -6), (52, 66, 80), 8)
            elif not affordable:
                rrect(self.screen, rct, (58, 64, 72), 9)
            else:
                rrect(self.screen, rct, (60, 74, 90) if hover else (48, 58, 70), 9)
            pygame.draw.circle(self.screen, dark if affordable else (90, 96, 104),
                               (rct.x + 18, rct.centery), 11)
            pygame.draw.circle(self.screen, base if affordable else (110, 116, 124),
                               (rct.x + 18, rct.centery), 9)
            tcol = (235, 240, 246) if affordable else (130, 136, 144)
            self.screen.blit(self.font_s.render("%s %d" % (cfg["name"], cfg["cost"]), True, tcol),
                             (rct.x + 34, rct.y + 11))
        wave_txt = self.font.render("波次 %d/%d" % (max(0, self.wave_index + 1), TOTAL_WAVES),
                                    True, (220, 228, 236))
        self.screen.blit(wave_txt, (458, 58))

    def draw_placement_preview(self):
        if self.selected is None or self.over:
            return
        mx, my = pygame.mouse.get_pos()
        if my <= TOP_H:
            return
        col, row = mx // CELL, (my - TOP_H) // CELL
        if 0 <= col < COLS and 0 <= row < ROWS:
            occupied = any(t.row == row and t.col == col for t in self.towers)
            ok = not occupied and self.res >= TOWER_TYPES[self.selected]["cost"]
            ov = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
            ov.fill((90, 220, 120, 70) if ok else (220, 80, 70, 70))
            self.screen.blit(ov, (col * CELL, TOP_H + row * CELL))

    def draw_end_panel(self):
        mask = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        mask.fill((18, 24, 32, 170))
        self.screen.blit(mask, (0, 0))
        panel = pygame.Rect(WIN_W * 0.16, WIN_H * 0.34, WIN_W * 0.68, WIN_H * 0.3)
        rrect(self.screen, panel, (38, 50, 64), 16)
        pygame.draw.rect(self.screen, (244, 196, 48), panel, 3, border_radius=16)
        msg = "胜利！守住了全部 %d 波" % TOTAL_WAVES if self.win else "基地失守，游戏结束"
        t1 = self.font_big.render(msg, True, (255, 255, 255))
        t2 = self.font.render("按 R 重新开始，关闭窗口退出", True, (244, 196, 48))
        self.screen.blit(t1, t1.get_rect(center=(WIN_W // 2, panel.centery - 18)))
        self.screen.blit(t2, t2.get_rect(center=(WIN_W // 2, panel.centery + 34)))

    def draw(self):
        self.draw_board()
        for s in self.suns:
            s.draw(self.screen, self.now)
        for t in self.towers:
            t.draw(self.screen)
        for e in sorted(self.enemies, key=lambda x: x.y):
            e.draw(self.screen)
        for p in self.projectiles:
            p.draw(self.screen)
        for pt in self.particles:
            pt.draw(self.screen)
        self.draw_placement_preview()
        self.draw_ui()
        if self.paused and not self.over:
            mask = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            mask.fill((18, 24, 32, 120))
            self.screen.blit(mask, (0, 0))
            tp = self.font_big.render("已暂停（空格继续）", True, (255, 255, 255))
            self.screen.blit(tp, tp.get_rect(center=(WIN_W // 2, WIN_H // 2)))
        if self.over:
            self.draw_end_panel()
        pygame.display.flip()

    def run(self):
        while True:
            dt = self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE and not self.over:
                        self.paused = not self.paused
                    if event.key == pygame.K_r:
                        self.reset()
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    random.seed()
    Game().run()
