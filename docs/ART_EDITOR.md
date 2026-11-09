# 美术资源编辑指南

两条路：**要精细就用图形编辑器**，**只想换张图就用命令行**。

---

## 一、图形编辑器（推荐给人用）

双击仓库根目录的 **`editor.bat`**。

它启动 `anim_demo/plant_editor.py`（Tkinter，纯标准库，无需装东西），五步向导：

1. **描述与 Prompt** —— 填植物中文名、外观描述；右侧只读预览自动拼好的完整 prompt
2. **立绘三选一** —— 后台并发抽 3 张候选，点「选它」定稿为 `base.png`
3. **动作帧** —— 一键批量生成全部缺失帧（断点续跑），单帧可重 roll，旧版自动备份
4. **子弹/飞行道具** —— 可选，产出独立透明底 `projectile.png`
5. **拼表预览** —— 去背 + 全局统一缩放拼表，可直接拉起预览

**已实测**：编辑器能正常构造并销毁（`App` 构造 OK，标题「植物工坊 Plant Forge —— 原创植物定制」）。

> 需要 token：优先读环境变量 `MODELSCOPE_TOKEN` / `MS_TOKEN`，
> 也可在界面右上角填写并存到本地 `anim_demo/.ms_token`（已 gitignore，别提交）。
> 仓库里本地已有可用 token。

---

## 二、命令行素材管理（最快，适合"我画好了，直接换"）

```powershell
# 看所有单位、哪些有图哪些缺
python tools\art_manager.py list

# 用你自己画的一张 PNG 替换（自动裁边、居中、铺满 4x4 网格）
python tools\art_manager.py import snow_pea D:\我的图\snow_pea.png

# 用一整个帧目录替换（逐帧、全局统一缩放、底部锚点对齐）
python tools\art_manager.py import snow_pea D:\我的帧\snow_pea\

# 从该单位已有的 base.png / frames 重新拼表
python tools\art_manager.py rebuild snow_pea

# 只跑校验
python tools\art_manager.py verify
```

每次替换后**自动跑 `check_sprites`**，不达标会直接报出来（比如宽高比越界、某帧空、某帧多个角色），不会静默写坏。

---

## 三、精灵表的硬规格（自己画图必须遵守）

| 项 | 要求 |
|---|---|
| 尺寸 | **256×256**，PNG，透明背景 |
| 网格 | 4 列 × 4 行，每格 64×64 |
| 行序 | 第 0 行 idle（2 帧）／第 1 行 walk（4）／第 2 行 attack（3）／第 3 行 hurt（2） |
| 用不到的格 | 留空透明 |
| 角色位置 | 每格内**底部居中**（锚点约 x=32, y=58），保证切帧不跳变 |
| 宽高比 | 内容宽高比在 **[0.35, 1.3]** 之间（太瘦长会被拒） |
| 单帧内容 | 每帧只允许**一个**角色 |

植物不移动，walk 行通常会回退成 `idle_0` 静立——`build_spritesheet.py` 会自动兜底并给出 warn，不算错误。

---

## 四、文件放哪

| 类型 | 路径 |
|---|---|
| 植物精灵表 | `anim_demo/assets/sprites/<key>.png`（**根目录，扁平，没有 plants 子目录**） |
| 敌人精灵表 | `anim_demo/assets/sprites/enemies/<key>.png` |
| 生成源（立绘/帧） | `anim_demo/assets/plants/<key>/base.png`、`.../frames/*.png` |
| 单位数据 | `tdgame/data/plants/<key>.json`、`tdgame/data/enemies/<key>.json` |

`<key>` 用数据 JSON 里的英文 `key`，不是中文名。

---

## 五、换完之后

```powershell
# 校验精灵表规格
python scripts\check_sprites.py

# 校验游戏能否全部加载
python scripts\check_render.py --shot-dir _work
```

两者都 PASS 就等于生效了；游戏运行中按 **R** 可热重载（`sprite_animation_demo.py` 里），
进游戏（`run_game.bat`）则会直接加载新图。
