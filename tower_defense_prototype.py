# -*- coding: utf-8 -*-
"""
原创塔防游戏原型（Python 标准库 tkinter，无需任何外部素材/第三方包）
对应从 PlantsVsZombies.exe 逆向得到的三大核心机制：
  1) 波次系统：预计算每波敌人类型队列（点数预算随波次递增），运行时按毫秒逐个放出
  2) 攻击系统：防御塔 -> 产生弹道 -> 弹道移动/矩形碰撞 -> 查伤害表结算（含减速）
  3) 经济系统：单一全局资源计数器 + 可点击天降资源，建造走“余额 >= 成本”门控

运行：python tower_defense_prototype.py
操作：点击顶部选择防御塔 -> 点击格子放置；点击下落的能量块收集资源
"""
import random
import tkinter as tk

# ---------------- 全局配置（数据驱动，调平衡改这里） ----------------
ROWS, COLS = 5, 9
CELL = 72
BOARD_W, BOARD_H = COLS * CELL, ROWS * CELL
TOP_H = 86
FRAME_MS = 30          # 帧间隔（约 33 FPS），时间单位统一为毫秒

# 防御塔定义：成本/冷却(ms)/射程(像素)/弹道类型
TOWER_TYPES = {
    "shooter": {"name": "速射塔", "cost": 50,  "cooldown": 900,  "range": BOARD_W,
                "proj": "pea",   "color": "#4f86c6"},
    "cannon":  {"name": "重炮塔", "cost": 100, "cooldown": 2200, "range": BOARD_W,
                "proj": "shell", "color": "#d98324"},
    "frost":   {"name": "冰霜塔", "cost": 75,  "cooldown": 1300, "range": BOARD_W,
                "proj": "frost", "color": "#3aa6a0"},
}

# 弹道定义：速度(像素/秒)、伤害、特殊效果
PROJECTILE_TYPES = {
    "pea":   {"speed": 320, "damage": 25, "slow": 0,    "color": "#9fd16a", "r": 6},
    "shell": {"speed": 240, "damage": 70, "slow": 0,    "color": "#e0a458", "r": 8},
    "frost": {"speed": 300, "damage": 15, "slow": 0.5,  "color": "#8fd6e1", "r": 6},
}

# 敌人定义：血量、速度(像素/秒)、点数成本、击杀奖励、颜色、体型
ENEMY_TYPES = {
    "normal": {"hp": 100, "speed": 34, "cost": 1, "reward": 25, "color": "#9b59b6", "r": 16},
    "fast":   {"hp": 60,  "speed": 60, "cost": 1, "reward": 25, "color": "#e05a4e", "r": 13},
    "tank":   {"hp": 280, "speed": 24, "cost": 3, "reward": 60, "color": "#7f8c8d", "r": 19},
}

TOTAL_WAVES = 8
START_RESOURCE = 150
START_LIVES = 5
SUN_INTERVAL = 8000     # 天降资源间隔（ms）
SUN_VALUE = 25
SPAWN_GAP = 1100        # 同波敌人放出间隔（ms）
WAVE_GAP = 6000         # 波次间隔（ms）


# ---------------- 游戏对象 ----------------
class Tower:
    def __init__(self, row, col, kind):
        self.row, self.col, self.kind = row, col, kind
        cfg = TOWER_TYPES[kind]
        self.cx = col * CELL + CELL // 2
        self.cy = row * CELL + CELL // 2 + TOP_H
        self.cooldown = cfg["cooldown"]
        self.timer = 0

    def update(self, dt, game):
        self.timer -= dt
        if self.timer <= 0:
            # 找同一行、在射程内、最靠前（x 最小）的存活敌人
            targets = [e for e in game.enemies
                       if e.row == self.row and not e.dead and e.x >= self.cx]
            if targets:
                target = min(targets, key=lambda e: e.x)
                if target.x - self.cx <= TOWER_TYPES[self.kind]["range"]:
                    game.spawn_projectile(self)
                    self.timer = self.cooldown


class Enemy:
    def __init__(self, row, kind):
        self.row, self.kind = row, kind
        d = ENEMY_TYPES[kind]
        self.max_hp, self.hp = d["hp"], d["hp"]
        self.base_speed = d["speed"]
        self.x = BOARD_W + d["r"]          # 从右侧屏外进入
        self.y = row * CELL + CELL // 2 + TOP_H
        self.dead = False
        self.slow_timer = 0
        self.slow_factor = 1.0

    def update(self, dt, game):
        if self.slow_timer > 0:
            self.slow_timer -= dt
            speed = self.base_speed * self.slow_factor
        else:
            self.slow_factor = 1.0
            speed = self.base_speed
        self.x -= speed * dt / 1000.0
        if self.x < 8:                      # 到达左侧终点
            self.dead = True
            game.lose_life()

    def take_damage(self, damage, slow):
        self.hp -= damage
        if slow:
            self.slow_factor = slow
            self.slow_timer = 2500
        if self.hp <= 0:
            self.dead = True


class Projectile:
    def __init__(self, tower):
        p = PROJECTILE_TYPES[TOWER_TYPES[tower.kind]["proj"]]
        self.x, self.y = tower.cx + 14, tower.cy
        self.row = tower.row
        self.kind = TOWER_TYPES[tower.kind]["proj"]
        self.speed, self.damage, self.slow = p["speed"], p["damage"], p["slow"]
        self.color, self.r = p["color"], p["r"]
        self.dead = False

    def update(self, dt, game):
        self.x += self.speed * dt / 1000.0
        if self.x > BOARD_W + 20:
            self.dead = True
            return
        for e in game.enemies:
            if e.dead or e.row != self.row:
                continue
            if abs(e.x - self.x) < e_radius(e) + self.r:   # 矩形/圆形碰撞
                e.take_damage(self.damage, self.slow)
                self.dead = True
                break


def e_radius(enemy):
    return ENEMY_TYPES[enemy.kind]["r"]


class FallingResource:
    def __init__(self):
        self.col = random.randrange(COLS)
        self.row = random.randrange(ROWS)
        self.target_x = self.col * CELL + CELL // 2
        self.target_y = self.row * CELL + CELL // 2 + TOP_H
        self.x, self.y = self.target_x, TOP_H - 10
        self.life = 9000                   # 存在时间（ms）
        self.dead = False

    def update(self, dt):
        if self.y < self.target_y:
            self.y = min(self.target_y, self.y + 120 * dt / 1000.0)
        else:
            self.life -= dt
            if self.life <= 0:
                self.dead = True

    def hit(self, mx, my):
        return abs(mx - self.x) < 20 and abs(my - self.y) < 20


# ---------------- 主控制器 ----------------
class Game:
    def __init__(self, root):
        self.root = root
        root.title("原创塔防原型")
        self.res = START_RESOURCE
        self.lives = START_LIVES
        self.selected = None
        self.over = False

        # 顶部 UI
        self.top = tk.Frame(root, height=TOP_H, bg="#2c3e50")
        self.top.pack(fill="x")
        self.lbl = tk.Label(self.top, fg="white", bg="#2c3e50", font=("微软雅黑", 11))
        self.lbl.pack(anchor="w", padx=10, pady=(8, 4))
        self.buttons = {}
        bar = tk.Frame(self.top, bg="#2c3e50")
        bar.pack(anchor="w", padx=8)
        for kind, cfg in TOWER_TYPES.items():
            b = tk.Button(bar, text="%s (%d)" % (cfg["name"], cfg["cost"]),
                          width=12, command=lambda k=kind: self.select(k))
            b.pack(side="left", padx=4)
            self.buttons[kind] = b
        self.hint = tk.Label(self.top, text="选择防御塔后点击格子放置",
                             fg="#f1c40f", bg="#2c3e50", font=("微软雅黑", 9))
        self.hint.pack(anchor="w", padx=10, pady=4)

        # 画布
        self.canvas = tk.Canvas(root, width=BOARD_W, height=BOARD_H,
                                bg="#7cb342", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)

        # 游戏状态
        self.towers, self.enemies, self.projectiles, self.suns = [], [], [], []
        self.plan_waves()                  # 预计算整关波次（数据驱动）
        self.wave_index = -1
        self.state = "gap"                # gap(波间) -> spawn -> clear
        self.state_timer = 3000
        self.spawn_queue = []
        self.spawn_timer = 0
        self.sun_timer = SUN_INTERVAL
        self.refresh_buttons()
        self.tick()

    # ---- 波次预计算：复刻 PVZ“点数预算 + 随波次递增”思想 ----
    def plan_waves(self):
        self.waves = []
        for w in range(TOTAL_WAVES):
            budget = 8 + w * 4            # 该波点数预算，随波次递增
            queue = []
            kinds = list(ENEMY_TYPES.keys())
            while budget > 0:
                affordable = [k for k in kinds if ENEMY_TYPES[k]["cost"] <= budget]
                if not affordable:
                    break
                # 后期波次提高重甲出现权重
                weights = [1 + (3 if k == "tank" and w >= 3 else 0) for k in affordable]
                pick = random.choices(affordable, weights=weights, k=1)[0]
                queue.append(pick)
                budget -= ENEMY_TYPES[pick]["cost"]
            self.waves.append(queue)

    def select(self, kind):
        if self.over:
            return
        self.selected = kind if self.selected != kind else None
        self.hint.config(text="已选择 %s，点击空格放置；再次点击按钮取消"
                         % TOWER_TYPES[kind]["name"] if self.selected else "选择防御塔后点击格子放置")

    def on_click(self, event):
        if self.over:
            return
        # 1) 优先判断是否点中掉落资源
        for s in self.suns:
            if not s.dead and s.hit(event.x, event.y):
                self.res += SUN_VALUE
                s.dead = True
                return
        # 2) 否则尝试在格子放塔
        if self.selected is None:
            return
        col, row = event.x // CELL, event.y // CELL
        if not (0 <= col < COLS and 0 <= row < ROWS):
            return
        if any(t.row == row and t.col == col for t in self.towers):
            self.hint.config(text="该格已有防御塔")
            return
        cost = TOWER_TYPES[self.selected]["cost"]
        if self.res < cost:               # 经济门控：余额 >= 成本
            self.hint.config(text="资源不足，需要 %d" % cost)
            return
        self.res -= cost
        self.towers.append(Tower(row, col, self.selected))
        self.selected = None
        self.hint.config(text="建造成功")

    def spawn_projectile(self, tower):
        self.projectiles.append(Projectile(tower))

    def lose_life(self):
        self.lives -= 1
        if self.lives <= 0:
            self.end_game(False)

    # ---- 波次状态机 ----
    def update_waves(self, dt):
        self.state_timer -= dt
        if self.state == "gap":
            if self.state_timer <= 0:
                self.wave_index += 1
                self.spawn_queue = list(self.waves[self.wave_index])
                self.state = "spawn"
                self.spawn_timer = 0
        elif self.state == "spawn":
            self.spawn_timer -= dt
            if self.spawn_timer <= 0 and self.spawn_queue:
                kind = self.spawn_queue.pop(0)
                self.enemies.append(Enemy(random.randrange(ROWS), kind))
                self.spawn_timer = SPAWN_GAP
            if not self.spawn_queue:
                self.state = "clear"
        elif self.state == "clear":
            if not self.enemies:          # 该波敌人全部解决
                if self.wave_index >= TOTAL_WAVES - 1:
                    self.end_game(True)
                else:
                    self.state = "gap"
                    self.state_timer = WAVE_GAP

    def tick(self):
        if self.over:
            return
        dt = FRAME_MS
        # 天降资源
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

        # 结算死亡敌人的奖励
        for e in self.enemies:
            if e.dead and e.hp <= 0 and not getattr(e, "rewarded", False):
                self.res += ENEMY_TYPES[e.kind]["reward"]
                e.rewarded = True
        self.enemies = [e for e in self.enemies if not e.dead]
        self.projectiles = [p for p in self.projectiles if not p.dead]
        self.suns = [s for s in self.suns if not s.dead]

        self.render()
        self.refresh_buttons()
        self.root.after(FRAME_MS, self.tick)

    # ---- 渲染：全部用 Canvas 原语，原创图形，无外部素材 ----
    def render(self):
        c = self.canvas
        c.delete("all")
        # 网格（棋盘格）
        for r in range(ROWS):
            for col in range(COLS):
                if (r + col) % 2 == 0:
                    c.create_rectangle(col * CELL, r * CELL, (col + 1) * CELL, (r + 1) * CELL,
                                       fill="#8bc34a", outline="")
        # 左侧危险线
        c.create_line(4, 0, 4, BOARD_H, fill="#c0392b", width=4)
        # 塔
        for t in self.towers:
            cfg = TOWER_TYPES[t.kind]
            c.create_rectangle(t.cx - 20, t.cy - 20, t.cx + 20, t.cy + 20,
                               fill=cfg["color"], outline="white", width=2)
            c.create_oval(t.cx - 7, t.cy - 7, t.cx + 7, t.cy + 7, fill="white", outline="")
        # 敌人
        for e in self.enemies:
            d = ENEMY_TYPES[e.kind]
            c.create_oval(e.x - d["r"], e.y - d["r"], e.x + d["r"], e.y + d["r"],
                          fill=d["color"], outline="white", width=2)
            if e.slow_factor < 1:
                c.create_oval(e.x - d["r"], e.y - d["r"], e.x + d["r"], e.y + d["r"],
                              outline="#8fd6e1", width=3)
            # 血条
            w = d["r"] * 2
            ratio = max(0, e.hp / e.max_hp)
            c.create_rectangle(e.x - d["r"], e.y - d["r"] - 8, e.x - d["r"] + w,
                               e.y - d["r"] - 4, fill="#444", outline="")
            c.create_rectangle(e.x - d["r"], e.y - d["r"] - 8,
                               e.x - d["r"] + w * ratio, e.y - d["r"] - 4,
                               fill="#2ecc71", outline="")
        # 弹道
        for p in self.projectiles:
            c.create_oval(p.x - p.r, p.y - p.r, p.x + p.r, p.y + p.r,
                          fill=p.color, outline="white")
        # 天降资源
        for s in self.suns:
            c.create_oval(s.x - 16, s.y - 16, s.x + 16, s.y + 16,
                          fill="#f7d154", outline="#f39c12", width=2)
            c.create_text(s.x, s.y, text="%d" % SUN_VALUE, fill="#7d5a00",
                          font=("微软雅黑", 10, "bold"))
        # 结束画面（胜利/失败），由 render 统一绘制，保证不被覆盖
        if self.over:
            msg = "胜利！你守住了全部 %d 波" % TOTAL_WAVES if self.win else "基地失守，游戏结束"
            c.create_rectangle(BOARD_W * 0.2, BOARD_H * 0.35, BOARD_W * 0.8,
                               BOARD_H * 0.65, fill="#2c3e50", outline="#f1c40f", width=3)
            c.create_text(BOARD_W // 2, BOARD_H // 2, text=msg,
                          fill="white", font=("微软雅黑", 16, "bold"))
            c.create_text(BOARD_W // 2, BOARD_H // 2 + 38,
                          text="关闭窗口退出", fill="#f1c40f", font=("微软雅黑", 11))

    def refresh_buttons(self):
        wave_disp = max(0, self.wave_index + 1)
        self.lbl.config(text="资源 %d      波次 %d/%d      基地生命 %d"
                        % (self.res, wave_disp, TOTAL_WAVES, self.lives))
        for kind, b in self.buttons.items():
            b.config(state=("disabled" if self.res < TOWER_TYPES[kind]["cost"] else "normal"),
                     relief=("sunken" if self.selected == kind else "raised"))

    def end_game(self, win):
        # 只设置状态；结束画面统一在 render() 中绘制，避免被同一帧随后的 render() 覆盖
        self.over = True
        self.win = win


if __name__ == "__main__":
    random.seed()
    root = tk.Tk()
    Game(root)
    root.mainloop()
