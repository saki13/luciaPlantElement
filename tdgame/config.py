# -*- coding: utf-8 -*-
"""全局口径常量。

headless 引擎内部统一使用 **秒 / 格 / HP / 阳光** 单位（与 game_balance_design.md v0.2 对齐）；
pygame 渲染层再按 CELL 换算成像素、按 ×1000 换算成毫秒。纯数值模拟不导入 pygame。
"""
from __future__ import annotations

# ---- 棋盘（与 tower_defense_pygame.py 口径一致：5 行 × 9 列，CELL=76）----
ROWS = 5
COLS = 9
CELL = 76
TOP_H = 96
BOARD_W = COLS * CELL            # 684px
# 棋盘左侧留出的"小车通道"宽度（仅渲染层用；headless 用格坐标，与此无关）
BOARD_GUTTER = 34

# ---- 时间步长（headless 固定步长离散模拟）----
DT = 0.1                        # 秒/步，10Hz 决策 + 100ms 精度，足够复现 0.8s/2.5s 等节奏

# ---- 局内经济 / 生命（v0.2 §11）----
START_RESOURCE = 100            # v0.1 由 150 下调到 100
START_LIVES = ROWS              # 每行一辆小车，等价 5 条命
SKY_SUN_INTERVAL = 10.0         # 天降保底每 10s 落 25（headless 自动拾取）
SKY_SUN_VALUE = 25
SUNFLOWER_INTERVAL = 8.0        # 向阳花每 8s 产 25，首产第 4s
SUNFLOWER_FIRST = 4.0
SUN_VALUE = 25
KILL_DROP_SUN = 0               # v0.2 取消常规击杀掉阳光（教学首关可在关卡里覆盖）

# ---- 出怪节奏（沿用旧原型）----
SPAWN_GAP = 1.1                 # 同波出怪间隔（秒）
WAVE_GAP = 6.0                  # 波间间隔（秒）

# ---- 敌人移动 / 啃食口径 ----
DEFAULT_BITE_DPS = 25
ELITE_BITE_DPS = 40             # 巨人
LAWN_MOWER_TRIGGER_X = -0.2     # 敌人前缘越过该格坐标触发小车 / 破线

# ---- 设计代币 / 品阶（v0.2 §6/§7）----
TIER_STEP = 22.5
MAX_TIER = 13
AXIS_LEVELS = 5                 # 单轴 0..5 档
AXIS_BASE_SCORE = [0, 8, 17, 27, 38, 52]          # b(档)，边际 8·9·10·11·14
AXIS_WEIGHTS = {"fire": 1.0, "area": 1.3, "pierce": 0.9, "durability": 0.8, "control": 1.4}
# 个别能力标签的价值远高于通用标签（例如护甲壳：等于省一个格子），
# 单独给它们定「能力分」与「代币价」，而不是硬抬阳光价。
TAG_SCORE_OVERRIDE = {
    # §5.3：纯功能标签（护甲壳、经济、对空…）**不计战斗点**，
    # 价值只体现在代币与局内作用上，不允许抬高 power/品阶。
}
TAG_TOKEN_OVERRIDE = {
    "shell": 240,       # 是 shield_break / armor_pierce(80) 的 3 倍
}
GENERIC_TAG_SCORE = 3           # 每个战斗功能标签的 power 通用分
TOKEN_AXIS_CUM = [0, 40, 80, 120, 180, 260]       # 单轴第 n 档累计代币
TAG_TOKEN_PRICE = {"shield_break": 80, "armor_pierce": 80}
GENERIC_TAG_TOKEN = (60, 120)   # 其他战斗标签代币区间
# 计入 power 通用分的战斗功能标签（economy/wall/upgrade 等非战斗标签不计）
COMBAT_TAGS = {"shield_break", "armor_pierce", "aoe", "control", "fragments", "pierce",
               "one_shot", "hard_cc", "summon", "fullscreen", "manual_ultimate"}
AP_MULT_DEFAULT = 2.0           # armor_pierce 标签对【甲段】的默认穿甲倍率（草案，headless 校准）

# 品阶 -> 局内阳光（v0.2 §8.1，锚定原版高价植物）
SUN_BY_TIER = {
    1: 50, 2: 100, 3: 150, 4: 200, 5: 275, 6: 325, 7: 500,
    8: 565, 9: 635, 10: 700, 11: 770, 12: 835, 13: 900,
}

# recharge 五档（秒，v0.2 §8.2）
RECHARGE_FAST = 5.0
RECHARGE_MID = 7.5
RECHARGE_STEADY = 15.0
RECHARGE_SLOW = 27.5            # 25–30s 取中值
RECHARGE_ULTRA = 50.0
RECHARGE_FLOOR = 5.0            # 自制株硬下限
# 触发强制加长 CD 的强机制标签
LONG_CD_TAGS = {"one_shot", "hard_cc", "summon", "fullscreen", "manual_ultimate"}
ULTRA_CD_TAGS = {"manual_ultimate"}

# ---- headless 回归默认参数 ----
DEFAULT_RUNS = 100
