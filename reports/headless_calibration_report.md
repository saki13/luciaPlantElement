# Headless 数值校准报告（M0）

- 日期：2026-11-04
- 数据来源：`reports/headless_20261104_023736.json`（每场景 100 局，确定性 seed）
- 事实口径：`game_balance_design.md` v0.2；本报告只记录**节奏/AI 旋钮**的调整，未改动任何已锁定的战斗数值（伤害、血量、护甲、格挡、阳光价、recharge 公式）。

## 1. 方法

- 纯标准库 headless 引擎（`tdgame/engine`）固定步长 DT=0.1s，同一 seed 完全可复现（单测 `test_determinism_same_seed` 守底）。
- 每个场景跑 100 局，用 `RuleBot` 两种策略对照：`smart`（按 counter 选卡、刚性破盾、标准经济流）与 `dumb`（只会基础直射）。
- 指标：win（清空出怪表且存活）、clean（零破线零丢车）、mower（触发小车局占比）、breach（破线次数均值）、lives、终局阳光 sunL、时长。

## 2. 校准过程中调整的旋钮（均非战斗数值）

| 旋钮 | 调整 | 解决的问题 |
|---|---|---|
| 首怪时间 `first_spawn_at` | 5s → 12s | 给经济开局留出苗窗口，避免 72–100s 确定性崩盘 |
| 前期活跃行数 | `active_rows=min(5,1+w//2)` | 前两波单路、w8 铺满 5 行，平滑多线教学曲线 |
| M1 单波密度 | `cap_fn=min(6,2+w)` + 出怪白名单 | 新手主线 w4 不再误刷 650EHP 铁桶形成尸潮 |
| 出怪白名单 `allowed` | M1 仅 normal/fast/banner/cone；M2 加盾兵；无尽才全解锁 | 把"机制出现时机"与教学阶段严格绑定 |
| Bot 经济流 | 接敌前冲 3 朵向阳花、危及线军事优先、中期补到 5 朵 | 修复 Bot 自我锁死经济上限（曾限死 2 朵） |
| Bot 刚性破盾 `_row_needs_break` | 需要破盾的行只买破盾株，买不起就留现金，不砸对盾无效的直射 | 修复"零钱被无效豌豆+反复补墙吃光、永远攒不到 150"的死锁 |
| Bot 后期爆兵 | sun≥300 时尽快铺满输出列、按威胁选高伤株 | Boss 局终局阳光囤积从 2650 降到约 161–218，胜率 0.03→0.79 |
| M2 考场形态 | 两行聚焦、12 只含 4 盾兵、起始 200 阳光、固定表 | 让格挡机制不被随机尸潮淹没，形成可判定的教学对照 |

## 3. 100 局实测 vs 设计目标

| 场景 | win | clean | mower | lives | 目标（counter_map.headless_targets） | 判定 |
|---|---|---|---|---|---|---|
| m1_day_10w（新手主线） | 0.92 | 0.75 | 0.69 | 4.50 | 教学友好、高胜率 | 达标 |
| m2_shield **smart**（带破盾） | **1.00** | 1.00 | 0.00 | 5.00 | 配出针对能力即可稳定过 | 达标 |
| m2_shield **dumb**（仅基础直射） | **0.00** | 0.00 | 1.00 | 5.00 | 不会针对能力应被卡死 | 达标（格挡死锁） |
| boss50_late（T10 高配卡池） | 0.79 | 0.51 | 0.28 | 5.00 | 0.40–0.60 为理想区间 | 略高，作为"50 轮硬门槛可过"可接受 |
| boss50_basic（低配卡池） | 0.00 | 0.00 | 0.00 | 5.00 | ≤0.10 | 达标（品阶门槛分化） |
| endless_25w（深度压力，未配反制器） | 0.30 | 0.24 | 2.23 | 1.61 | 配反制植物后的中段目标 0.55–0.75 | **不在 M0 收敛，归 M4** |

## 4. 关键机制结论（均有单测/对照守底）

1. **格挡双轨成立**：盾兵 `block_flat=20` 把豌豆/双发每发 20 伤害完全归零，dumb 局两只满血盾兵卡死僵持到超时并丢车；`shield_break` 标签跳过格挡，smart 局 t60/t73 各出一株破盾株，99s 满血零丢车。对应单测 `test_block_can_zero_and_break`、`test_m2_shield_smart_wins_dumb_cannot`。
2. **品阶门槛分化成立**：boss_50（总 EHP 4400、weight99、免控）低配卡池 0% 通关、T10 高配 79%，验证 T10 作为 50 轮硬门槛、而非天花板（首版天花板 T13）。
3. **护甲 EHP 守恒**：穿甲倍率仅作用甲段、溢出按 (1−reduction) 折减进本体，路障 280 / 铁桶 650 EHP 口径由 `test_armor_*` 与 `test_nominal_ehp_locked` 守底。

## 5. 已知缺口与归属（不在 M0 强行过拟合）

- **无尽终局阳光囤积（sunL≈709）与胜率 0.30**：满屏后廉价豌豆占满输出列，缺乏"铲掉低 tier 株升级高伤株"能力（board 暂无 remove_plant API）。归 **M4**：补铲种升级 + 后期高价株偏好，并把 `endless.ensure_solvable` 的 solver 回调接上 headless（>0.5 胜率闸门，否则重 roll）。
- **Boss 召唤/多阶段未实现**：`boss_50.json` 已含 summon/phase 字段，引擎 M0 把它当高威胁精英测门槛；召唤逻辑归 **M3**。
- **暂无带 armor_pierce 的内置植物**：该标签由 M2 定制器配方生成（`scenarios/customizer.py` 已支持），现阶段高甲靠 bombberry/melonpult 高爆灌伤代理。
- **M2 其余 5 个能力考场**（armor/speed/swarm/control/weight）已落可跑骨架，但敌人编排还是预算模板，需在 M2 真机联调时做成像格挡考场一样的固定教学表。

## 6. 复现命令

```powershell
$py = "D:\ProgramData\anaconda3\python.exe"
# 全量单元测试
& $py -m unittest tests.test_balance tests.test_engine tests.test_scenarios `
    tests.test_replay tests.test_golden_sync tests.test_session tests.test_boss tests.test_endless
# 一键总检（六关：单测 / 精灵表 / 校准基线 / 关卡回归 / 渲染断言 / 一致性门禁）
pwsh -File scripts\check_all.ps1
# 100 局 headless 回归
& $py -m tdgame.headless_run --runs 100
# pygame 薄壳无显示冒烟 + 截图（pygame 在项目自包含 libs/）
$env:SDL_VIDEODRIVER="dummy"; $env:SDL_AUDIODRIVER="dummy"
$env:PYTHONPATH="D:\lucia\rea\project\pvz\libs;D:\lucia\rea\project\pvz"
& $py -m tdgame.app_pygame --smoke --frames 3 --shot logs\app_smoke.png
```

---

## 7. 2026-11-04 复核更新（接手后）

本节记录接手方对本报告的复核与改动。**第 3 节的历史数字保留原样**，此处只写变化。

### 7.1 无尽胜率收敛（原 0.30/0.40 → 0.60）

原报告把无尽 0.30 归给 M4「等反制器接入」。复核后的实测链条：

| 实验 | 25 波无尽胜率 |
|---|---|
| 原节奏（单波密度 `3 + w//2`） | 0.40 |
| 1/16 槽位换成 `normal`/`fast`（**弱怪**对照） | 0.55 / 0.50（变容易，证明替换机制没坏） |
| 1/32 槽位换成 `shield_cadet` | 0.05 |
| 1/16 槽位换成 `shield_cadet` | 0.00 |
| 1/16 槽位换成 `bucket`/`giant`（真反制） | 0.00 |

即：**任何有意义的反制注入都会把 Bot 打到 0**——它本来就卡在悬崖边。
根因与「Boss 打不死」同源：`block_flat` 与重甲相对卡池 DPS 过强。

因此本轮**不靠反制器**，而是按本报告一贯的口径（只调节奏旋钮）把单波密度
从 `3 + w//2` 放缓到 `3 + w//3`：

| 场景 | win | clean | mower | sunL |
|---|---|---|---|---|
| endless_25w（新） | **0.60** | 0.50 | 1.20 | 1081 |

0.60 落在 `counter_map.headless_targets` 的 0.55–0.75 区间内。**未改动任何战斗数值。**

### 7.2 Boss 门槛的真相（重要）

原报告第 3 节写 `boss50_late 0.79`、第 4 节称「品阶门槛分化成立」。复核发现：
Boss 的 `block_flat = 30` 把**整个卡池的伤害归零**（豌豆/双发 20、荆棘 25 全部无效），
唯一有效的 `custom_shieldbreaker` 只有 28.6 dps，打 5500 原始伤害要 193 秒，
而战斗只有约 120 秒。实测 `boss_50` 击杀率恒为 0。

**原 0.79 的胜率全部来自割草机清场**（Boss 走到最左被小车碾死，而它是最后一个敌人）。

曾试 `mower_immune` 让 Boss 不被白嫖，结果直接变 0% 不可通关，已回退。
这需要一次专门的 Boss 数值重做（降 `block_flat` 或给卡池补高单发），
已登记为 `BACKLOG.md` 的 **D-11**，不在本轮范围内。

### 7.3 关卡回归补建

原报告只覆盖 6 个手搓场景，`data/levels/*.json` 从未被模拟（18 关里只有 2 关跑过）。
本轮新增 `scripts/check_levels.py` + `reports/levels_baseline.json`，当前覆盖 **25 关**
（M1×10 + M2×6 + M3×8 + Boss×1），5 seeds/关，逐字段比对基线。

### 7.4 测试与门禁

单测 39 → **92**；新增六道一键总检 `scripts/check_all.ps1`（全绿约 29s）。
