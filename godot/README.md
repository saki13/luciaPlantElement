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
