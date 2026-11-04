# tdgame —— 数据驱动塔防（headless 与真机共用一套数值）

原创塔防的工程主体。设计原则：**所有确定性战斗/经济/品阶逻辑都在纯标准库模块里，
pygame 只做薄渲染**，因此同一份 `balance.py` 既能被 headless 模拟器批量回归，也驱动未来真机，
保证文档数值与战斗结果一致、可手算复现。数值唯一事实来源是根目录 `game_balance_design.md` v0.2。

## 目录结构

```
tdgame/
├── config.py              # 全局口径常量（棋盘/经济/品阶/代币/recharge）
├── balance.py             # 纯数值：power/品阶/代币/三维成本 + 确定性伤害管线
├── headless_run.py        # 批量回归 CLI（--runs N --scenes ...），输出 reports/*.json
├── app_pygame.py          # pygame 薄渲染壳（占位，支持 dummy 冒烟/截图）
├── engine/
│   ├── entities.py        # Plant/Enemy/Projectile 数据实体
│   ├── board.py           # Simulation：固定步长推进、出怪、啃食、子弹、小车/破线
│   ├── wavegen.py         # 预算出怪/固定表/白名单/单波上限
│   ├── bot.py             # RuleBot：经济流、刚性破盾、补墙、后期爆兵
│   └── loader.py          # JSON -> Registry，派生 power/tier/recharge 并校验
├── scenarios/
│   ├── customizer.py      # M2 植物定制器（五轴+标签+代币+阶段准入 -> 可注册植物卡）
│   ├── zombie_editor.py   # M5 僵尸编辑器（四维点数+能力标签 -> 可注册敌人）
│   ├── endless.py         # M4 无尽缩放 + counter_map 自动反制选怪 + 可解性闸门
│   ├── progression.py     # P1–P4 阶段/代币奖励/解锁流
│   └── level_run.py       # 关卡 JSON -> 出怪表 -> Simulation 的桥
└── data/
    ├── plants/*.json      # 13 张内置植物
    ├── enemies/*.json     # 8 种内置敌人（含格挡盾兵、重甲、巨人、50轮Boss）
    ├── levels/*.json      # 18 个关卡：M1×10、M2×6、M3×2（由 scripts/gen_levels.py 生成）
    └── counter_map.json   # 7 组克制关系 + 6 条反制选择规则 + headless 目标胜率
```

## 分层依赖（单向，不回头）

`data(JSON)` → `loader 校验/派生` → `balance 公式` → `engine 模拟` → 上层 `headless_run / scenarios / app_pygame`。
渲染层不得重算任何战斗公式，只读取 Registry 与 Simulation 状态。

## 运行方式

解释器：`D:\ProgramData\anaconda3\python.exe`（3.11）。pygame 是项目自包含依赖，位于 `libs/`，
跑渲染相关命令前把它加进 `PYTHONPATH`；纯 headless/单测不需要 pygame。

```powershell
$py = "D:\ProgramData\anaconda3\python.exe"
# 单元测试（39 个：balance 12 + engine 11 + scenarios 16）
& $py -m unittest tests.test_balance tests.test_engine tests.test_scenarios
# headless 批量回归
& $py -m tdgame.headless_run --runs 100
# 重新生成关卡 JSON
& $py scripts\gen_levels.py
# pygame 薄壳 dummy 冒烟
$env:SDL_VIDEODRIVER="dummy"; $env:SDL_AUDIODRIVER="dummy"
$env:PYTHONPATH="D:\lucia\rea\project\pvz\libs;D:\lucia\rea\project\pvz"
& $py -m tdgame.app_pygame --smoke --frames 3 --shot logs\app_smoke.png
```

## M0–M5 骨架地图（本轮交付的是"可跑可测的活骨架"，非空壳）

| 里程碑 | 已落地 | 关键入口 | 预留边界（后续做） |
|---|---|---|---|
| M0 战斗地基 | balance 伤害管线、Simulation、loader、RuleBot、headless、pygame 薄壳 | `engine/`、`balance.py` | 铲种升级 API |
| M1 新手白天 | 10 关逐关加波/解锁到双发，白名单不出重甲 | `data/levels/m1_*.json`、`level_run` | 真机点选落子、剧情引导 |
| M2 能力挑战+定制 | 格挡固定考场（smart/dumb 确定性对照）+ 定制器配装/代币/阶段门 + 另 5 考场骨架 | `scenarios/customizer.py`、`m2_*.json` | 其余 5 考场固定化、工坊美术联动 |
| M3 进阶+Boss | 进阶首关 + 50 轮门槛 Boss 固定表 | `data/levels/m3_*` | Boss 召唤/多阶段（JSON 字段已预留） |
| M4 无尽/反制 | 轮次缩放、counter_map 反制选怪、每 50 轮 Boss、可解性闸门接口 | `scenarios/endless.py` | 接 headless solver、铲种升级、爬塔 |
| M5 僵尸编辑/我是僵尸 | 四维点数+标签预算、可注册敌人校验 | `scenarios/zombie_editor.py` | "我是僵尸"攻防反转玩法、编辑器 UI |

## 校准结论

见 `reports/headless_calibration_report.md`：100 局回归下新手 92% 通关、格挡考场
破盾 100% 对纯直射 0%、Boss 高配 79% 对低配 0%，核心机制门槛全部正确分化；
无尽深度压力（30%）与阳光囤积明确归 M4 反制器处理。
