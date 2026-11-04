# 开发流程

接手后建立的质量门禁与日常流程。核心原则只有一条：

> **Python 引擎（`tdgame/`）是唯一事实源。** 渲染层只读状态，绝不重算战斗公式；
> GDScript 侧的实现是"被验证的候选"，由黄金用例钉死。

---

## 1. 环境

| 项 | 值 |
|---|---|
| Python | `D:\ProgramData\anaconda3\python.exe`（3.11.7） |
| pygame | 项目内自包含 `libs/`（已入库） |
| Godot | 4.7.2（`D:\apps\Godot\Godot_v4.7.2-stable_win64.exe`） |
| 依赖 | `numpy`、`pillow`（Anaconda 自带） |

跑 pygame 相关脚本前需要：

```powershell
$env:PYTHONPATH = "D:\lucia\rea\project\pvz\libs;D:\lucia\rea\project\pvz"
$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"
```

---

## 2. 一键总检（改完代码跑这个）

```powershell
$env:PVZ_PYTHON = "D:\ProgramData\anaconda3\python.exe"
$env:PVZ_GODOT  = "D:\apps\Godot\Godot_v4.7.2-stable_win64.exe"
pwsh -File scripts\check_all.ps1
```

四道关卡，任何一道失败即 exit 1：

| 关卡 | 命令 | 守什么 |
|---|---|---|
| 1. Python 单测（50 个） | `python -m unittest tests...` | 伤害管线、引擎确定性、场景、回放、黄金文件同步 |
| 2. 精灵表体检 | `python scripts/check_sprites.py` | 表结构、角色宽高比离群、源帧多角色拼图 |
| 3. 一致性门禁 | `scripts\run_conformance.ps1` | GDScript 的 `resolve_hit` 与 Python 逐字段一致 |
| 4. pygame 冒烟 | `python -m tdgame.app_pygame --smoke` | 渲染壳仍能起 |

没有 Godot 时可以 `-SkipGodot` 跳过第 3 关。

---

## 3. 常见改动怎么做

### 改了 `tdgame/balance.py`

黄金用例会失同步，`tests.test_golden_sync` 会立刻红。修法：

```powershell
python scripts/gen_golden_hits.py
```

然后重跑总检——第 3 关会告诉你 GDScript 侧要不要跟着改。

### 改了 `godot/scripts/BalanceHit.gd`

必须过第 3 关。想确认门禁没被"糊弄过去"，可以做变异测试：把
`AP_MULT_DEFAULT` 从 2.0 改成 2.5，应当有 200+ 条失败、exit 1，改回来再归零。

### 改了 `tdgame/replay.py` 的回放格式

`tests/test_replay.py` 会守 schema（帧长度、`t0=0`、步长精确 `DT`、metrics 与末帧一致）。
改完记得重新生成 `replays/`：

```powershell
python -m tdgame.replay --scene m1_day_10w --seed 1000
```

### 新增一个角色（美术）

1. `tdgame/data/plants|enemies/` 加 JSON，`python scripts/list_roster.py` 确认 `loader errors: none`
2. `anim_demo/gen_plant.py` / `gen_enemy.py` 加 `cn/base_desc/attack` 配置
   - **`base_desc` 只写绝对描述**。写「比普通僵尸更瘦小」这种**相对比较**会诱导模型
     返回四视图/多姿态拼图 —— fast/giant 两张坏表就是这么来的
3. `--phase base --keys <key>` 出立绘，**先确认是单角色**再出帧
4. `--phase frames` → `--phase sheet` → `python scripts/check_sprites.py`

### 改了美术管线本身

`build_spritesheet.py` 的 `build_dir` 现在会自检多角色帧并打 `[warn]`。

> ⚠️ 它用的是**全局统一 scale**（取所有帧最紧边）。只要一帧是拼图，整张表 11 格会一起
> 被压扁。**warn 不是可忽略项**，看到就说明这批帧要重出。

---

## 4. CI

`.github/workflows/ci.yml` 两个 job：

- `python checks`：单测 + 精灵表体检
- `resolve_hit conformance`：下载 Godot → 重新生成黄金用例 → 跑门禁

Godot 版本通过 workflow 顶部的 `GODOT_VERSION` 控制。

> ⚠️ 这份 workflow **尚未在真实 CI 上跑过**（本地无法验证 GitHub Actions）。
> 首次 push 若 `Download Godot` 步骤失败，多半是版本号对应的文件名不匹配，
> 改 `GODOT_VERSION` 即可。

---

## 5. 不要提交的东西

`.gitignore` 已覆盖，别手动 `git add -f` 绕过：

| 路径 | 原因 |
|---|---|
| `anim_demo/.ms_token` | **机密**，ModelScope token |
| `ghidra-project/`、`unpacked/` | 早期逆向产物，版权敏感，不得分发 |
| `*.zip` | 两个交接包共 227MB |
| `anim_demo/assets/plants|enemies/*/base.png`、`frames/` | AI 原始大图约 215MB |
| `_work/`、`_artfix/`、`logs/` | 本地过程产物 |

---

## 6. 提交前清单

```powershell
pwsh -File scripts\check_all.ps1     # 必须 PASS
git status --short                   # 确认没有 _work/ _artfix/ logs/ 混入
git add -A
git commit -m "..."                  # 说明改了什么、为什么、验证结果
git push                             # 远端走 SSH，不走 gh-proxy
```
