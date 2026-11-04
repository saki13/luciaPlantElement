# 原创塔防工程交接文档（HANDOVER）

> 交接日期：2026-11-04
> 适用对象：接手本项目的研发同事。读完本文即可：跑起来、看懂架构与数值、复现全部测试、
> 继续用 AI 管线生产/修补美术、并清楚知道当前做到哪一步、下一步做什么。
> 配套两份压缩包（见文末「交接物清单」）：**运行包**（小，开箱即跑）与**美术源材包**（大，含 AI 原始竖图）。

---

## 0. 一分钟了解这个项目

- 这是一个**完全原创**的 2D 横版塔防（玩法骨架借鉴植物防守类游戏的品类范式，但角色、命名、美术、代码全部自研，**不含任何原版游戏素材**）。
- 工程主体 `tdgame/` 是一套**纯 Python 标准库的 headless（无显示）数值引擎**：所有战斗、经济、品阶、出怪逻辑都不依赖 pygame，可批量、确定性地回归平衡；`pygame` 只作为一层薄渲染壳。
- 美术由一条 **魔搭千问（Qwen-Image-2.1）AI 生图 → PIL 自动去背拼表 → pygame 动画框架加载** 的管线生产，已产出 **13 种植物 + 8 种敌人共 21 个单位**的立绘、动作帧与 4×4 精灵表。
- 数值设计的唯一事实来源是根目录 **`game_balance_design.md`（v0.2）**；代码常量与该文档对齐，平衡数字标注为草案、以 headless 回归终校为准。

合规红线：`ghidra-project/`、`unpacked/` 是早期对个人合法持有游戏做逆向学习的产物（Ghidra 工程与解包文件），**不属于原创交付物、也不应分发**；本次交接包已显式排除它们，工程运行也不依赖这两个目录。

---

## 1. 环境与快速上手

### 1.1 解释器与依赖

| 项 | 值 |
|---|---|
| Python | `D:\ProgramData\anaconda3\python.exe`（3.11.7） |
| 第三方依赖 | 仅 `pygame`（2.6.1 / SDL 2.28.4）与 `requests`、`Pillow`（Anaconda 自带） |
| pygame 安装方式 | 系统 Anaconda 目录只读，无法常规 pip，已用 `pip install --target=./libs pygame` 放进项目内 **`libs/`（21.7MB，自包含，随包带走）** |

- **纯 headless / 跑单元测试不需要 pygame**，直接用 Anaconda Python 即可。
- 跑渲染/动画相关脚本前，把 `libs` 与项目根加进 `PYTHONPATH`：

```powershell
$py = "D:\ProgramData\anaconda3\python.exe"
$env:PYTHONPATH = "D:\lucia\rea\project\pvz\libs;D:\lucia\rea\project\pvz"
```

> 换机器时把路径改成解压后的实际根目录即可；代码里也有脚本会自行把同级 `libs` 插入 `sys.path`。

### 1.2 无显示环境（headless）跑 pygame

服务器/自动化场景用 SDL dummy 驱动，不会弹窗：

```powershell
$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"
```

**关键坑**：dummy 模式下调用 `surface.convert_alpha()` 前，必须先 `pygame.display.set_mode(...)` 建立视频模式，否则报 `No video mode has been set`。动画框架的正式 demo 内部会建模式；自己写离屏脚本时记得手动建。

### 1.3 三条命令验证环境（交接时全部实测通过）

```powershell
$py = "D:\ProgramData\anaconda3\python.exe"
# 1) 39 个单元测试（balance 12 + engine 11 + scenarios 16）
& $py -m unittest tests.test_balance tests.test_engine tests.test_scenarios
# 2) headless 100 局回归，结果写 reports/*.json
& $py -m tdgame.headless_run --runs 100
# 3) pygame 薄壳 dummy 冒烟并截图
$env:SDL_VIDEODRIVER="dummy"; $env:SDL_AUDIODRIVER="dummy"
$env:PYTHONPATH="D:\lucia\rea\project\pvz\libs;D:\lucia\rea\project\pvz"
& $py -m tdgame.app_pygame --smoke --frames 3 --shot logs\app_smoke.png
```

> PowerShell 跑 unittest 时，测试进度点走 stderr，会被包装成红色 `NativeCommandError` 字样，**这不是失败**；以输出末尾的 `Ran N tests ... OK` 为准。

---

## 2. 目录地图

```
pvz/
├── HANDOVER.md                     # 本文档
├── README.md                       # 早期逆向→原创原型阶段的交付说明（含 main.pak 格式等历史）
├── game_balance_design.md          # ★数值设计唯一事实来源 v0.2（平衡公式/五轴/品阶/代币/克制总纲）
├── pvz-architecture.html           # 架构可视化页面
├── tower_defense_prototype.py      # 早期 tkinter 极简原型（纯标准库，可运行，玩法与 pygame 版一致）
├── tower_defense_pygame.py         # 早期 pygame 精美原型（代码原创绘制，无外部美术）
│
├── tdgame/                         # ★工程主体：纯标准库 headless 引擎 + 数据 + 场景
│   ├── config.py                   # 全局口径常量（棋盘/经济/品阶/代币/recharge），单位 秒/格/HP/阳光
│   ├── balance.py                  # 纯数值：power/品阶/代币/三维成本 + 确定性伤害管线（不 import pygame）
│   ├── headless_run.py             # 批量回归 CLI（--runs N --scenes ...）→ reports/*.json
│   ├── app_pygame.py               # pygame 薄渲染壳（当前为色块占位，支持 --smoke 离屏冒烟/截图）
│   ├── engine/
│   │   ├── entities.py             # Plant/Enemy/Projectile 运行时实体（只持动态状态，静态数值在 JSON）
│   │   ├── board.py                # Simulation：固定步长推进、出怪、啃食、子弹、小车/破线
│   │   ├── wavegen.py              # 点数预算出怪 / 固定表 / 白名单 / 单波上限
│   │   ├── bot.py                  # RuleBot：经济流、刚性破盾、补墙、后期爆兵（smart/dumb 对照）
│   │   └── loader.py               # JSON → Registry，派生 power/tier/recharge 并做校验
│   ├── scenarios/
│   │   ├── customizer.py           # M2 植物定制器（五轴+标签+代币+阶段准入 → 可注册植物卡）
│   │   ├── zombie_editor.py        # M5 僵尸编辑器（四维点数+能力标签 → 可注册敌人）
│   │   ├── endless.py              # M4 无尽缩放 + counter_map 自动反制选怪 + 可解性闸门
│   │   ├── progression.py          # P1–P4 阶段/代币奖励/解锁流
│   │   └── level_run.py            # 关卡 JSON → 出怪表 → Simulation 的桥
│   └── data/
│       ├── plants/*.json           # 13 张内置植物
│       ├── enemies/*.json          # 8 种内置敌人
│       ├── levels/*.json           # 18 关：M1×10、M2×6、M3×2（scripts/gen_levels.py 生成）
│       └── counter_map.json        # 7 组克制关系 + 6 条反制选择规则 + headless 目标胜率
│
├── anim_demo/                      # ★AI 美术管线 + 动画框架 + Tkinter 植物工坊
│   ├── gen_image_qwen.py           # 千问异步生图客户端（文生图/图像编辑，token 读环境变量）
│   ├── gen_plant.py                # 13 植物配置与逐帧 prompt 驱动（植物无 walk，7 帧）
│   ├── gen_enemy.py                # 8 敌人配置与逐帧 prompt（含真行走，11 帧，攻击三模板）
│   ├── gen_roster.py               # 全花名册批量驱动（base/frames/sheet/all，断点续跑、失败不中断）
│   ├── build_spritesheet.py        # 纯 Pillow 去背 + 全局缩放 + 底部锚点拼 4×4 精灵表
│   ├── animation.py                # 可复用动画框架 SpriteSheet/AnimatedSprite（含占位表回退）
│   ├── gen_frames_qwen.py          # 早期单角色多帧脚本（管线雏形，保留备查）
│   ├── sprite_animation_demo.py    # 精灵动画演示窗口
│   ├── plant_editor.py             # Tkinter 植物工坊完整向导（45.7KB，配置化造角色）
│   ├── verify_plant.py / verify_qwen_sheet.py  # 早期单角色/精灵表校验脚本
│   ├── capture_anim.py             # 动画离屏截帧
│   ├── .ms_token                   # 【机密，不入任何包、不入库】见 §6.2
│   └── assets/
│       ├── plants/<key>/base.png、frames/*.png  # 植物原始 760×1280 竖图与逐帧（源材包）
│       ├── enemies/<key>/base.png、frames/*.png # 敌人原始竖图与逐帧（源材包）
│       ├── sprites/<key>.png                   # 成品植物精灵表 256×256（运行包含此目录）
│       ├── sprites/enemies/<key>.png           # 成品敌人精灵表
│       └── art_build_status.json               # 批量管线各单位阶段状态
│
├── scripts/                        # 工具脚本：list_roster/gen_levels/smoke/capture/unpack 等
├── tests/                          # 39 个单测 + diag/smoke 诊断脚本
├── reports/                        # headless 校准报告 md + 100 局回归 json
├── libs/                           # 自包含 pygame（随包）
├── logs/                           # 过程日志/截图（默认不入运行包）
├── ghidra-project/                 # 逆向工程（132MB，版权敏感，不入包）
└── unpacked/                       # main.pak 解包文件（48MB，版权敏感，不入包）
```

> 美术目录里有少量**历史试验素材**，不在 21 个正式花名册内：植物源目录含一个早期 `blade_tree/`（所以 plants 下是 14 个目录而非 13），`sprites/` 下另有 `blob.png`、`blob_qwen.png`、`blade_tree.png` 三张试验表（故 sprites 共 24 张 png，其中 21 张是正式表）。量产脚本和加载验证都已跳过这些试验品，可保留参考也可随时删除。

---

## 3. 总体架构与分层依赖

严格**单向依赖、不回头**：

```
data(JSON)  →  loader 校验/派生  →  balance 公式  →  engine 模拟  →  上层 headless_run / scenarios / app_pygame
```

- 渲染层（`app_pygame.py` 等）**只读** Registry 与 Simulation 状态，**绝不允许重算任何战斗公式**。这保证 headless 批量回归的结果就是未来真机的结果，且数值可手算复现。
- `balance.py`、`engine/*`、`scenarios/*` 都是纯标准库，不 import pygame，因此可在无显示环境高速批量跑。
- 单位制统一在 `config.py`：内部用 **秒 / 格 / HP / 阳光**；棋盘 5 行 × 9 列、`CELL=76`、固定步长 `DT=0.1s`（10Hz 决策）。渲染层再按 CELL 换像素、按 ×1000 换毫秒。

---

## 4. headless 引擎实现原理

### 4.1 实体与状态分离（engine/entities.py）

- 静态数值（伤害、血量、护甲、阳光价、五轴等）全部存在加载后的 JSON 定义 dict 里；实体对象只持有**动态运行时状态**。
- `Plant`：格坐标、当前 hp、攻击倒计时 `attack_timer`、发射计数、经济产出计时、一次性引信 `fuse_timer`（爆栗果）等。
- `Enemy`：前缘格坐标 `x`（从右向左减小）、本体/护甲血量及上限、`block_flat` 格挡、速度、啃咬 DPS、`weight` 重量、`slow_resist` 减速抗性、`kb_immune` 免推、减速到期时间、当前啃食目标等。
- `Projectile`：弹道静态段 `spec`（speed/hit/on_hit/slow）、伤害、标签、剩余可穿透数 `hit_left`；速度在属性里由 px/s 换算成 格/s。

### 4.2 加载与派生（engine/loader.py）

`load_registry()` 扫描 `data/plants`、`data/enemies`、`counter_map.json`，逐个进 `Registry`：

- `derive_plant()`：用 `balance.power_score` 重算 power、`tier_of` 重算品阶，写 `_power/_tier`；内置卡可显式声明 tier 来锚定价位（不一致会记 `_tier_mismatch` 警告）；缺省 recharge 时按品阶系统派生，并强制 5s 硬下限。
- `validate_plant/validate_enemy()`：必填字段、五轴取值 0..5、免费底盘下限（至少 100HP=坦度1，远程/近战有打击面起步档）、阳光合理区间、护甲减伤 ∈[0,1)、减速抗性 ∈[0,1]。
- 任何越界配装写入 `Registry.errors` 并**拒绝注册**，不会带着坏数据进模拟。
- 还可传 `custom_plant_dirs` 扫描植物工坊产物：只有同时含 `axes` 与 `combat` 的才注册为可参战单位，纯美术目录跳过并告警。

花名册加载是否干净，一条命令即可确认（交接实测 `loader errors: none`）：

```powershell
& $py scripts\list_roster.py
```

### 4.3 确定性伤害管线（balance.resolve_hit）

这是全项目最核心的纯函数，对**单个敌人结算一次伤害实例**，就地改 `hp_body/armor_hp`，并返回每一步的明细 dict。顺序固定：

1. **格挡**：敌人有 `block_flat` 且攻击不带 `shield_break` 标签时，`dmg = max(0, dmg - block_flat)`。格挡是**每实例固定减、可以把伤害完全归零**；带 `shield_break` 则跳过格挡并标记 `shield_broke=True`。
2. **归零短路**：格挡后 `dmg<=0` 直接返回（`blocked_fully=True`），**不破甲、不打本体**——这是「格挡死锁」教学考场成立的根本。
3. **护甲段**：护甲存在时，穿甲倍率 `ap`（`armor_pierce` 标签默认 `AP_MULT_DEFAULT=2.0`，否则 1.0）**只作用于甲段**；甲段能吸收的原始伤害当量 = `armor_hp/ap`。
   - 伤害没打穿甲：按倍率扣甲；
   - 打穿甲：剩余原始溢出伤害 ×`(1 - armor_reduction)` 折减后才进本体（`nominal_hp` 的 EHP 口径因此守恒，路障 280 / 铁桶 650 有锁定测试守底）。
4. **裸本体**：无甲时穿甲倍率不生效，原始伤害直接扣本体。
5. **控制结算**（独立纯函数）：`effective_speed_mult` 按减速抗性折算减速；`knockback_distance = 基础击退 / weight`，`kb_immune` 直接清零。

### 4.4 power / 品阶 / 代币 / 三维成本（balance.py + config.py）

- **五轴**：`fire 火力 / area 打击面 / pierce 穿透 / durability 坦度 / control 控制`，每轴 0..5 档。
- **power 分**：`power_score = Σ b(档) × 轴权重 + 战斗标签通用分`。权重 control 1.4 最高、area 1.3、fire 1.0、pierce 0.9、durability 0.8；基础分表 `AXIS_BASE_SCORE=[0,8,17,27,38,52]`（边际递增 8·9·10·11·14），每个战斗功能标签 +3 分。
- **品阶 tier**：每 `TIER_STEP=22.5` 分一阶，`tier=floor(power/22.5)+1`，夹在 1..13。`SUN_BY_TIER` 给出品阶→局内阳光价（T1=50 … T7=500 … T13=900）。**T10 是每 50 轮的硬门槛而非天花板，首版天花板 T13。**
- **设计代币（定制器货币）**：`TOKEN_AXIS_CUM=[0,40,80,120,180,260]` 为单轴第 n 档累计价；破防标签 `shield_break/armor_pierce` 各 80 代币。`design_token_for_build` 会先扣除**免费底盘**隐含档（100HP=坦度1、远程整行=打击面2/近战1）再算净额。教学锚点：「火力3 + 破盾 = 200 代币 / T3 / 150 阳光」。
- **三维成本**：一株植物的成本不是只有阳光，而是 **阳光（由 tier 派生）+ recharge 冷却（与阳光并列的出场率平衡参数）+ 设计代币（定制阶段）**。`derive_recharge` 按品阶给五档 CD（5 / 7.5 / 15 / 27.5 / 50 秒），强机制标签（one_shot、hard_cc、summon、fullscreen、manual_ultimate）强制加长 CD，且 5s 是不可突破的硬下限。

### 4.5 模拟、出怪与 AI（board / wavegen / bot）

- `board.Simulation` 以 `DT=0.1` 固定步长推进：按波次表/预算刷怪、敌人左移与啃食、植物按间隔产生弹道、弹道移动与矩形碰撞后调 `balance.resolve_hit`、敌人越过 `LAWN_MOWER_TRIGGER_X=-0.2` 触发该行小车/判定破线丢命。同一 seed 完全可复现（有 `test_determinism_same_seed` 守底）。
- `wavegen`：用「点数预算随波次递增 × 关卡系数」控制刷怪量，支持固定表、出怪白名单（M1 只出 normal/fast/banner/cone，M2 加盾兵，无尽才全解锁）、单波数量上限。
- `bot.RuleBot` 提供两种策略做对照：
  - `smart`：开局冲 3 朵向阳花的经济流、`_row_needs_break` 检测到格挡行就**刚性只买破盾株**（买不起就持币，不砸对盾无效的直射）、中期补到 5 朵经济、后期 sun≥300 爆兵铺输出列；
  - `dumb`：只会基础直射，用于验证「不会针对能力就应被卡死」。

### 4.6 数据 JSON 结构

植物（以 `data/plants/peashooter.json` 为例）：

```json
{
  "key": "peashooter", "cn": "豌豆射手", "role": "ranged", "tier": 2,
  "axes": {"fire": 2, "area": 2, "pierce": 0, "durability": 1, "control": 0},
  "tags": [], "sun": 100, "recharge": 5.0, "hp": 100,
  "art_prompt": "……（美术风格提示词）",
  "combat": {
    "atk_interval": 1.0, "damage": 20,
    "range": {"type": "row", "cells": 9},
    "projectile": {"key": "pea", "speed": 320, "hit": "single"}
  }
}
```

- 敌人必填：`key/cn/hp_body/speed/bite_dps/budget`，可选 `armor{hp,reduction}`、`block_flat`、`weight`、`slow_resist`、`kb_immune`、`regen`、`tags`；`boss_50.json` 还预留了 `summon/phase` 字段（M3 实现）。
- 关卡 JSON 由 `scripts/gen_levels.py` 生成，`scenarios/level_run.py` 负责把关卡翻译成出怪表再喂给 Simulation。
- `counter_map.json`：`matchups` 定义 7 组克制（格挡/护甲/厚本体/高速/人海/重量免控/高啃咬）各自的敌人字段、被什么标签或轴反制、惩罚什么构筑、以及结算规则文字；`selector_rules` 是 6 条「玩家偏什么构筑 → 反制选什么怪」的规则；`headless_targets` 给出目标胜率区间与可解性闸门（最低 0.50）。

### 4.7 场景模块（scenarios/）

| 模块 | 里程碑 | 职责 |
|---|---|---|
| `customizer.py` | M2 | 植物定制器：五轴配点 + 功能标签 → 校验 → 算代币/品阶/阳光/CD → 产出可注册植物卡；破盾/穿甲标签在此生成 |
| `zombie_editor.py` | M5 | 僵尸编辑器：四维点数 + 能力标签预算，产出通过 `validate_enemy` 的可注册敌人 |
| `endless.py` | M4 | 无尽轮次缩放、按 counter_map 自动反制选怪、每 50 轮 Boss、`ensure_solvable` 可解性闸门（solver 回调待接） |
| `progression.py` | — | P1–P4 阶段推进、设计代币奖励、解锁流 |
| `level_run.py` | — | 关卡 JSON 与 Simulation 之间的桥接 |

---

## 5. 平衡体系与校准结论

设计纲领（详见 `game_balance_design.md` v0.2，**以该文档为唯一事实来源**）：

- 先做机制减法再落数值；用五轴点数预算防止单卡全能；同威胁点预算内把点数投到玩家短板轴，「打贬值不堆数值」。
- 前期怪最多带 1 个机制，第 50 轮 Boss 才允许多机制复合；每个生成组合必须存在当前卡池可打出 >50% 胜率的解法，否则作废重 roll。
- 怪物能力与植物能力经 `counter_map` 严格对位。

100 局 headless 校准（`reports/headless_calibration_report.md`，确定性 seed，本次复核 39 单测全绿）：

| 场景 | win | clean | 结论 |
|---|---|---|---|
| m1_day_10w 新手主线 | 0.92 | 0.75 | 教学友好高胜率，达标 |
| m2_shield **smart**（带破盾） | 1.00 | 1.00 | 针对配装可稳定过 |
| m2_shield **dumb**（仅直射） | 0.00 | 0.00 | 格挡死锁，不会针对即被卡死 |
| boss50_late（T10 高配） | 0.79 | 0.51 | 50 轮硬门槛可过（略高于理想区间，可接受） |
| boss50_basic（低配） | 0.00 | 0.00 | 品阶门槛分化成立 |
| endless_25w（未配反制器） | 0.30 | 0.24 | 不在 M0 收敛，明确归 M4 |

校准只调了**节奏/AI 旋钮**（首怪时间、活跃行数、单波密度、白名单、Bot 经济与破盾策略等），未改任何已锁定战斗数值。

---

## 6. AI 美术管线（重点，含完整使用方法）

### 6.1 端到端流程总览

```
① gen_image_qwen 文生图            ② 同一 base 做图像编辑逐帧        ③ PIL 去背 + 拼表            ④ 动画框架加载
base.png（760×1280 白底）  →   idle/attack/hurt(/walk) 各帧  →  4×4、64px/格、256×256 表  →  animation.SpriteSheet
   先人工确认风格再继续            星型锚定（都引用同一张 base）     全局缩放+底部锚点，缺帧兜底      切 idle2/walk4/attack3/hurt2
```

### 6.2 生图客户端 gen_image_qwen.py 与鉴权

- 接口基座 `https://api-inference.modelscope.cn/`，模型 `Qwen/Qwen-Image-2.1`。
- **Token 只从环境变量读**（`MODELSCOPE_TOKEN` 或 `MS_TOKEN`），代码里不写死。本机 token 存于 `anim_demo/.ms_token`（39 字节，**机密：绝不入库、绝不打进交接包、不要贴进文档/聊天**）。跑管线前在当前 shell 注入：

```powershell
$env:MS_TOKEN = (Get-Content -LiteralPath anim_demo\.ms_token -Raw).Trim()
$env:PYTHONIOENCODING = "utf-8"   # 让中文 prompt/日志在控制台不乱码
```

- 调用流程：带 `X-ModelScope-Async-Mode: true` 头 POST `v1/images/generations` 拿 `task_id` → 每 5s 轮询 `v1/tasks/{id}`（带 `X-ModelScope-Task-Type: image_generation`）→ `SUCCEED` 后下载 `output_images[0]`。
- 图像编辑：把本地参考图转 base64 data-uri 放进 payload 的 `image_url` 列表。
- **必须牢记的坑**：
  1. **请求体绝不能带 `size` 字段**——该模型此接口带 size 会直接 submit HTTP 500；默认返回约 **760×1280** 白底不透明竖图，后期再裁切。
  2. prompt 必须强制「**纯白色干净背景 #FFFFFF、全身居中、四周留白、无地面投影、无文字水印**」，否则自动去背会失败。
  3. 文生约 20s/张；图像编辑慢时单帧轮询可能 40+ 次（1–3 分钟）；偶发服务端瞬时 500（如 `unknown FC status: Dequeued`）是服务端问题而非 prompt 问题，**重跑即可补齐**。

### 6.3 prompt 工程与多帧一致性（不漂移、不乱长器官）

`gen_plant.py / gen_enemy.py` 内置两段共用约束：

- `TAIL`：固定平视、画面只有一个角色、**严格保持既有器官结构、不额外长出手脚/武器/无关物体**、底部形态每帧与立绘一致、纯白底、Q 版粗描边明快平涂、无投影无文字。
- `EDIT_GUARD`：每次图像编辑都「以参考图为唯一基准，画完全相同的那一只」，只允许在不改身份的前提下调姿态/表情。
- **星型锚定，不要链式**：每一帧都引用同一张 `base.png` 做参考，而不是用上一帧生成下一帧——链式会累积漂移。
- 植物风格：绿色系为主；敌人风格：Q 版可爱不血腥、灰绿/土褐/暖橙/金属灰、避免大面积紫色（普通僵尸允许小面积暗紫裤）。

### 6.4 植物管线 gen_plant.py（固定塔，无行走帧）

**设计决定：植物种在格子上不移动，因此不生成 walk 帧以提速**（以后想做再补）。

- `PLANTS` 字典为每种植物配置 `cn`（中文名）、`base_desc`（原创立绘描述）、`attack`（attack_0 蓄力 / attack_1 发力 / attack_2 回收 三句特色动作）。经济/防御/爆炸类的 attack 不是射击：向阳花是孕育/托起阳光，坚果是下沉硬化格挡，爆栗果是引信/卡通炸裂/空壳。
- `REQUIRED_PNG = [idle_0, idle_1, attack_0..2, hurt_0, hurt_1]` 共 **7 帧**：`idle_0` 直接由 base 复制，其余 6 次 AI 调用。walk 四槽在拼表阶段由 `build_spritesheet` 自动回退为 idle_0 静立。
- 早期已生成的前 10 个植物保留了「微风轻摇」walk 帧（目录里是 11 张），不浪费；后 3 个（winter_melon/pine_needler/custom_shieldbreaker）为新标准 7 张。

```powershell
& $py anim_demo\gen_plant.py --plant bamboo --base     # 单只出立绘（先定风格）
& $py anim_demo\gen_plant.py --plant bamboo --frames   # 出该植物动作帧（已存在自动 skip）
& $py anim_demo\gen_plant.py --plant all --base        # 全部植物出立绘
```

### 6.5 敌人管线 gen_enemy.py（会移动，完整 11 帧）

- `REQUIRED_PNG` 共 **11 帧**：idle×2、**walk×4 真正的左右脚交替蹒跚行走循环**、attack×3、hurt×2。
- `ATTACK_SETS` 提供三套攻击模板，由每个敌人的 `attack_kind` 选择（具体归属以 `gen_enemy.py` 内配置为准）：`bite` 啃咬（普通/快速/旗手/路障类）、`shield` 举盾顶撞（格挡盾兵）、`slam` 重击举臂砸下（巨人/Boss 类）。

```powershell
& $py anim_demo\gen_enemy.py --enemy normal --base
& $py anim_demo\gen_enemy.py --enemy all --frames
```

### 6.6 批量驱动 gen_roster.py（推荐入口）

统一编排 21 个单位，带**断点续跑 + 失败不中断 + 状态落盘**：

```powershell
& $py anim_demo\gen_roster.py --phase base               # 先出全部立绘
& $py anim_demo\gen_roster.py --phase frames             # 立绘人工确认后批量出动作帧
& $py anim_demo\gen_roster.py --phase sheet              # 去背拼 4×4 精灵表
& $py anim_demo\gen_roster.py --phase all                # 一条龙（后台长任务）
& $py anim_demo\gen_roster.py --phase frames --kind plant          # 只跑植物
& $py anim_demo\gen_roster.py --phase frames --keys shield_cadet   # 只补指定 key
```

- 底层对已存在的 base/帧自动 skip，重复运行只补缺口；单单位/单帧抛 `SystemExit` 会被捕获记录、不影响其他单位，结尾汇总 failures，退出码 1 表示有失败。
- 进度写 `assets/art_build_status.json`；判定「某单位帧齐全」依据各模块自己的 `REQUIRED_PNG`（植物 7、敌人 11）。
- **单帧重 roll 流程**：删掉不满意的那张 `frames/xxx.png` → 重跑 `--phase frames --keys <key>`，只补被删的帧，其余秒过；整只风格不对则删 `base.png` 从 `--phase base` 重来。

### 6.7 去背拼表 build_spritesheet.py（纯 Pillow）

固定网格约定（与 `animation.ANIM_DEF` 严格对应）：4×4、每格 `FRAME=64`、整表 256×256；行序 `idle/walk/attack/hurt`，有效帧数 `ROW_FRAMES=[2,4,3,2]` 共 11 格，其余 5 格留白。

- **去背双阈值**：`LO=12, HI=48`，距离定义 `dist=max(255-r,255-g,255-b)`（纯白≈0）。`dist<=LO` 全透明、`>=HI` 不透明、中间线性羽化保留抗锯齿。
- **目录模式全局统一缩放**：所有帧先去背裁到不透明 bbox，再用同一个 `scale`（按最宽/最高帧算，`MAX_W=62/MAX_H=60`）缩放，水平居中、底边锚点 `DIR_BOTTOM_PAD=4` 贴格——这保证同一角色帧间身体等大、着地点一致，不会忽大忽小悬空。
- 缺帧打印 `[warn]` 并用 `idle_0.png` 兜底（不报错），所以植物缺 walk 也能正常出表。
- 两种输入模式：

```powershell
# 单立绘：所有格放同一标准姿态（动态交给 animation.py 的程序化变换）
& $py anim_demo\build_spritesheet.py 输入图.png 输出表.png
# 帧目录：逐格去背拼多帧表（gen_roster 内部就是调 build_dir）
& $py anim_demo\build_spritesheet.py anim_demo\assets\plants\bamboo\frames anim_demo\assets\sprites\bamboo.png
```

> 不要轻易全局调去背阈值：调激进会误伤冰西瓜/向阳花这类浅色、近白边缘。个别残留（见 §9 铁桶淡影）应定点处理而非改全局。

### 6.8 动画框架 animation.py

- `ANIM_DEF` 定义四个状态的行号、帧数、每帧毫秒、是否循环：idle(2,460ms,循环)、walk(4,130ms,循环)、attack(3,150ms,单次结束回 idle)、hurt(2,160ms,单次)。
- `SpriteSheet(path)`：文件存在则 `load().convert_alpha()` 并按网格切出各状态帧 + 白色受击剪影；文件不存在会自动程序化生成一张占位史莱姆表（保证永远可跑）。
- `AnimatedSprite`：按毫秒推进切帧，自带呼吸/脚步缩放、攻击 squash&stretch、受击染白、朝向翻转；以底部中心为锚点 blit，缩放不悬空。运行中按 R 可热重载真图。
- 真图替换零改码：把同网格 PNG 放到同名路径即可。

### 6.9 新增一个单位的标准步骤

1. 在 `tdgame/data/plants|enemies/` 加战斗 JSON（loader 校验通过、`list_roster.py` 能看到）；
2. 在 `gen_plant.py` 的 `PLANTS`（或 `gen_enemy.py` 的 `ENEMIES`）加 `cn/base_desc/attack(/attack_kind)` 配置；
3. `--phase base --keys <key>` 出立绘，**人工确认风格**；
4. `--phase frames --keys <key>` 批量出帧，失败帧删除后重跑；
5. `--phase sheet --keys <key>` 拼表；
6. 按 §8 做四层校验；
7. （后续工作）在渲染层把 key 映射到精灵表路径。

---

## 7. 渲染壳、演示与植物工坊

- `tdgame/app_pygame.py`：pygame 薄壳，当前用色块画 8 卡栏 + 5×9 棋盘 + 占位植物/敌人，验证事件循环与渲染通路；支持 `--smoke --frames N --shot out.png` 离屏截图。**精灵表尚未接入这里**（见 §9 缺口）。
- `anim_demo/sprite_animation_demo.py`：精灵动画正式演示窗口，能看到 idle/walk/attack/hurt 切换与程序化弹性。
- `anim_demo/plant_editor.py`：Tkinter 植物工坊完整向导（多步、后台线程队列回传、含子弹贴图步骤），配置化造角色并可产出能被 loader 扫描的目录。
- 根目录两个 `tower_defense_*.py`：逆向阶段结束后做的原创独立原型（tkinter 与 pygame 双表现层、玩法数值一致、8 波守家），是 tdgame 的前身，可直接运行参考。

---

## 8. 测试与美术校验方法

### 8.1 引擎单测（39 个，全部应通过）

```powershell
& $py -m unittest tests.test_balance tests.test_engine tests.test_scenarios
```

- `test_balance.py`（12）：伤害管线、格挡归零与破盾、护甲穿甲与 EHP 守恒、power/tier/代币/recharge 派生等；
- `test_engine.py`（11）：Simulation 推进、确定性同 seed、出怪/啃食/小车破线等；
- `test_scenarios.py`（16）：定制器/僵尸编辑器/无尽反制/关卡桥/格挡考场 smart 胜 dumb 败等。
- 另有 `tests/diag.py`、`diag_m2.py`、`smoke_run.py` 与 `scripts/smoke_test*.py` 做诊断与冒烟。

### 8.2 美术四层校验（本次 21 张表全部 ALL_OK）

1. **帧齐全性**：按各模块 `REQUIRED_PNG` 回读每个单位 base 与全部帧是否存在；
2. **PIL 客观校验**：每张表 256×256 RGBA、11 个有效格非空、5 个留白格干净透明、角落实测透明；
3. **pygame(SDL dummy) 框架加载**：先 `set_mode`，对每张表构造 `SpriteSheet`，断言四状态帧数为 2/4/3/2、每帧 64×64 且 `get_bounding_rect()` 非空；
4. **人工读眼**：跨帧角色一致、不漂移、不长新器官，去背干净、锚点对齐，浅色调（冰西瓜）边缘不被误透明。

---

## 9. 已知缺口与后续路线

| 项 | 现状 | 归属/建议 |
|---|---|---|
| 精灵表未接战斗工程 | `tdgame/data` JSON 与 `app_pygame.py` 仍用色块占位，未指向 21 张新精灵表 | **最直接的下一步**：加 key→sprite 路径映射并在薄壳加载 `SpriteSheet` |
| 铲种升级 | `board` 暂无 `remove_plant` API，导致无尽后期廉价株占满列、阳光囤积（sunL≈709、胜率 0.30） | M4：补铲种 + 高价株偏好 + 接 headless solver 可解性闸门 |
| Boss 召唤/多阶段 | `boss_50.json` 已有 summon/phase 字段，引擎当前按高威胁精英处理 | M3 实现召唤与阶段切换 |
| 内置穿甲植物 | 暂无自带 armor_pierce 的植物，该标签由定制器配方生成，高甲暂靠高爆灌伤代理 | M2 定制器联动 |
| M2 其余 5 考场 | armor/speed/swarm/control/weight 是可跑骨架但敌人编排仍为预算模板 | 真机联调时做成像格挡考场一样的固定教学表 |
| 植物 walk 帧 | 固定塔不移动，当前 walk 槽回退静立 | 以后需要「微风/施法位移」时再补，管线已留好 4 槽 |
| 铁桶精灵表淡影 | `enemies/bucket.png` 的 idle_0 格脚下有一缕极淡半透明灰影（源自 base），其余帧干净 | 可定点 PIL 清理该格或单独重 roll bucket base；**勿为此全局调去背阈值** |

---

## 10. 踩坑 FAQ（交接必读）

1. **unittest 输出一片红字 NativeCommandError？** 那是 PowerShell 把 stderr 包装了，看结尾 `Ran N / OK`，退出码 0 即通过。
2. **`No video mode has been set`？** dummy 离屏下 convert_alpha 前先 `pygame.display.set_mode()`。
3. **千问 submit 500？** 先查请求体是不是误带了 `size`（必须去掉）；轮询中途的 `Dequeued` 500 是服务端瞬时故障，重跑补齐。
4. **Token 报错/泄露风险？** token 只走环境变量 `MS_TOKEN/MODELSCOPE_TOKEN`；`.ms_token` 不得入库、不得入包、不要贴出来。新同事需用自己的 ModelScope token。
5. **帧间角色越长越歪/多手多脚？** 确保每帧都星型引用同一张 base、prompt 带 TAIL+EDIT_GUARD；不要用链式（上一帧生下一帧）。
6. **拼出来帧间忽大忽小/悬空？** 必须走目录模式的全局缩放与底部锚点，不要对每张图各自 normalize。
7. **去背把浅蓝/金黄边缘抠没了？** 别全局降阈值；对问题帧单独处理。
8. **改了 JSON 没生效或坏数据进了模拟？** 先跑 `scripts/list_roster.py` 看 `loader errors`，Registry 会拒绝越界配装。
9. **PowerShell 5.1 语法**：不要把 `if` 当内联表达式塞进括号；本机为 pwsh 7，三元用 `? :`；复杂输出建议重定向到 `logs/*.log` 再读（本机控制台偶尔不回显 stdout）。

---

## 11. 交接物清单与本次验证记录

**两份压缩包（项目根目录）**

1. `pvz_tdgame_runtime_20261104.zip` —— 轻量运行包：全部代码（tdgame/scripts/tests/reports）、自包含 `libs/`、根文档与两个原型、`anim_demo` 全部脚本 + **成品精灵表 `assets/sprites`**。解压即可跑 headless、单测、pygame 冒烟与动画框架。**不含** AI 原始大图、token、`.git`、`__pycache__`、逆向目录与日志。
2. `pvz_tdgame_art_sources_20261104.zip` —— 美术源材包：21 单位的 760×1280 原始立绘与逐帧（`assets/plants`、`assets/enemies`）、管线脚本与 `art_build_status.json`，用于单帧重 roll、重新拼表与扩员。不含 token。

**交接时实测（2026-11-04）**

- 单元测试：`Ran 39 tests ... OK`，退出码 0；
- 花名册：`scripts/list_roster.py` 输出 `loader errors: none`，13 植物 + 8 敌人数值齐全；
- pygame 薄壳：SDL dummy 冒烟退出码 0 并产出截图；
- 美术：21 张成品精灵表 PIL 客观校验 + pygame 框架加载均 `ALL_OK`（11 有效格、64px、可切 idle2/walk4/attack3/hurt2）。

接手后先跑 §1.3 的三条命令，看到 39 个 OK、headless 生成报告、冒烟截图产出，即说明环境与工程完好。
