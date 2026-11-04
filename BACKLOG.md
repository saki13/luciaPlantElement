# 待修补任务清单（BACKLOG）

> 生成日期：2026-11-04
> 依据：`HANDOVER.md` §9、`tdgame/README.md` 的 M0–M5 预留边界、`game_balance_design.md` §18、
> 以及对代码/数据/测试的实测审计（每条都标了证据位置）。
> **优先级按"不修会让后续工作失真"排序**，不是按"看起来爽"排。

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
