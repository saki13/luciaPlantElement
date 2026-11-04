# Godot 4 回放播放器（阶段 1）

这个工程**只做渲染，零战斗逻辑**。所有位置、血量、胜负都来自 Python 引擎导出的确定性快照，
Godot 只负责插值与切帧。这样 `tdgame/` 仍然是唯一事实源，39 个单测和 100 局校准结论完全不受影响。

## 首次运行

```powershell
# 1) 用 Godot 4.x 打开工程（任选其一）
godot --path godot                 # 编辑器里打开
godot --path godot --editor        # 明确进编辑器

# 2) 直接播放默认回放（m1_day_10w, seed 1000）
godot --path godot

# 3) 指定回放
godot --path godot -- --replay=../replays/boss50_late_s1002.json
```

首次打开会生成 `.godot/` 缓存目录（可随时删除，不入库）。

## 环境变量

| 变量 | 作用 |
|---|---|
| `PVZ_REPLAY` | 回放 JSON 路径（优先于 `--replay=`） |
| `PVZ_SPRITES` | 精灵表目录，默认 `../anim_demo/assets/sprites` |
| `PVZ_SPEED` | 播放倍速，默认 `1.0`（`4` 可快速看完一局） |
| `PVZ_AUTOQUIT` | 设为 `1` 时播完自动退出，用于 CI 冒烟 |

```powershell
$env:PVZ_AUTOQUIT="1"; $env:PVZ_SPEED="4"
godot --headless --path godot
```

`--headless` 不渲染但会跑完 `_process`，适合在 CI 里验证回放能被正确解析、单位能正确生成。

## 冒烟输出（成功时应看到，Godot 4.7.2 实测）

```
Godot Engine v4.7.2.stable.official.ed1daf0bf
replay loaded: D:/lucia/rea/project/pvz/replays/m1_day_10w_s1000.json
  scene=m1_day_10w seed=1000 frames=1296 win=true
  sprite_root=D:/lucia/rea/project/pvz/anim_demo/assets/sprites
playback finished at t=129.5s  sun=50 lives=5
```

`sun=50` 是 seed 1000 这一局的真实终局阳光（即 `replays/m1_day_10w_s1000.json` 的
`meta.metrics.sun_left`），**不是** 100 局平均的 47。这局 `mowers_used=0 / breaches=0`，干净胜利。

若出现 `WARNING: 1 sprite(s) missing`，说明 `PVZ_SPRITES` 指错了目录。

## 资源不复制

本工程**不复制**美术资源，直接按绝对路径读取 `anim_demo/assets/sprites/`，保证美术管线仍是单一来源。
代价是导出正式包时需要把它们挪进 `res://`（阶段 2 再做）。

## 已知限制

- 弹道按"等速直飞"反推位置，不是逐帧插值——因为回放里的弹道没有 uid，无法可靠配对。
- 没有血条、音效、点选交互；这些属于阶段 2。
- 单位朝向固定朝左（敌人）／朝右（植物），回放目前不记录翻转。

## 这份代码的验证状态

| 部分 | 状态 |
|---|---|
| `tdgame/replay.py`（回放导出） | ✅ `tests/test_replay.py` + `_work/verify_replay.py`：同 seed 字节级可复现、schema 自洽、所有单位都有素材 |
| `godot/` 逻辑路径 | ✅ **已实测**（Godot 4.7.2）：`Main.tscn` 解析、两个 GDScript 编译、21 张精灵表全部加载、`SpriteFrames` 切格、1296 帧插值推进、干净退出，零 warning |
| `godot/` 视觉路径 | ⚠️ **headless 不执行 `_draw()`**，所以棋盘/小车/弹道这些自绘元素尚未肉眼确认。需要**开窗口**跑一次看画面 |

> 注：`--headless` 只验逻辑，不验画面。上面冒烟通过说明"数据能被正确解析成实体"，
> 但"实体画在正确位置"要靠开窗口或者对照 `_work/replay_preview_m1.png`（Python 参考渲染器，
> 用的是同一套布局数学）。

如果 `_ready()` 报 `Script not found` 或场景打不开，最可能是 `Main.tscn` 的 `ext_resource`
路径写法与你的 Godot 版本不匹配，在编辑器里重新挂一次脚本即可。

---

# 阶段 2 第一步：`resolve_hit` 一致性门禁

阶段 2 要把运行时逻辑搬成 GDScript，但**两套实现必然漂移**，而漂移的代价是那套 100 局校准结论。
所以先只搬最关键、最容易验证的那一个纯函数——`tdgame/balance.py::resolve_hit`（确定性伤害管线）——
并用黄金用例把两者钉死。

## 数据流

```
tdgame/balance.py  ──(唯一事实源)──►  scripts/gen_golden_hits.py
                                              │
                                              ▼
                              godot/tests/golden_resolve_hit.json
                                              │
godot/scripts/BalanceHit.gd ──(候选实现)──►  godot/tests/run_conformance.gd ──► PASS / FAIL
```

Python 先生成「敌人初始状态 + 逐次伤害序列 → 每一步的明细和结算后血量」，
GDScript 侧只复现输入、逐字段比对输出。**客户端零战斗逻辑**这条红线依然成立：
GDScript 是被验证的候选实现，Python 才是权威。

## 一条命令

```powershell
pwsh -File scripts\run_conformance.ps1
```

或用环境变量指定路径：

```powershell
$env:PVZ_PYTHON = "D:\ProgramData\anaconda3\python.exe"
$env:PVZ_GODOT  = "D:\apps\Godot\Godot_v4.7.2-stable_win64.exe"
pwsh -File scripts\run_conformance.ps1
```

## 覆盖范围（747 用例 / 827 次伤害）

| 组 | 内容 |
|---|---|
| A | 8 种真实敌人 × 17 档伤害（含 0、负数、20.0001、33.3333、5000）× 4 种标签组合 |
| B | 显式 `ap_mult` 扫 5 档（`None`/1.0/1.5/2.0/3.0），只作用于甲段 |
| C | 边界：伤害恰好等于格挡值 / 等于格挡±1；恰好等于甲段可吸收上限 `armor_hp/ap`、及 ±0.5 |
| D | 合成极端配置：`block_flat=1000`、`armor_hp=1`、`reduction=0.999`、`hp_body=0.1`、格挡+护甲叠加 |
| E | 连续多段伤害（4 种序列 × 5 个敌人）：状态累积与每步 `round(...,6)` 的确定性 |

## 当前状态

**827/827 通过，`max_abs_diff = 0.0`——比特级一致。**

门禁本身做过变异测试，证明它不是空转：

| 操作 | fails | max_abs_diff | 退出码 |
|---|---|---|---|
| 正常 | 0 | 0.0 | 0 |
| 把 `AP_MULT_DEFAULT` 从 2.0 改成 2.5 | 210 | 260.0 | 1 |
| 还原 | 0 | 0.0 | 0 |

## 防漂移

`tests/test_golden_sync.py`（3 个用例）会在每次跑 Python 单测时重新生成一遍用例，
与仓库里那份逐字段比对。如果有人改了 `balance.py` 却没重新生成黄金文件，测试立刻失败。
修法就一句：`python scripts/gen_golden_hits.py`。

## 落地时的两个坑（已踩过）

1. **Python `round()` 是"平局取偶"，GDScript 的 `round()` 是"平局远离零"**。
   `BalanceHit.gd` 用 `String.num(x, n).to_float()` 复刻 Python 语义，827 次伤害零偏差。
2. **Windows PowerShell 5.1 读无 BOM 的 UTF-8 `.ps1` 会按 ANSI 解析**，中文注释直接把脚本解析崩。
   所以 `scripts/run_conformance.ps1` 刻意写成纯 ASCII，中文说明只放在本文件里。

