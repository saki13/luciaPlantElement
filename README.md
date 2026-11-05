# 原创塔防（PVZ-like）：从逆向练习到可玩游戏

> 本仓库最初是一次**逆向学习练习**的交付物（解包原版资源、定位三大核心函数、
> 用 Python 重写一个不依赖原版素材的塔防原型）。之后它演进成了一个**可玩的
> 塔防游戏**：纯标准库的确定性 headless 引擎 + pygame 客户端 + Godot 回放/移植。
>
> 原始练习的两份交付物仍在仓库根目录（`tower_defense_pygame.py`、
> `tower_defense_prototype.py`），保留作为那次练习的记录。**现在的主线是 `tdgame/`。**

## 一、怎么跑

统一用 Anaconda 的 Python（系统便携 Python 的 tkinter 缺 init.tcl）。

```powershell
# 1) 可玩客户端（主线守关，鼠标点卡点格种植，X 铲子，R 重开，[ ] 换关）
python -m tdgame.app_pygame

# 2) M5 我是僵尸（攻防反转：植物是预置的，你花预算投僵尸去啃光它们）
python -m tdgame.app_pygame --mode izombie

# 3) 无头批量回归（不需要显示器）
python -m tdgame.headless_run --runs 20

# 4) 一键总检：八道门禁，约 55 秒
pwsh -File scripts\check_all.ps1
```

Windows 本机 pygame 在项目自带的 `libs/`（`pip install --target=./libs pygame`），
程序会自动回退到它；CI/Linux 用 pip 安装的 pygame。

**操作**：点卡片选植物 → 点格子种下；`X` 切铲子；`R` 重开本关；`[` `]` 切关卡；
`Q` 退出。价格标签变暗表示阳光不够或还在冷却。

## 二、项目结构

```
tdgame/                 主线（纯标准库，无第三方依赖即可 headless 跑）
  config.py             全部数值旋钮（DT=0.1、格子、波次、经济）
  balance.py            resolve_hit 等伤害结算的唯一实现（跨语言移植的基准）
  engine/board.py       确定性定步长模拟（唯一的战斗真相）
  engine/session.py     PlaySession：可玩交互状态机（点选/铲种/冷却/胜负）
  engine/bot.py         RuleBot：headless 自动布阵（回归与难度评估用）
  engine/trace.py       逐步状态 trace（跨语言一致性门禁的数据源）
  engine/solver.py      可解性求解器（给闸门提供真实胜率）
  scenarios/            endless / progression / level_run / savegame / tower / i_zombie
  data/                 关卡、植物、敌人、我是僵尸关卡（全部 JSON）
  app_pygame.py         可玩客户端（只负责画与输入，绝不重算战斗公式）
  replay.py             回放导出（给 Godot 播）
scripts/                门禁与工具：check_all / check_levels / check_calibration /
                        check_render / check_sprites / check_board_trace / check_izombie …
godot/                  Godot 4 项目：回放播放器 + BoardSim.gd（运行时移植）
reports/                基线（校准/关卡/trace）与校准报告
tests/                  153 个测试
```

## 三、设计约束（重要）

1. **Python 引擎是唯一真相**。渲染层（pygame / Godot）只画，**绝不重算战斗公式**。
2. **确定性**：固定步长 `DT=0.1`，自带 LCG 随机源，同一 seed 永远同一结果。
   所有基线都是**逐字段精确比对**，没有容差。
3. **改数值必须重新基线化**：`python scripts/check_calibration.py --update` 等。
4. **跨语言一致**：GDScript 侧的 `BoardSim.gd` 必须与 Python 逐步一致，
   由 `scripts/check_board_trace.py` 守（目前 **8 场景 / 2554 步零差异**）。

## 四、内容规模

| 项 | 数量 |
|---|---|
| 关卡 | 25（M1×10、M2×6、M3×8 + Boss×1） |
| 植物 | 14 种（含内置穿甲株 `thorn_piercer`） |
| 敌人 | 8 种（普通/快速/路障/铁桶/巨人/旗帜/盾兵/Boss） |
| M5 我是僵尸关卡 | 3（预算 20 / 34 / 100） |
| 爬塔 | 20 层，每 10 层一个攻坚层 |
| 测试 | 153 |
| 门禁 | 8 道，一键约 55 秒 |

## 五、八道门禁

`pwsh -File scripts\check_all.ps1` 依次跑：

1. **单元测试**（153 个）
2. **精灵表体检**（表结构、宽高比、每帧单角色）
3. **校准基线**（6 个场景 × 20 局，逐字段比对）
4. **关卡回归**（25 关 × 5 seeds，逐字段比对）
5. **渲染断言**（会话/卡栏/自动对局/截图非纯色/降级模式）
6. **resolve_hit 一致性**（Python oracle vs GDScript，827/827）
7. **我是僵尸闸门**（关卡可解性、预算约束、可玩渲染、无铲子）
8. **board.step 逐步 trace**（8 场景 / 2554 步，Python 与 GDScript 逐步一致）

加 `-SkipGodot` 可跳过需要 Godot 的步骤。

## 六、已知问题（诚实清单）

- **D-11 Boss 实际打不死**：`boss_50` 的 `block_flat=30` 把豌豆/双发的伤害完全归零，
  唯一有效的破盾株只有 28.6 dps，打不完 5500 原始伤害。此前 `boss50_late` 的
  0.79 胜率**全部来自割草机清场**。需要一次专门的 Boss 数值重做（降 block 或给卡池补高单发）。
  爬塔的 Boss 层因此暂用巨人攻坚（`tower.BOSS_KEY`，改一行即可换回）。
- **Bot 不会评估性价比**：把新卡加进 Bot 卡池反而可能降低胜率
  （穿甲株让 `boss50_late` 从 0.40 掉到 0.00）。
- **GDScript 侧还没有 Bot 与出怪调度**，不能脱离 Python 独立跑完整对局。
  这是"全量 Godot 化"真正的大头。
- **移植未覆盖**：一次性植物（爆栗）、碎片/穿透计数、植物被动。
- ~~LICENSE 尚未确定~~ → **已采用 MIT**（见 `LICENSE`）。

## 七、合规边界

- 逆向**自己合法拥有**的游戏用于个人学习可以；
  **不要分发原版 exe 或提取出的美术/音频**。
- 本项目的角色形象、名称、数值与全部代码均为原创，
  不照搬原版角色形象；`unpacked/`、`ghidra-project/` 等逆向中间产物**不入库**。

## 八、开发约定

见 [CONTRIBUTING.md](CONTRIBUTING.md)（环境、六阶段流程、改什么要重新基线化、
禁止提交清单、CI 章节与踩过的坑）与 [BACKLOG.md](BACKLOG.md)（任务清单与进度）。
校准方法与历史数字见 [reports/headless_calibration_report.md](reports/headless_calibration_report.md)。
内容扩展规划（品阶体系 / 植物解锁 / 新增关卡批次 / 爬塔曲线）见 [ROADMAP.md](ROADMAP.md)。
