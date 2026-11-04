# 待修补任务清单（BACKLOG）

> 生成日期：2026-11-04
> 依据：`HANDOVER.md` §9、`tdgame/README.md` 的 M0–M5 预留边界、`game_balance_design.md` §18、
> 以及对代码/数据/测试的实测审计（每条都标了证据位置）。
> **优先级按"不修会让后续工作失真"排序**，不是按"看起来爽"排。

---

## 进度更新

### 2026-11-04 · 批次 ① 完成

| ID | 状态 | 说明 |
|---|---|---|
| B-01 关卡回归缺失 | ✅ 已修 | 新增 `scripts/check_levels.py` + `reports/levels_baseline.json`，18 关全部纳入闸门（5 seeds/关，3.3s）。**发现：智能 Bot 在 18 关上全部 100% 通关——关卡没有难度曲线，全都过易** |
| B-03 奖励数据双写 | ✅ 已修 | 删除 `progression.CHALLENGE_TOKEN_REWARD`，改为只读关卡 JSON 的 `reward.design_tokens`；新增 2 个测试守住（含"硬编码表不得复活"） |
| B-04 渲染层无测试 | ✅ 已修 | 新增 `scripts/check_render.py`：21 张表加载、21 单位动画推进、截图非纯色、降级模式可跑 |
| B-02 `scenarios/` 无线上调用方 | ⏳ 批次 ② 处理 | 交互版会真正调 `progression`（关卡奖励）与 `endless`（无尽模式） |
| B-05 CI 未实测 | ⏳ 待一次真实 push | CI 已补上关卡回归与渲染断言两步 |
| B-06 门禁只覆盖 `resolve_hit` | ⏳ 随阶段 2 | — |

**总检已从 4 关扩到 6 关**，全绿 23.2s。测试 50 → 52。

### 2026-11-04 · 批次 ② 完成（pygame 侧）

| ID | 状态 | 说明 |
|---|---|---|
| C-01 游戏不能玩 | ✅ 已修（pygame） | 新增 `tdgame/engine/session.py` 的 `PlaySession`：点选卡、种植、铲种、冷却、实时步进（按 `DT` 累计，与 headless 完全一致）、胜负。`app_pygame.py` 重写为**可玩客户端**：鼠标点卡/点格、X 铲子、R 重开、Q 退出、卡栏带冷却遮罩与变灰、中文字体回退到英文。新增 `tests/test_session.py` 22 个 headless 交互测试 |
| C-06 无铲种 API | ✅ 提前完成 | `board.remove_plant()`：不返还阳光，且会把正在啃食的敌人的 `eating` 置空（有测试守） |
| D-06 Godot 不是游戏 | ⏳ 未做 | Godot 仍是回放播放器。要可玩必须先解决"GDScript 侧没有运行时"——即 E-01（阶段 2 主体）或 Python↔Godot IPC。**pygame 侧已可玩，所以"能不能玩"这个里程碑已达成** |

测试 52 → **74**；六关仍全绿 22.7s。

### 2026-11-04 · 批次 ③ 完成 + 批次 ④ 部分

| ID | 状态 | 说明 |
|---|---|---|
| C-02 5 个考场是预算模板 | ✅ 已修 | `gen_levels.py` 把 m2_armor/speed/swarm/control/weight 全部改成固定教学表（各自只教一种能力）。时长从 55–84s 涨到 80–111s。重新生成后只有这 5 个文件变化，其余 13 关字节未动 |
| C-03 无内置穿甲植物 | ✅ 已修 | 新增 `thorn_piercer`（荆棘穿甲株）：T3 / 150 阳光 / 7.5s CD / 25 伤 / `armor_pierce`。美术由子 Agent 用千问管线生成并通过四层校验（mean 33.9×56.8，aspect 0.60），已加入 M2/M3 关卡卡池。**但 Bot 的选卡策略不会用它**（见 D-10） |
| C-04 Boss 无召唤/多阶段 | ✅ 已修 | `Enemy` 增加 summon/phase 字段；`board` 增加 `_update_boss_phases`（半血提速 1.5×、召唤间隔 ×0.6）与 `_update_summons`（12s 一只、同父上限 3）。6 个新测试。**顺带修掉一个真 bug**：Boss 破线后被 `_cleanup` 移除，导致"出怪跑完且场上无敌人"误判通关 → 加 `_check_end` 已定结果守卫 |
| C-05 进阶关卡 2/10 | ⏳ 未做 | — |
| C-07 solver 未接 | ⏳ 未做 | — |
| C-08 无尽胜率未收敛 | ⏳ 未做 | 仍 0.40 |

**批次 ③④ 过程中挖出的三个新问题**

- **D-10 Bot 不会用新卡**：把 `thorn_piercer` 加进 `POOL_LATE` 后 `boss50_late` 从 0.40 掉到 0.00——Bot 花 150 阳光买它却挤掉经济。它的选卡只看"便宜/有针对性"，不评估性价比。目前该植物只进关卡卡池（给玩家用），不进 Bot 的校准卡池。
- **D-11 Boss 实际上打不死**：实测 `bosskill` 在 `block_flat=30` 时恒为 0；把 EHP 从 4400 砍到 1600 也只有 5%。根因是 **`block_flat=30` 把整池伤害归零**（豌豆/双发 20、荆棘 25 全部无效），后期唯一有效的 `custom_shieldbreaker` 只有 28.6 dps。**之前 0.79 的胜率全部来自割草机清场。** 曾试 `mower_immune` 让 Boss 不被白嫖，结果直接 0% 不可通关，已回退——正确解法是一次专门的 Boss 数值重做（降 block 或给卡池补高单发），不是调参数。
- **D-12 千问客户端无重试**：`gen_image_qwen.py` 的下载与轮询没有重试，一次 `SSLError` 就中断整批 `--frames`（子 Agent 本次踩 5 次网络错、1 次整批 abort）。

测试 74 → **80**；六关全绿 22.1s。

### 2026-11-04 · 批次 ④ 收口

| ID | 状态 | 说明 |
|---|---|---|
| C-04 Boss 召唤/多阶段 | ✅ 已完成（上一条） | — |
| C-05 进阶关卡 2/10 | ✅ 已修 | M3 从 2 关补到 **8 关主线 + 1 关 Boss**（共 25 关）。卡池分两段、波数与单波上限逐关递进，实测胜率从 1.00 平滑降到 0.60，难度曲线成立 |
| C-07 solver 未接 | ✅ 已修 | 新增 `tdgame/engine/solver.py`（`headless_win_rate` / `make_solver`）。`ensure_solvable` 现在真能拿到胜率、按 `max_rolls` 重 roll 并在不可解时给 warning。12 个新测试覆盖反制器 + solver + 闸门 |
| C-08 无尽胜率收敛 | ❌ **未达成，已定性** | 见下 |

**C-08 的结论：不是反制器的问题，是 Bot 太弱**

反制器原来**根本没被调用**（`headless_run` 的无尽场景从不调 `pick_counter_enemies`）。本轮把它接上了，做法是"按比例替换槽位"而不是整池加权。实测数据：

| 场合 | 胜率 |
|---|---|
| 无反制（对照） | 0.40 |
| 1/16 槽位换成 `normal`/`fast`（弱怪，做对照） | **0.55 / 0.50**（变容易，符合预期） |
| 1/32 槽位换成 `shield_cadet` | 0.05 |
| 1/16 槽位换成 `shield_cadet` | **0.00** |
| 1/16 槽位换成 `iron bucket` / `giant`（真反制） | 0.00 |

换成弱怪会变容易，说明替换机制本身没破坏出怪表；**换成任何一个真反制都归零**，说明 Bot 本来就卡在 0.40 的悬崖边，加任何压力都掉下去。根因与 D-11 同一个：`block_flat` 与重甲相对卡池 DPS 太强。

因此反制版对照场景**已从校准基线里撤出**（避免 0.00 污染基线），反制器改由单测守住。`headless_run.py` 里留了注释说明原因。

**下一步的前置条件**：要先强化 Bot 的选卡与配装策略（D-10/D-13），否则无法从它身上读出反制器/无尽收敛的真实效果。

测试 80 → **92**；六关全绿 29.1s。

---

## 0. 优先级定义

| 级别 | 含义 | 判据 |
|---|---|---|
| **P0** | 验证盲区 | 不修的话，后面所有改动都可能悄悄失效而没人知道 |
| **P1** | 里程碑缺口 | 直接决定 M1–M5 能不能算"完成" |
| **P2** | 工程与资产 | 影响协作、发布、可维护性，但不阻塞玩法 |
| **P3** | 长线 | 依赖前面完成，或取决于是否要出货 |

工作量单位：人日，**粗估**，误差 ±50%。

---

## P0 · 验证盲区（建议立刻做，约 2 人日）

| ID | 问题 | 证据 | 影响 |
|---|---|---|---|
| **B-01** | **关卡回归完全缺失**：18 个关卡文件只有 2 个被模拟过 | `headless_run.py` 不 `import load_levels`；`load_levels` 仅在 `tests/test_scenarios.py:124` 出现，且只跑 `m1_01`、`m2_shield` | M1 的 10 关、M2 的 5 关、M3 的 2 关平衡性**完全未知**，等于写完就封存 |
| **B-02** | **`scenarios/` 没有线上调用方** | `endless.py` / `progression.py` 的函数只被 `__init__.py` 导出和测试引用，无任何业务代码调用 | 这些是"能跑的库"，不是"在用的功能"。M4/M5 实际进度被高估 |
| **B-03** | **奖励数据双写不同源** | 关卡 JSON 有 `reward.design_tokens`（`level_run.py:15` 透传），但 `progression.reward_for_level()` 用的是自己写死的 `CHALLENGE_TOKEN_REWARD` | 改关卡 JSON 的奖励不会生效，容易埋坑 |
| **B-04** | `app_pygame.py` 无任何测试 | 测试引用检查：`app_pygame` **无测试引用** | 渲染壳改坏了没人知道，只能靠人眼看 |
| **B-05** | CI workflow 从未真实跑过 | `.github/workflows/ci.yml` 本地无法验证 | 首次 push 可能直接红，尤其是 Godot 下载那步的版本号 |
| **B-06** | Godot 侧只有 `resolve_hit` 一个函数有门禁 | `godot/tests/run_conformance.gd` 只覆盖伤害管线 | 阶段 2 继续搬 `board` 时没有任何一致性保护 |

**动作**

1. B-01：照 `scripts/check_calibration.py` 的思路做 `scripts/check_levels.py` —— 遍历
   `levels/*.json`，每关固定 seed 跑 N 局，把胜负/时长/丢车写进 `reports/levels_baseline.json`，
   逐字段比对。**这一条最优先，因为它给 M1–M3 装上了眼睛。**
2. B-02/B-03：定夺 `scenarios/` 的定位——要么接进真正的流程（存档、关卡选择、无尽模式），
   要么明确标注为"实验性库"并从完成度里剔除。奖励以关卡 JSON 为唯一来源，
   `progression` 改为读关卡数据。
3. B-04：给 `app_pygame` 加一个 headless 截图冒烟断言（能起、精灵表全加载、截图非空）。
4. B-05：push 一次看 CI，修版本号。
5. B-06：随阶段 2 推进逐步扩门禁。

---

## P1 · 里程碑缺口（约 15–18 人日）

### M1 新手白天

| ID | 问题 | 证据 | 估 |
|---|---|---|---|
| C-01 | **游戏根本不能玩**：没有点选落子，`Simulation.step` 没接进渲染层 | `app_pygame.py:265` 的 `TODO(M1+)`；Godot 侧也是纯回放 | 2–3 |

> 这是"能不能算一个游戏"的分水岭。目前两套渲染层都是**播放器**，不是游戏。

### M2 能力挑战 + 定制器

| ID | 问题 | 证据 | 估 |
|---|---|---|---|
| C-02 | **6 个考场只有 1 个固定化**，其余 5 个仍是预算模板 | `m2_shield` = `"mode":"fixed"`；`m2_armor/speed/swarm/control/weight` = `"mode":"budget"` | 1.5 |
| C-03 | 无内置穿甲植物，高甲只能靠高爆灌伤代理 | 13 张植物 JSON 里 `armor_pierce` 出现 0 次 | 0.5（含美术重 roll） |

### M3 进阶 + Boss

| ID | 问题 | 证据 | 估 |
|---|---|---|---|
| C-04 | **Boss 没有召唤/多阶段** | `boss_50.json` 有 `"summon":{"mob":"cone","interval":12,"max_alive":3}`，但引擎 grep `summon/phase` 只命中 `config.py` 的标签名 | 2 |
| C-05 | 进阶关卡只有 2 关（规划约 10 关） | `data/levels/m3_01.json`、`m3_boss.json` | 2 |

### M4 无尽 / 反制

| ID | 问题 | 证据 | 估 |
|---|---|---|---|
| C-06 | **无铲种 API**，后期廉价株占满列、阳光囤积 | 全仓库 grep `remove_plant` / `shovel` 无命中；无尽终局阳光 900 | 1 |
| C-07 | **可解性闸门没接**，`ensure_solvable(solver=None)` 直接放行 | `endless.py:110-122` | 1.5 |
| C-08 | 无尽胜率 0.40 未收敛（目标 0.55–0.75） | `reports/calibration_baseline.json` · `endless_25w.win_rate = 0.4` | 1–2（依赖 C-06/C-07） |

### M5 僵尸编辑器 / 我是僵尸

| ID | 问题 | 证据 | 估 |
|---|---|---|---|
| C-09 | 只有"造敌人"数据层，**攻防反转玩法与编辑器 UI 完全没做** | `zombie_editor.py` 77 行，只有 `quote_points / validate_enemy_build / build_enemy_definition` | 5–8 |
| C-10 | 爬塔模式未做 | 无相关代码 | 3 |

---

## P2 · 工程与资产（约 8–10 人日）

| ID | 问题 | 证据 | 估 |
|---|---|---|---|
| D-01 | **无 LICENSE** | 根目录无 LICENSE / LICENSE.txt | 0.2 |
| D-02 | 无依赖声明，换机器靠口口相传 | 无 requirements.txt / pyproject.toml | 0.3 |
| D-03 | 无 `.gitattributes`，CRLF 噪音刷屏 | 每次 `git add` 都有几十行 `LF will be replaced by CRLF` | 0.2 |
| D-04 | **完全无音频** | 无 sound/mixer/audio 相关代码 | 3 |
| D-05 | 无存档持久化 | `progression.PlayerProgress` 只在内存（docstring 自认："持久化序列化留给上层存档模块"） | 1 |
| D-06 | Godot 播放器不是游戏 | 无输入处理，只能播回放 | 5–8（可与 C-01 合并） |
| D-07 | Godot 视觉细节：无血条、弹道画在精灵下层、朝向固定 | `ReplayPlayer.gd` 已注明 | 1–2 |
| D-08 | 无关卡/场景选择 UI | 只能靠环境变量 `PVZ_REPLAY` 换回放 | 2 |
| D-09 | 原始美术 215MB 未入库 | `.gitignore` 排除了 `plants|enemies/*/base.png`、`frames/` | 0.5（若上 Git LFS） |

---

## P3 · 长线（约 15–20 人日，取决于是否出货）

| ID | 项 | 说明 |
|---|---|---|
| E-01 | 运行时逻辑全量搬 GDScript | `balance` 已搬并通过门禁；剩 `entities` / `board` / `wavegen`，约 1150 行 |
| E-02 | `board.step` 一致性门禁 | 状态机不能逐字段比，要比"同 seed 跑完整局的终局 metrics + 关键帧快照" |
| E-03 | 移植后重新校准 | 若不能比特级一致，需重跑 100 局并重新基线化 |

> 阶段 2 的**风险已被实测降低**：引擎 RNG 是自己实现的 LCG（`board.py:54`），
> 不是 Python 的 MT19937，因此可以比特级复刻到 GDScript。

---

## 建议执行顺序

| 批次 | 内容 | 工期 | 产出 |
|---|---|---|---|
| **①** | B-01, B-02/03, B-04, B-05 | 2 天 | 关卡平衡可见、数据同源、CI 真跑 |
| **②** | C-01 + D-06（合并做） | 1 周 | **游戏能玩**——点选落子 + 实时步进 |
| **③** | C-02, C-03, C-06 | 3 天 | M2 考场齐、M4 铲种 |
| **④** | C-04, C-05, C-07, C-08 | 1–2 周 | M3/M4 收口，无尽收敛 |
| **⑤** | C-09, C-10, D-01~D-09 | 2–3 周 | M5 + 发布准备 |
| **⑥** | E-01~E-03（可选） | 3–4 周 | 全量 Godot 化 |

**关键判断**：批次 ② 之前，这个项目严格来说还不是"游戏"，是"数值实验室 + 回放播放器"。
如果目标是尽快能给人试玩，②应该提到 ① 之前；如果目标是先把数值做扎实，按现在顺序。

---

## 明确不做（避免范围蔓延）

- 不复刻任何原版游戏素材（角色/名称/美术全部自研）
- 不做联网 / 排行榜 / 内购
- 不做关卡编辑器（定制器 + 僵尸编辑器已覆盖"造内容"需求）
- 不追求 3D 或高保真美术（Q 版粗描边是既定风格）

---

## 附：本清单的审计方法

1. `grep` 全仓库的 `TODO/FIXME/预留/待接/暂不` → 只有 2 处真 TODO（`app_pygame.py:265`、`endless.py:110`）
2. 逐模块检查测试引用 → 发现 `app_pygame` 无测试
3. 逐函数检查"非测试调用方" → 发现 `scenarios/` 整体无线上使用
4. 逐关卡检查 `spawn.mode` → 发现 5/6 考场仍是 budget
5. 引擎 grep `summon|phase|remove_plant` → 确认 Boss 召唤与铲种均未实现
6. 植物 tags 汇总 → 确认无 `armor_pierce`
7. 仓库元文件检查 → LICENSE / requirements / .gitattributes 全缺
